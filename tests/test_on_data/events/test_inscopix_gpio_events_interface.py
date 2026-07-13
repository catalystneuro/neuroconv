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

# ``BNC Sync Output`` is a 0/1 frame clock (9 low->high edges); ``GPIO-2`` is the odor-concentration
# code (amplitudes 128/144/160/224, cut into 4 bands -> 335 band-change events).
EVENTS_CONFIG = {
    "BNC Sync Output": {"reading": "rising"},
    "GPIO-2": {"levels": [136, 152, 192], "field": "concentration"},
}


@pytest.fixture
def interface():
    return InscopixGpioEventsInterface(file_path=GPIO_FILE_PATH, events_config=EVENTS_CONFIG)


def test_requires_events_config():
    # events_config is a required keyword; omitting it is an error (signal-encoded selection is explicit).
    with pytest.raises(ValidationError, match="events_config"):
        InscopixGpioEventsInterface(file_path=GPIO_FILE_PATH)


def test_metadata_schema_is_valid(interface):
    Draft7Validator.check_schema(interface.get_metadata_schema())


def test_session_start_time(interface):
    session_start_time = interface.get_metadata()["NWBFile"]["session_start_time"]
    assert session_start_time == datetime(2025, 2, 27, 11, 25, 28, 935000, tzinfo=timezone.utc)


def test_metadata_seeds_event_types(interface):
    event_types = interface.get_metadata()["Events"]["inscopix_gpio_events"]["event_types"]
    assert set(event_types) == {"BNC Sync Output", "GPIO-2"}
    # The digital line is timestamp-only (no value columns).
    assert event_types["BNC Sync Output"]["event_name"] == "bnc_sync_output"
    assert event_types["BNC Sync Output"]["columns"] == {}
    # The coded line gets one categorical column keyed by its field, labeling the four observed bands.
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
    assert len(table) == 9  # nine low->high edges on the frame clock


def test_coded_line_writes_categorical_column(interface):
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    table = nwbfile.get_events_table("Gpio2")
    assert table.colnames == ("timestamp", "concentration")
    assert len(table) == 335  # one event per band change
    assert set(table["concentration"].data) == {"0", "1", "2", "3"}


def test_unknown_channel_raises():
    interface = InscopixGpioEventsInterface(
        file_path=GPIO_FILE_PATH, events_config={"NotAChannel": {"reading": "rising"}}
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
        assert len(read_nwbfile.get_events_table("Gpio2")) == 335
        assert len(read_nwbfile.get_events_table("BncSyncOutput")) == 9
