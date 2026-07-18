import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import TDTEventsInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

TDT_DATA_PATH = ECEPHY_DATA_PATH / "tdt"


def test_exclude_events():
    # exclude_events drops the named event types from the discovered set.
    folder_path = TDT_DATA_PATH / "epocs_with_offsets_1"
    interface = TDTEventsInterface(folder_path=folder_path, exclude_events=["Tick", "s4s_", "sms_"])
    event_types = interface.get_metadata()["Events"]["tdt_events"]["event_types"]
    assert set(event_types) == {"s1s_"}


class TDTEventsInterfaceMixin:
    """Builds ``self.interface`` from ``data_interface_cls`` and ``interface_kwargs`` set on the subclass."""

    data_interface_cls = TDTEventsInterface

    @pytest.fixture
    def interface(self):
        return self.data_interface_cls(**self.interface_kwargs)


class TestTimestampOnlyEventType(TDTEventsInterfaceMixin):
    """A timestamp-only event type: ``Tick`` in the durations dataset, with the event types that have
    durations excluded so only the timestamp-only one remains."""

    interface_kwargs = dict(
        folder_path=TDT_DATA_PATH / "epocs_with_offsets_1",
        exclude_events=["s1s_", "s4s_", "sms_"],
    )

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
        assert tick_events.colnames == ("timestamp",)
        assert len(tick_events) == 235


class TestEventTypeWithValueColumn(TDTEventsInterfaceMixin):
    """An event type carrying a categorical value column: ``PAB_`` in the payload dataset, 30 events
    whose codes cycle [16, 2064, 0]."""

    interface_kwargs = dict(folder_path=TDT_DATA_PATH / "epocs_with_payload")

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
        assert len(pab_events) == 30
        # The 30 events cycle through the three codes.
        assert list(pab_events["strobe"][:]) == ["16", "2064", "0"] * 10


class TestEventTypeWithDurations(TDTEventsInterfaceMixin):
    """Event types whose events have durations: ``s1s_``/``s4s_``/``sms_`` in the durations dataset,
    written as a per-event duration in the table's ``duration`` column."""

    interface_kwargs = dict(
        folder_path=TDT_DATA_PATH / "epocs_with_offsets_1",
        exclude_events=["Tick"],
    )

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
        s1s_table = nwbfile.get_events_table("S1s")
        assert s1s_table.colnames == ("timestamp", "duration")
        assert np.allclose(s1s_table["timestamp"][:], [54.629499, 90.678067, 126.729257, 162.823700, 198.878167])
        assert np.allclose(s1s_table["duration"][:], [0.999424, 1.000735, 1.000079, 0.999588, 0.999916])

        s4s_table = nwbfile.get_events_table("S4s")
        assert s4s_table.colnames == ("timestamp", "duration")
        assert np.allclose(s4s_table["timestamp"][:], [65.629389, 101.679104, 137.778299, 173.828997, 209.928192])
        assert np.allclose(s4s_table["duration"][:], [4.000973, 4.000973, 3.999826, 3.999171, 4.000317])

        sms_table = nwbfile.get_events_table("Sms")
        assert sms_table.colnames == ("timestamp", "duration")
        assert np.allclose(sms_table["timestamp"][:], [43.580621, 79.629517, 115.678577, 151.778591, 187.858944])
        assert np.allclose(sms_table["duration"][:], [0.251003, 0.249692, 0.249856, 0.249856, 0.250348])
