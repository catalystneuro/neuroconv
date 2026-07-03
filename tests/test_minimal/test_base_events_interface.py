"""Data-free tests of the shared events writer, driven by ``MockEventsInterface``."""

import re

import pytest
from jsonschema.validators import Draft7Validator
from pynwb.event import EventsTable
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.testing.mock_interfaces import MockEventsInterface


class TestMockEventsInterface:
    def test_get_metadata(self):
        interface = MockEventsInterface()
        Draft7Validator.check_schema(interface.get_metadata_schema())

        # The Events block nests event_types under the metadata_key, with the global EventTables
        # alongside it. metadata_key defaults to "mock_events" and is overridable.
        events_metadata = interface.get_metadata()["Events"]
        assert set(events_metadata.keys()) == {"mock_events", "EventTables"}
        assert set(events_metadata["mock_events"]["event_types"].keys()) == {"events"}

        overridden = MockEventsInterface(metadata_key="my_events").get_metadata()["Events"]
        assert set(overridden.keys()) == {"my_events", "EventTables"}

    def test_events_with_timestamps_only(self):
        interface = MockEventsInterface(event_payload="timestamps only")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        events = nwbfile.get_events_table("Events")
        assert events.colnames == ("timestamp",)
        assert len(events) == 4

    def test_events_single_value(self):
        # A point event type carrying one categorical value.
        interface = MockEventsInterface(event_payload="single value")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        events = nwbfile.get_events_table("Events")
        assert isinstance(events, EventsTable)
        assert events.colnames == ("timestamp", "outcome")
        assert len(events) == 4
        # The payload codes [0, 1, 0, 1] map through column_categories["labels"].
        assert list(events["outcome"][:]) == ["go", "no_go", "go", "no_go"]

    def test_events_multi_value_payload(self):
        # A struct payload fans each field into its own column, on the same rows: 'outcome' is
        # categorical (display labels) and 'amplitude' is numeric (raw values, no MeaningsTable).
        interface = MockEventsInterface(num_events=3, event_payload="multi value")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        events = nwbfile.get_events_table("Events")
        assert set(events.colnames) == {"timestamp", "outcome", "amplitude"}
        assert list(events["outcome"][:]) == ["go", "no_go", "go"]
        assert list(events["amplitude"][:]) == [0.0, 1.0, 2.0]

    def test_events_with_duration(self):
        # An event-with-duration type carries per-event durations, so the writer adds a `duration` column.
        interface = MockEventsInterface(
            num_events=3,
            event_extent="event with duration",
            event_payload="single value",
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        events = nwbfile.get_events_table("Events")
        assert set(events.colnames) == {"timestamp", "duration", "outcome"}
        assert list(events["duration"][:]) == [0.05, 0.05, 0.05]

    def test_metadata_customization(self):
        # The user-facing overrides all take effect from one explicit metadata dict: the table is
        # renamed, both columns are renamed, one column is categorical (a relabelled value plus
        # meanings) while the other stays numeric. Renaming never breaks the write because the value
        # is keyed on the field (the columns key), not on the output column_name; and labels/meanings
        # are both keyed by the raw value, so relabelling a value does not orphan its meaning.
        interface = MockEventsInterface(num_events=2, event_payload="multi value")
        metadata = {
            "Events": {
                "EventTables": {"events": {"table_name": "Choices", "description": "Trial choices."}},
                "mock_events": {
                    "event_types": {
                        "events": {
                            "table_metadata_key": "events",
                            "columns": {
                                "outcome": {
                                    "column_name": "choice",
                                    "column_categories": {
                                        "labels": {0: "GO", 1: "no_go"},
                                        "meanings": {
                                            0: "A go outcome.",
                                            1: "A no-go outcome.",
                                        },
                                    },
                                },
                                "amplitude": {"column_name": "signal"},
                            },
                        }
                    }
                },
            }
        }
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # The table is retrievable by its renamed name, with both columns under their new names.
        events = nwbfile.get_events_table("Choices")
        assert set(events.colnames) == {"timestamp", "choice", "signal"}
        # Categorical column: the relabelled value ("GO") and the kept one ("no_go").
        assert list(events["choice"][:]) == ["GO", "no_go"]
        # Numeric column (no categories): raw values pass through under the renamed name.
        assert list(events["signal"][:]) == [0.0, 1.0]
        # The meaning follows the relabelled value (keyed by the raw value, not the label text).
        meanings_table = events.meanings_tables["choice_meanings"]
        value_to_meaning = dict(zip(meanings_table["value"][:], meanings_table["meaning"][:]))
        assert value_to_meaning["GO"] == "A go outcome."

    def test_declaring_a_column_for_a_missing_payload_field_errors(self):
        # A columns entry whose field_source_id is absent from the data payload is a mismatch and must
        # fail with a clear message.
        interface = MockEventsInterface(event_payload="timestamps only")
        metadata = interface.get_metadata()
        metadata["Events"]["mock_events"]["event_types"]["events"]["columns"]["ghost"] = {"column_name": "ghost"}
        expected_error = "Event type 'events' declares a column for payload field 'ghost', but its payload has no such field (has [])."
        with pytest.raises(AssertionError, match=re.escape(expected_error)):
            interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)

    def test_merge_event_types_in_single_table(self):
        # Both event types route to one table (shared table_metadata_key "events_0"), so the writer
        # pools them into a single time-sorted table with an event_type discriminator column. Each
        # type carries a categorical column (outcome) and a numeric one (amplitude), so both fill
        # kinds are exercised on the rows a column does not own.
        interface = MockEventsInterface(num_event_types=2, num_events=2, event_payload="multi value")
        metadata = {
            "Events": {
                "EventTables": {"events_0": {"table_name": "Events0", "description": "Mock events."}},
                "mock_events": {
                    "event_types": {
                        "events_0": {
                            "table_metadata_key": "events_0",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome_0",
                                    "column_categories": {"labels": {0: "go", 1: "no_go"}},
                                },
                                "amplitude": {"column_name": "amplitude_0"},
                            },
                        },
                        "events_1": {
                            "table_metadata_key": "events_0",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome_1",
                                    "column_categories": {"labels": {0: "go", 1: "no_go"}},
                                },
                                "amplitude": {"column_name": "amplitude_1"},
                            },
                        },
                    }
                },
            }
        }
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        events = nwbfile.get_events_table("Events0")
        assert set(events.colnames) == {
            "timestamp",
            "event_type",
            "outcome_0",
            "outcome_1",
            "amplitude_0",
            "amplitude_1",
        }
        assert len(events) == 4
        # Timestamps are staggered per type, so the pooled table is time-sorted and interleaved;
        # event_type names each row's type.
        assert list(events["timestamp"][:]) == pytest.approx([0.1, 0.2, 0.3, 0.4])
        assert list(events["event_type"][:]) == [
            "events_0",
            "events_1",
            "events_0",
            "events_1",
        ]
        # Each type's columns are filled only on its own rows. On the other type's rows a categorical
        # column fills "" and a numeric column fills NaN.
        assert list(events["outcome_0"][:]) == ["go", "", "no_go", ""]
        assert list(events["outcome_1"][:]) == ["", "go", "", "no_go"]
        assert list(events["amplitude_0"][:]) == pytest.approx([0.0, float("nan"), 1.0, float("nan")], nan_ok=True)
        assert list(events["amplitude_1"][:]) == pytest.approx([float("nan"), 0.0, float("nan"), 1.0], nan_ok=True)

    def test_merge_event_types_with_only_timestamps(self):
        # Pool two value-less types (empty columns) into one table: without event_type their rows
        # would be indistinguishable.
        interface = MockEventsInterface(num_event_types=2, num_events=2, event_payload="timestamps only")
        metadata = {
            "Events": {
                "EventTables": {"events_0": {"table_name": "Events0", "description": "Mock events."}},
                "mock_events": {
                    "event_types": {
                        "events_0": {"table_metadata_key": "events_0", "columns": {}},
                        "events_1": {"table_metadata_key": "events_0", "columns": {}},
                    }
                },
            }
        }
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        events = nwbfile.get_events_table("Events0")
        assert set(events.colnames) == {"timestamp", "event_type"}
        # Both types' rows survive the pool: 2 events x 2 types, none dropped or duplicated.
        assert len(events) == 4
        # Staggered timestamps interleave the two types; event_type is the only thing telling
        # otherwise-identical (value-less) rows apart.
        assert list(events["timestamp"][:]) == pytest.approx([0.1, 0.2, 0.3, 0.4])
        assert list(events["event_type"][:]) == [
            "events_0",
            "events_1",
            "events_0",
            "events_1",
        ]

    def test_duplicate_column_name_in_merge_raises(self):
        # Two event types writing the same column_name ("outcome_0") into one table is a collision,
        # not a shared column; it must raise rather than silently pool two streams into one column.
        interface = MockEventsInterface(num_event_types=2, event_payload="single value")
        metadata = {
            "Events": {
                "EventTables": {"events_0": {"table_name": "Events0", "description": "Mock events."}},
                "mock_events": {
                    "event_types": {
                        "events_0": {
                            "table_metadata_key": "events_0",
                            "columns": {"outcome": {"column_name": "outcome_0"}},
                        },
                        "events_1": {
                            "table_metadata_key": "events_0",
                            "columns": {"outcome": {"column_name": "outcome_0"}},
                        },
                    }
                },
            }
        }
        expected_error = "Two event columns write the same column_name 'outcome_0' into table 'events_0'. Give each event column a unique column_name."
        with pytest.raises(AssertionError, match=re.escape(expected_error)):
            interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)

    def test_duplicate_table_name_raises(self):
        # Two event types on distinct tables (distinct table_metadata_key) that declare the same
        # table_name would collide as NWB objects; the writer rejects it up front with a clear message
        # rather than letting pynwb fail obscurely at add_events_table.
        interface = MockEventsInterface(num_event_types=2, event_payload="timestamps only")
        metadata = {
            "Events": {
                "EventTables": {
                    "events_0": {"table_name": "Events", "description": "Mock events."},
                    "events_1": {"table_name": "Events", "description": "Mock events."},
                },
                "mock_events": {
                    "event_types": {
                        "events_0": {"table_metadata_key": "events_0", "columns": {}},
                        "events_1": {"table_metadata_key": "events_1", "columns": {}},
                    }
                },
            }
        }
        expected_error = "Duplicate EventTables 'table_name' values found in metadata: {'Events': ['events_0', 'events_1']}. Each EventsTable must have a unique name; give these table_metadata_key entries distinct table_name values."
        with pytest.raises(AssertionError, match=re.escape(expected_error)):
            interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)
