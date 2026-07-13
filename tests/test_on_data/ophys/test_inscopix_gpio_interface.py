from datetime import datetime, timezone

import pytest
from pynwb import NWBHDF5IO, TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import InscopixGpioInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH

GPIO_FILE_PATH = str(OPHYS_DATA_PATH / "analog_datasets" / "inscopix" / "gpio" / "odor_concentration_stimulus.gpio")

# Monitor channels have known units; everything else defaults to "a.u.".
MONITOR_UNITS = {
    "EX-LED": "mW/mm^2",
    "OG-LED": "mW/mm^2",
    "DI-LED": "mW/mm^2",
    "e-focus": "micrometers",
}


@pytest.fixture
def interface():
    return InscopixGpioInterface(file_path=GPIO_FILE_PATH)


def test_session_start_time(interface):
    session_start_time = interface.get_metadata()["NWBFile"]["session_start_time"]
    assert session_start_time == datetime(2025, 2, 27, 11, 25, 28, 935000, tzinfo=timezone.utc)


def test_get_available_channels():
    inventory = InscopixGpioInterface.get_available_channels(GPIO_FILE_PATH)
    assert len(inventory) == 26
    by_name = {entry["name"]: entry for entry in inventory}
    # GPIO-2 is the odor code: 336 samples spanning four levels.
    assert by_name["GPIO-2"]["num_samples"] == 336
    assert by_name["GPIO-2"]["unique_values"] == [128.0, 144.0, 160.0, 224.0]


def test_writes_all_channels_by_default(interface):
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)
    # Every one of the 26 channels is written as a TimeSeries (digital and BNC lines included).
    assert len(nwbfile.acquisition) == 26
    assert "BNC_Sync_Output" in nwbfile.acquisition
    assert "Digital_GPI_0" in nwbfile.acquisition
    for name, unit in MONITOR_UNITS.items():
        time_series = nwbfile.acquisition[name]
        assert isinstance(time_series, TimeSeries)
        assert time_series.unit == unit
        # Irregular sampling: explicit per-event timestamps, not a fixed rate.
        assert time_series.timestamps is not None
        assert time_series.rate is None
    # A general-purpose GPIO input has no known unit.
    assert nwbfile.acquisition["GPIO-1"].unit == "a.u."


def test_exclude_channels(interface):
    nwbfile = mock_NWBFile()
    InscopixGpioInterface(
        file_path=GPIO_FILE_PATH, exclude_channels=["BNC Sync Output", "Digital GPI 0"]
    ).add_to_nwbfile(nwbfile=nwbfile)
    assert len(nwbfile.acquisition) == 24
    assert "BNC_Sync_Output" not in nwbfile.acquisition
    assert "Digital_GPI_0" not in nwbfile.acquisition


def test_channel_units_and_conversion_override(interface):
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(
        nwbfile=nwbfile,
        channel_units={"GPIO-1": "volts"},
        channel_conversion={"GPIO-1": 2.5},
    )
    assert nwbfile.acquisition["GPIO-1"].unit == "volts"
    assert nwbfile.acquisition["GPIO-1"].conversion == 2.5
    assert nwbfile.acquisition["e-focus"].unit == "micrometers"
    assert nwbfile.acquisition["e-focus"].conversion == 1.0


def test_stub_test_truncates(interface):
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, stub_test=True)
    # GPIO-1 has 475 samples in full; stub_test writes at most 100.
    assert nwbfile.acquisition["GPIO-1"].data.shape[0] == 100


def test_round_trip(interface, tmp_path):
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)
    nwbfile_path = tmp_path / "test_inscopix_gpio.nwb"
    with NWBHDF5IO(nwbfile_path, mode="w") as io:
        io.write(nwbfile)
    with NWBHDF5IO(nwbfile_path, mode="r") as io:
        read_nwbfile = io.read()
        assert read_nwbfile.acquisition["GPIO-2"].data.shape[0] == 336
        assert read_nwbfile.acquisition["e-focus"].unit == "micrometers"
