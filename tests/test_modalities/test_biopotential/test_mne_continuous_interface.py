"""Tests for the MNE-backed continuous interfaces, via the synthetic mocks and a real `.fif` on disk.

One interface writes one MNE channel type to one neurodata object, so the destination classes are
tested separately and the streaming machinery they share is tested once, through whichever of them is
convenient. Scope mirrors v1: no electrode geometry, no temporal alignment.
"""

from datetime import datetime

import numpy as np
import pytest
from pynwb import NWBHDF5IO

pytest.importorskip("mne")

from neuroconv.datainterfaces.biopotential.basemnecontinuousdatainterface import (  # noqa: E402
    BaseMNEElectricalSeriesInterface,
)
from neuroconv.tools.mne import MNERawDataChunkIterator  # noqa: E402
from neuroconv.tools.testing.mock_interfaces import (  # noqa: E402
    MockMNEElectricalSeriesInterface,
    MockMNETimeSeriesInterface,
)


class OnDiskMNEInterface(BaseMNEElectricalSeriesInterface):
    """Reads a ``.fif`` from disk with ``preload=False``, the case the chunk iterator exists for.

    The ``RawArray`` the mocks build is preloaded by construction, so it cannot show that the write
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


# ---------------------------------------------------------------------------------------------
# Scoping to one channel type
# ---------------------------------------------------------------------------------------------


def test_interface_writes_only_its_own_channel_type():
    """A Raw of mixed kinds yields only this interface's channels, in the source's own order."""
    interface = MockMNEElectricalSeriesInterface(num_channels=4, ch_types=["eeg", "eog", "eeg", "stim"])

    nwbfile = interface.create_nwbfile()

    assert interface.channel_indices == [0, 2]
    electrical_series = nwbfile.acquisition["ElectricalSeries"]
    assert electrical_series.data.shape[1] == 2
    assert len(nwbfile.electrodes) == 2
    # Only this interface's channels reach the file; the eog and stim ones are another interface's.
    assert set(nwbfile.acquisition) == {"ElectricalSeries"}
    np.testing.assert_allclose(electrical_series.data[:], interface.raw.get_data()[[0, 2]].T)


def test_channel_type_absent_from_the_raw_raises():
    with pytest.raises(ValueError, match="channel_type 'ecog' was not found in the Raw"):
        MockMNEElectricalSeriesInterface(num_channels=2, ch_types=["eeg", "eog"], channel_type="ecog")


def test_get_channel_types_reports_what_the_raw_holds():
    """Discovery: which interfaces a file needs is answerable before writing any of them."""
    interface = MockMNEElectricalSeriesInterface(num_channels=3, ch_types=["eeg", "eog", "stim"])

    assert interface.get_channel_types() == {"eeg", "eog", "stim"}


# ---------------------------------------------------------------------------------------------
# The ElectricalSeries destination
# ---------------------------------------------------------------------------------------------


def test_electrical_series_written_and_data_round_trips():
    interface = MockMNEElectricalSeriesInterface(num_channels=6, sampling_frequency=250.0, duration=2.0)
    nwbfile = interface.create_nwbfile()

    electrical_series = nwbfile.acquisition["ElectricalSeries"]

    # MNE Raw is (n_channels, n_times); the ElectricalSeries stores (n_times, n_channels).
    np.testing.assert_allclose(electrical_series.data[:], interface.raw.get_data().T)
    assert electrical_series.data.shape == (500, 6)

    # Regularly sampled from sfreq, no alignment, MNE already in volts.
    assert electrical_series.rate == 250.0
    assert electrical_series.starting_time == 0.0
    assert electrical_series.conversion == 1.0


def test_electrodes_table_has_channel_names_and_no_geometry():
    interface = MockMNEElectricalSeriesInterface(num_channels=4)
    nwbfile = interface.create_nwbfile()

    electrodes = nwbfile.electrodes
    assert len(electrodes) == 4
    assert "channel_name" in electrodes.colnames
    assert list(electrodes["channel_name"][:]) == interface.raw.ch_names

    # v1 writes no coordinates.
    for coordinate_column in ("x", "y", "z", "rel_x", "rel_y", "rel_z"):
        assert coordinate_column not in electrodes.colnames


def test_write_electrical_series_false_writes_only_electrodes():
    interface = MockMNEElectricalSeriesInterface(num_channels=4)
    nwbfile = interface.create_nwbfile(write_electrical_series=False)

    assert len(nwbfile.acquisition) == 0
    assert len(nwbfile.electrodes) == 4


def test_round_trip_through_disk(tmp_path):
    interface = MockMNEElectricalSeriesInterface(num_channels=5, sampling_frequency=100.0, duration=1.0)
    nwbfile_path = tmp_path / "mne_continuous.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    with NWBHDF5IO(path=str(nwbfile_path), mode="r") as io:
        read_nwbfile = io.read()
        read_series = read_nwbfile.acquisition["ElectricalSeries"]
        np.testing.assert_allclose(read_series.data[:], interface.raw.get_data().T)
        assert read_series.rate == 100.0
        assert list(read_nwbfile.electrodes["channel_name"][:]) == interface.raw.ch_names


# ---------------------------------------------------------------------------------------------
# The TimeSeries destination
# ---------------------------------------------------------------------------------------------


def test_time_series_written_with_no_electrodes_table():
    """The TimeSeries destination backs its data with nothing: no electrodes, no group, no device."""
    interface = MockMNETimeSeriesInterface(num_channels=3, ch_types=["eeg", "eog", "eog"], channel_type="eog")

    nwbfile = interface.create_nwbfile()

    time_series = nwbfile.acquisition["TimeSeriesEOG"]
    assert time_series.data.shape == (1000, 2)
    np.testing.assert_allclose(time_series.data[:], interface.raw.get_data()[[1, 2]].T)
    assert nwbfile.electrodes is None
    assert len(nwbfile.devices) == 0


@pytest.mark.parametrize(
    "channel_type,expected_unit",
    [
        ("eog", "volts"),
        ("stim", "volts"),  # MNE labels trigger lines volts; the type, not the unit, scopes an interface
        ("mag", "teslas"),
        ("grad", "teslas/meter"),  # gradiometers are not in teslas
        ("misc", "n.a."),  # MNE declares this one unitless; NWB still requires a string
    ],
)
def test_time_series_unit_is_read_from_the_channel_type(channel_type, expected_unit):
    interface = MockMNETimeSeriesInterface(num_channels=1, ch_types=[channel_type], channel_type=channel_type)

    nwbfile = interface.create_nwbfile()

    assert nwbfile.acquisition[f"TimeSeries{channel_type.upper()}"].unit == expected_unit


def test_interfaces_compose_into_one_file():
    """Several interfaces over the same Raw cover it between them, which is how a whole file is written."""
    channel_types = ["eeg", "eog", "stim"]
    kwargs = dict(num_channels=3, ch_types=channel_types)
    electrical_series_interface = MockMNEElectricalSeriesInterface(**kwargs)
    eog_interface = MockMNETimeSeriesInterface(**kwargs, channel_type="eog")
    stim_interface = MockMNETimeSeriesInterface(**kwargs, channel_type="stim")

    nwbfile = electrical_series_interface.create_nwbfile()
    eog_interface.add_to_nwbfile(nwbfile=nwbfile)
    stim_interface.add_to_nwbfile(nwbfile=nwbfile)

    assert set(nwbfile.acquisition) == {"ElectricalSeries", "TimeSeriesEOG", "TimeSeriesSTIM"}
    total_written = sum(series.data.shape[1] for series in nwbfile.acquisition.values())
    assert total_written == len(channel_types)
    # Only the eeg channel is an electrode.
    assert len(nwbfile.electrodes) == 1


def test_each_interface_addresses_its_own_metadata_entry():
    """One interface, one key, one object: the default key names the channel type it is scoped to."""
    kwargs = dict(num_channels=2, ch_types=["eeg", "eog"])
    electrical_series_interface = MockMNEElectricalSeriesInterface(**kwargs)
    eog_interface = MockMNETimeSeriesInterface(**kwargs, channel_type="eog")

    assert electrical_series_interface.metadata_key == "mne_eeg"
    assert eog_interface.metadata_key == "mne_eog"
    assert list(electrical_series_interface.get_metadata()["Ecephys"]["ElectricalSeries"]) == ["mne_eeg"]
    assert list(eog_interface.get_metadata()["TimeSeries"]) == ["mne_eog"]


# ---------------------------------------------------------------------------------------------
# Streaming, shared by both destinations
# ---------------------------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------------------------
# Sampling rate faithfulness
# ---------------------------------------------------------------------------------------------


def test_mixed_native_sampling_rates_are_refused():
    """MNE upsamples slower channels to the fastest, so writing that Raw would store invented samples.

    The source's own rates survive only on the reader's private extras, so the guard reads those. The
    shape here is what `read_raw_edf` produces for channels at 256, 256 and 32 samples per record,
    where the trailing 57 is the EDF+ annotation signal that `sel` drops.
    """
    interface = MockMNEElectricalSeriesInterface(num_channels=3, ch_types=["eeg", "eeg", "eeg"])
    interface.raw._raw_extras = [{"n_samps": [256, 256, 32, 57], "sel": [0, 1, 2]}]

    with pytest.raises(ValueError, match="different sampling rates") as excinfo:
        interface._validate_homogeneous_sampling_rate()

    # Both native rates are named, scaled off the sfreq MNE settled on, and so is the way out.
    assert "125 Hz" in str(excinfo.value)
    assert "1000 Hz" in str(excinfo.value)
    assert "exclude" in str(excinfo.value)


def test_homogeneous_native_sampling_rates_pass():
    """A single-rate source is the case with nothing to check, and it must not trip the guard."""
    interface = MockMNEElectricalSeriesInterface(num_channels=2)
    interface.raw._raw_extras = [{"n_samps": [256, 256, 57], "sel": [0, 1]}]

    interface._validate_homogeneous_sampling_rate()


def test_readers_without_a_samples_per_record_vector_are_left_alone():
    """A RawArray exposes no native-rate information; the guard skips rather than guessing."""
    interface = MockMNEElectricalSeriesInterface(num_channels=2)

    interface._validate_homogeneous_sampling_rate()
