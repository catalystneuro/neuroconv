import numpy as np
import pytest
from jsonschema.validators import Draft7Validator
from pynwb import NWBHDF5IO
from pynwb.event import EventsTable
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import TDTEventsInterface
from neuroconv.datainterfaces.events.tdt_events.tdteventsdatainterface import (
    _data_is_counter,
    _offset_is_synthesized,
)

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

TDT_DATA_PATH = ECEPHY_DATA_PATH / "tdt"


class TestDetectors:
    def test_synthesized_offset_is_detected(self):
        onset = np.array([1.0, 2.0, 3.0])
        offset = np.array([2.0, 3.0, np.inf])  # TDT fill: offset[i] == onset[i + 1], last is inf
        assert _offset_is_synthesized(onset, offset)

    def test_real_offset_is_not_synthesized(self):
        onset = np.array([1.0, 2.0, 3.0])
        offset = np.array([1.5, 2.5, 3.5])  # genuine falling edges strictly inside each interval
        assert not _offset_is_synthesized(onset, offset)

    def test_single_event_offset_is_synthesized(self):
        onset = np.array([1.0])
        offset = np.array([np.inf])
        assert _offset_is_synthesized(onset, offset)

    def test_counter_data_is_detected(self):
        assert _data_is_counter(np.array([1.0, 2.0, 3.0, 4.0]))
        assert _data_is_counter(np.array([0.0, 1.0, 2.0]))

    def test_value_codes_are_not_a_counter(self):
        assert not _data_is_counter(np.array([16.0, 2064.0, 0.0, 16.0]))


class TestTimestampOnlyEventType:
    """A timestamp-only event type: ``Tick`` in the durations dataset, with the event types that have
    durations excluded so only the timestamp-only one remains."""

    folder_path = str(TDT_DATA_PATH / "epocs_with_offsets_1")
    exclude_events = ["s1s_", "s4s_", "sms_"]  # the event types whose events have durations

    @pytest.fixture
    def interface(self):
        return TDTEventsInterface(folder_path=self.folder_path, exclude_events=self.exclude_events)

    def test_session_start_time(self, interface):
        # The anonymized dataset has a fixed session start date.
        assert interface.get_metadata()["NWBFile"]["session_start_time"] == "1970-01-12T13:46:40+00:00"

    def test_lists_the_event_type(self, interface):
        event_types = interface.get_metadata()["Events"]["tdt_events"]["event_types"]
        assert set(event_types.keys()) == {"Tick"}
        entry = event_types["Tick"]
        assert entry["event_name"] == "Tick"
        assert entry.get("columns", {}) == {}  # a timestamp-only event type has no value columns

    def test_exclude_events(self):
        # Excluding every event type leaves none.
        interface = TDTEventsInterface(folder_path=self.folder_path, exclude_events=self.exclude_events + ["Tick"])
        assert interface.get_metadata()["Events"]["tdt_events"]["event_types"] == {}

    def test_metadata_key_default_and_override(self, interface):
        # No EventTables block is seeded: a solo event type names its own table from event_name, so
        # metadata["Events"] holds only the per-interface metadata_key block.
        assert set(interface.get_metadata()["Events"].keys()) == {"tdt_events"}

        renamed = TDTEventsInterface(
            folder_path=self.folder_path, exclude_events=self.exclude_events, metadata_key="my_recording"
        )
        assert set(renamed.get_metadata()["Events"].keys()) == {"my_recording"}

    def test_metadata_schema_is_valid(self, interface):
        Draft7Validator.check_schema(interface.get_metadata_schema())

    def test_add_to_nwbfile_writes_events(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        tick_events = nwbfile.get_events_table("Tick")  # "Tick" has no underscore, so it stays verbatim
        assert isinstance(tick_events, EventsTable)
        assert tick_events.colnames == ("timestamp",)
        assert len(tick_events) == 235

    def test_round_trip(self, interface, tmp_path):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        nwbfile_path = tmp_path / "test_tdt_events.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_events = io.read().get_events_table("Tick")
            assert isinstance(read_events, EventsTable)
            assert len(read_events) == 235


class TestEventTypeWithValueColumn:
    """An event type carrying a categorical value column: ``PAB_`` in the payload dataset, 30 events
    whose codes cycle [16, 2064, 0]."""

    folder_path = str(TDT_DATA_PATH / "epocs_with_payload")

    @pytest.fixture
    def interface(self):
        return TDTEventsInterface(folder_path=self.folder_path)

    def test_get_events(self, interface):
        events = interface.get_events()
        assert set(events) == {"PAB_"}
        for array in events["PAB_"].values():
            assert len(array) == 30

    def test_metadata_seeds_value_column_labels(self, interface):
        metadata = interface.get_metadata()
        entry = metadata["Events"]["tdt_events"]["event_types"]["PAB_"]
        # The PAB_ event type gets one categorical value column ("strobe", keyed by its payload field);
        # the three distinct codes are seeded as an editable raw-code -> label map.
        value_column = entry["columns"]["strobe"]
        assert value_column["column_categories"]["labels"] == {0: "0", 16: "16", 2064: "2064"}
        assert value_column["column_name"] == "strobe"
        # The event type names its own (solo) table from event_name and carries its description; no
        # EventTables entry is seeded (the writer drops the trailing padding "_", so the table is "PAB").
        assert entry["event_name"] == "PAB_"
        assert entry["event_description"] == "Onset times of the TDT epoc 'PAB_', labeled by strobe value."
        assert "EventTables" not in metadata["Events"]

    def test_add_to_nwbfile_writes_labeled_events(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        pab_events = nwbfile.get_events_table("PAB")  # "PAB_", trailing padding "_" dropped
        assert isinstance(pab_events, EventsTable)
        assert len(pab_events) == 30
        # The 30 events cycle through the three codes.
        assert list(pab_events["strobe"][:]) == ["16", "2064", "0"] * 10

    def test_user_relabeling_round_trip(self, interface, tmp_path):
        metadata = interface.get_metadata()
        labels = metadata["Events"]["tdt_events"]["event_types"]["PAB_"]["columns"]["strobe"]["column_categories"][
            "labels"
        ]
        labels.update({0: "none", 16: "left", 2064: "right"})
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = tmp_path / "test_tdt_value_column.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_events = io.read().get_events_table("PAB")
            assert isinstance(read_events, EventsTable)
            # Codes [16, 2064, 0] map through the user's relabeling.
            assert list(read_events["strobe"][:]) == ["left", "right", "none"] * 10


class TestEventTypeWithDurations:
    """Event types whose events have durations: ``s1s_``/``s4s_``/``sms_`` in the durations dataset,
    written as a per-event duration in the table's ``duration`` column."""

    folder_path = str(TDT_DATA_PATH / "epocs_with_offsets_1")

    @pytest.fixture
    def interface(self):
        return TDTEventsInterface(folder_path=self.folder_path, exclude_events=["Tick"])

    def test_add_to_nwbfile_writes_durations(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        # Each event type becomes a table named from the store (trailing padding "_" dropped, capitalized),
        # carrying a "duration" column of the real per-event durations (~1 s, ~4 s, ~0.25 s).
        for table_name, expected_duration in [("S1s", 1.0), ("S4s", 4.0), ("Sms", 0.25)]:
            table = nwbfile.get_events_table(table_name)
            assert isinstance(table, EventsTable)
            assert table.colnames == ("timestamp", "duration")
            assert len(table) == 5
            assert np.allclose(table["duration"][:], expected_duration, atol=0.01)
