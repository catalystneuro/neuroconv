import numpy as np
import pytest
from pynwb.event import EventsTable
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import TDTEventsInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

TDT_DATA_PATH = ECEPHY_DATA_PATH / "tdt"


def test_exclude_events():
    # exclude_events drops the named event types from the discovered set.
    folder_path = str(TDT_DATA_PATH / "epocs_with_offsets_1")
    interface = TDTEventsInterface(folder_path=folder_path, exclude_events=["Tick", "s4s_", "sms_"])
    event_types = interface.get_metadata()["Events"]["tdt_events"]["event_types"]
    assert set(event_types) == {"s1s_"}


class TestTimestampOnlyEventType:
    """A timestamp-only event type: ``Tick`` in the durations dataset, with the event types that have
    durations excluded so only the timestamp-only one remains."""

    folder_path = str(TDT_DATA_PATH / "epocs_with_offsets_1")
    exclude_events = ["s1s_", "s4s_", "sms_"]

    @pytest.fixture
    def interface(self):
        return TDTEventsInterface(folder_path=self.folder_path, exclude_events=self.exclude_events)

    def test_get_metadata(self, interface):
        expected_metadata = {
            "tdt_events": {
                "event_types": {
                    "Tick": {
                        "event_name": "Tick",
                        "event_description": "Onset times of the TDT epoc 'Tick'.",
                    },
                },
            },
        }
        assert interface.get_metadata()["Events"] == expected_metadata

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        tick_events = nwbfile.get_events_table("Tick")  # "Tick" has no underscore, so it stays verbatim
        assert isinstance(tick_events, EventsTable)
        assert tick_events.colnames == ("timestamp",)
        assert len(tick_events) == 235


class TestEventTypeWithValueColumn:
    """An event type carrying a categorical value column: ``PAB_`` in the payload dataset, 30 events
    whose codes cycle [16, 2064, 0]."""

    folder_path = str(TDT_DATA_PATH / "epocs_with_payload")

    @pytest.fixture
    def interface(self):
        return TDTEventsInterface(folder_path=self.folder_path)

    def test_get_metadata(self, interface):
        expected_metadata = {
            "tdt_events": {
                "event_types": {
                    "PAB_": {
                        "event_name": "PAB_",
                        "event_description": "Onset times of the TDT epoc 'PAB_', labeled by strobe value.",
                        "columns": {
                            "strobe": {
                                "column_name": "strobe",
                                "description": "Strobe code for each 'PAB_' event.",
                                "column_categories": {"labels": {0: "0", 16: "16", 2064: "2064"}},
                            },
                        },
                    },
                },
            },
        }
        assert interface.get_metadata()["Events"] == expected_metadata

    def test_add_to_nwbfile(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        pab_events = nwbfile.get_events_table("PAB")  # "PAB_", trailing padding "_" dropped
        assert isinstance(pab_events, EventsTable)
        assert len(pab_events) == 30
        # The 30 events cycle through the three codes.
        assert list(pab_events["strobe"][:]) == ["16", "2064", "0"] * 10


class TestEventTypeWithDurations:
    """Event types whose events have durations: ``s1s_``/``s4s_``/``sms_`` in the durations dataset,
    written as a per-event duration in the table's ``duration`` column."""

    folder_path = str(TDT_DATA_PATH / "epocs_with_offsets_1")

    @pytest.fixture
    def interface(self):
        return TDTEventsInterface(folder_path=self.folder_path, exclude_events=["Tick"])

    def test_get_metadata(self, interface):
        expected_metadata = {
            "tdt_events": {
                "event_types": {
                    "s1s_": {"event_name": "s1s_", "event_description": "Onset times of the TDT epoc 's1s_'."},
                    "s4s_": {"event_name": "s4s_", "event_description": "Onset times of the TDT epoc 's4s_'."},
                    "sms_": {"event_name": "sms_", "event_description": "Onset times of the TDT epoc 'sms_'."},
                },
            },
        }
        assert interface.get_metadata()["Events"] == expected_metadata

    def test_add_to_nwbfile(self, interface):
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
