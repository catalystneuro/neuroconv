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

# The eight analog/monitor channels present (and non-empty) in the fixture, and their default units.
EXPECTED_UNITS = {
    "GPIO-1": "a.u.",
    "GPIO-2": "a.u.",
    "GPIO-3": "a.u.",
    "GPIO-4": "a.u.",
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


def test_writes_analog_channels_with_units(interface):
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)
    assert set(nwbfile.acquisition) == set(EXPECTED_UNITS)
    for name, unit in EXPECTED_UNITS.items():
        time_series = nwbfile.acquisition[name]
        assert isinstance(time_series, TimeSeries)
        assert time_series.unit == unit
        # Irregular sampling: explicit per-event timestamps, not a fixed rate.
        assert time_series.timestamps is not None
        assert time_series.rate is None


def test_digital_and_bnc_channels_excluded(interface):
    # The digital lines and BNC sync/trigger channels are events, not analog; they are never written here.
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)
    written = set(nwbfile.acquisition)
    assert not any(name.startswith("Digital ") or name.startswith("BNC ") for name in written)


def test_channel_units_and_conversion_override(interface):
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(
        nwbfile=nwbfile,
        channel_units={"GPIO-1": "volts"},
        channel_conversion={"GPIO-1": 2.5},
    )
    assert nwbfile.acquisition["GPIO-1"].unit == "volts"
    assert nwbfile.acquisition["GPIO-1"].conversion == 2.5
    # An un-overridden monitor channel keeps its default unit and conversion.
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
