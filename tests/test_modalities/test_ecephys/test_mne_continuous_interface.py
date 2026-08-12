"""Tests for BaseMNEContinuousDataInterface via the synthetic MockMNEContinuousDataInterface.

These exercise the base's ``mne.io.BaseRaw`` -> ElectricalSeries + electrodes-table write path
with no data on disk. Scope mirrors v1: voltage channels only, no electrode geometry, no
temporal alignment.
"""

from datetime import datetime

import numpy as np
import pytest
from pynwb import NWBHDF5IO

pytest.importorskip("mne")

from neuroconv.datainterfaces.ecephys.basemnecontinuousdatainterface import (  # noqa: E402
    BaseMNEContinuousDataInterface,
)
from neuroconv.tools.mne import MNERawDataChunkIterator  # noqa: E402
from neuroconv.tools.testing.mock_interfaces import (  # noqa: E402
    MockMNEContinuousDataInterface,
)


class OnDiskMNEInterface(BaseMNEContinuousDataInterface):
    """Reads a ``.fif`` from disk with ``preload=False``, the case the chunk iterator exists for.

    The ``RawArray`` the mock builds is preloaded by construction, so it cannot show that the write
    path leaves a lazily-opened Raw on disk.
    """

    def __init__(self, file_path, **kwargs):
        self.file_path = file_path
        super().__init__(**kwargs)

    def _read_raw(self):
        import mne

        return mne.io.read_raw_fif(self.file_path, preload=False, verbose=False)

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        return metadata


@pytest.fixture
def lazy_interface_and_source(tmp_path):
    """Write a ``.fif`` to disk and return an interface reading it lazily, plus the source array."""
    import mne

    number_of_channels, number_of_samples = 8, 5_000
    source = np.random.default_rng(0).standard_normal((number_of_channels, number_of_samples)) * 1e-5
    info = mne.create_info(
        ch_names=[f"CH{index}" for index in range(number_of_channels)],
        sfreq=1000.0,
        ch_types="eeg",
    )
    file_path = tmp_path / "raw.fif"
    mne.io.RawArray(source, info, verbose=False).save(file_path, overwrite=True, verbose=False)

    return OnDiskMNEInterface(file_path=file_path), source


def test_electrical_series_written_and_data_round_trips():
    interface = MockMNEContinuousDataInterface(num_channels=6, sampling_frequency=250.0, duration=2.0)
    nwbfile = interface.create_nwbfile()

    assert "ElectricalSeries" in nwbfile.acquisition
    electrical_series = nwbfile.acquisition["ElectricalSeries"]

    # MNE Raw is (n_channels, n_times); the ElectricalSeries stores (n_times, n_channels).
    expected = interface.raw.get_data().T
    np.testing.assert_allclose(electrical_series.data[:], expected)
    assert electrical_series.data.shape == (500, 6)

    # Regularly sampled from sfreq, no alignment, MNE already in volts.
    assert electrical_series.rate == 250.0
    assert electrical_series.starting_time == 0.0
    assert electrical_series.conversion == 1.0


def test_electrodes_table_has_channel_names_and_no_geometry():
    interface = MockMNEContinuousDataInterface(num_channels=4)
    nwbfile = interface.create_nwbfile()

    electrodes = nwbfile.electrodes
    assert electrodes is not None
    assert len(electrodes) == 4

    # channel_name column mirrors the Raw channel order.
    assert "channel_name" in electrodes.colnames
    assert list(electrodes["channel_name"][:]) == interface.raw.ch_names

    # v1 writes no coordinates.
    for coordinate_column in ("x", "y", "z", "rel_x", "rel_y", "rel_z"):
        assert coordinate_column not in electrodes.colnames


def test_mixed_voltage_channel_types_all_written():
    # eeg + eog are both voltage; v1 writes them together in one ElectricalSeries.
    interface = MockMNEContinuousDataInterface(num_channels=3, ch_types=["eeg", "eeg", "eog"])
    nwbfile = interface.create_nwbfile()

    assert nwbfile.acquisition["ElectricalSeries"].data.shape[1] == 3
    assert len(nwbfile.electrodes) == 3


def test_write_electrical_series_false_writes_only_electrodes():
    interface = MockMNEContinuousDataInterface(num_channels=4)
    nwbfile = interface.create_nwbfile(write_electrical_series=False)

    assert len(nwbfile.acquisition) == 0
    assert nwbfile.electrodes is not None
    assert len(nwbfile.electrodes) == 4


def test_round_trip_through_disk(tmp_path):
    interface = MockMNEContinuousDataInterface(num_channels=5, sampling_frequency=100.0, duration=1.0)
    nwbfile_path = tmp_path / "mne_continuous.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    expected = interface.raw.get_data().T
    with NWBHDF5IO(path=str(nwbfile_path), mode="r") as io:
        read_nwbfile = io.read()
        read_series = read_nwbfile.acquisition["ElectricalSeries"]
        np.testing.assert_allclose(read_series.data[:], expected)
        assert read_series.rate == 100.0
        assert list(read_nwbfile.electrodes["channel_name"][:]) == interface.raw.ch_names


def test_full_write_streams_from_disk_without_preloading(lazy_interface_and_source):
    """The full write goes through the iterator, so a `preload=False` Raw is never materialized."""
    interface, source = lazy_interface_and_source
    assert interface.raw.preload is False

    nwbfile = interface.create_nwbfile()
    electrical_series = nwbfile.acquisition["ElectricalSeries"]

    assert isinstance(electrical_series.data, MNERawDataChunkIterator)
    assert electrical_series.data.shape == (source.shape[1], source.shape[0])
    assert interface.raw.preload is False


def test_iterator_selections_are_transposed_and_faithful(lazy_interface_and_source):
    """Each selection comes back in (n_times, n_channels) order with the source values."""
    interface, source = lazy_interface_and_source
    iterator = MNERawDataChunkIterator(raw=interface.raw)

    selection = iterator[100:200, 2:5]

    assert selection.shape == (100, 3)
    np.testing.assert_allclose(selection, source[2:5, 100:200].T)
    assert interface.raw.preload is False


def test_iterated_write_round_trips_through_disk(lazy_interface_and_source, tmp_path):
    """Every buffer reaches the file: the written dataset matches the source end to end."""
    interface, source = lazy_interface_and_source
    nwbfile_path = tmp_path / "lazy_mne.nwb"

    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    with NWBHDF5IO(path=str(nwbfile_path), mode="r") as io:
        written = io.read().acquisition["ElectricalSeries"]
        np.testing.assert_allclose(written.data[:], source.T)


def test_stub_test_reads_only_the_stub(lazy_interface_and_source):
    """`stub_test` reads its slice through the Raw's own start/stop, not by loading everything."""
    interface, source = lazy_interface_and_source

    nwbfile = interface.create_nwbfile(stub_test=True)

    electrical_series = nwbfile.acquisition["ElectricalSeries"]
    assert electrical_series.data.shape == (100, source.shape[0])
    np.testing.assert_allclose(electrical_series.data, source[:, :100].T)
    assert interface.raw.preload is False
