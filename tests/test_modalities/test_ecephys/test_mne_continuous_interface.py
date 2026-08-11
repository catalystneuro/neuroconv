"""Tests for BaseMNEContinuousDataInterface via the synthetic MockMNEContinuousDataInterface.

These exercise the base's ``mne.io.BaseRaw`` -> ElectricalSeries + electrodes-table write path
with no data on disk. Scope mirrors v1: voltage channels only, no electrode geometry, no
temporal alignment.
"""

import numpy as np
import pytest
from pynwb import NWBHDF5IO

pytest.importorskip("mne")

from neuroconv.tools.testing.mock_interfaces import (  # noqa: E402
    MockMNEContinuousDataInterface,
)


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
