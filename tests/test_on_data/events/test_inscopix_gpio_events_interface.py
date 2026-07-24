from datetime import datetime, timezone

import pytest
from jsonschema.validators import Draft7Validator
from pydantic import ValidationError
from pynwb import NWBHDF5IO
from pynwb.event import EventsTable
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import InscopixGpioEventsInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH

GPIO_FILE_PATH = str(OPHYS_DATA_PATH / "analog_datasets" / "inscopix" / "gpio" / "odor_concentration_stimulus.gpio")

# ``BNC Sync Output`` is a 0/1 frame clock (9 rising edges); ``GPIO-2`` is the odor-concentration code
# (amplitudes 128/144/160/224, cut into four bands -> 334 band-change events).
EVENTS_CONFIG = {
    "BNC Sync Output": {"detect": "rising"},
    "GPIO-2": {"levels": [136, 152, 192], "field": "concentration"},
}


@pytest.fixture
def interface():
    return InscopixGpioEventsInterface(file_path=GPIO_FILE_PATH, events_config=EVENTS_CONFIG)


def test_requires_events_config():
    # events_config is a required keyword; omitting it is an error (selection is explicit).
    with pytest.raises(ValidationError, match="events_config"):
        InscopixGpioEventsInterface(file_path=GPIO_FILE_PATH)


def test_get_available_channels():
    inventory = InscopixGpioEventsInterface.get_available_channels(GPIO_FILE_PATH)
    by_name = {entry["name"]: entry for entry in inventory}
    assert by_name["BNC Sync Output"]["unique_values"] == [0.0, 1.0]  # a 0/1 line


def test_metadata_schema_is_valid(interface):
    Draft7Validator.check_schema(interface.get_metadata_schema())


def test_session_start_time(interface):
    session_start_time = interface.get_metadata()["NWBFile"]["session_start_time"]
    assert session_start_time == datetime(2025, 2, 27, 11, 25, 28, 935000, tzinfo=timezone.utc)


def test_metadata_seeds_event_types(interface):
    event_types = interface.get_metadata()["Events"]["inscopix_gpio_events"]["event_types"]
    assert set(event_types) == {"BNC Sync Output", "GPIO-2"}
    # The digital line read as rising edges is timestamp-only (no value column).
    assert event_types["BNC Sync Output"]["event_name"] == "bnc_sync_output"
    assert event_types["BNC Sync Output"]["columns"] == {}
    # The coded line gets one categorical column labeling the four observed bands.
    concentration = event_types["GPIO-2"]["columns"]["concentration"]
    assert concentration["column_name"] == "concentration"
    assert concentration["column_categories"]["labels"] == {
        0: "0",
        1: "1",
        2: "2",
        3: "3",
    }


def test_metadata_key_default_and_override():
    interface = InscopixGpioEventsInterface(file_path=GPIO_FILE_PATH, events_config=EVENTS_CONFIG)
    assert set(interface.get_metadata()["Events"]) == {"inscopix_gpio_events"}
    interface = InscopixGpioEventsInterface(
        file_path=GPIO_FILE_PATH,
        events_config=EVENTS_CONFIG,
        metadata_key="odor_session",
    )
    assert set(interface.get_metadata()["Events"]) == {"odor_session"}


def test_selection_by_inclusion(interface):
    # Only the two configured channels are written; the other 24 channels never appear.
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    assert set(nwbfile.events) == {"BncSyncOutput", "Gpio2"}


def test_digital_line_is_timestamp_only(interface):
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    table = nwbfile.get_events_table("BncSyncOutput")
    assert isinstance(table, EventsTable)
    assert table.colnames == ("timestamp",)
    assert len(table) == 9  # nine rising edges on the frame clock


def test_coded_line_writes_categorical_column(interface):
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    table = nwbfile.get_events_table("Gpio2")
    assert table.colnames == ("timestamp", "concentration")
    assert len(table) == 334  # one event per band change (the opening-state sample is not an event)
    assert set(table["concentration"].data) == {"0", "1", "2", "3"}


def test_high_period_reading_writes_durations():
    # A digital line read as high periods carries a duration column.
    interface = InscopixGpioEventsInterface(
        file_path=GPIO_FILE_PATH,
        events_config={"BNC Sync Output": {"detect": "high_period"}},
    )
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    table = nwbfile.get_events_table("BncSyncOutput")
    assert "duration" in table.colnames


def test_unknown_channel_raises():
    interface = InscopixGpioEventsInterface(
        file_path=GPIO_FILE_PATH, events_config={"NotAChannel": {"detect": "rising"}}
    )
    with pytest.raises(ValueError, match="not present in the file"):
        interface.get_metadata()


def test_round_trip(interface, tmp_path):
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    nwbfile_path = tmp_path / "test_inscopix_gpio_events.nwb"
    with NWBHDF5IO(nwbfile_path, mode="w") as io:
        io.write(nwbfile)
    with NWBHDF5IO(nwbfile_path, mode="r") as io:
        read_nwbfile = io.read()
        assert len(read_nwbfile.get_events_table("Gpio2")) == 334
        assert len(read_nwbfile.get_events_table("BncSyncOutput")) == 9
