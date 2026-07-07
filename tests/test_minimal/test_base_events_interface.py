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

        # The Events block nests event_types under the metadata_key. No EventTables entry is emitted:
        # a solo type names its own table from its (required) event_name/event_description.
        events_metadata = interface.get_metadata()["Events"]
        assert set(events_metadata.keys()) == {"mock_events"}
        assert set(events_metadata["mock_events"]["event_types"].keys()) == {"events"}
        entry = events_metadata["mock_events"]["event_types"]["events"]
        assert entry["event_name"] == "events"
        assert "event_description" in entry

        overridden = MockEventsInterface(metadata_key="my_events").get_metadata()["Events"]
        assert set(overridden.keys()) == {"my_events"}

    def test_events_with_timestamps_only(self):
        interface = MockEventsInterface(event_payload="timestamps only")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        # The solo type "events" names its table by CamelCasing event_name ("events" -> "Events").
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
        # The user-facing overrides all take effect from one explicit metadata dict: the (solo) table is
        # renamed via event_name (CamelCased), both columns are renamed, one column is categorical (a
        # relabelled value plus meanings) while the other stays numeric. Renaming never breaks the write
        # because the value is keyed on the field (the columns key), not on the output column_name; and
        # labels/meanings are both keyed by the raw value, so relabelling a value does not orphan its meaning.
        interface = MockEventsInterface(num_events=2, event_payload="multi value")
        metadata = {
            "Events": {
                "mock_events": {
                    "event_types": {
                        "events": {
                            "event_name": "choices",
                            "event_description": "Trial choices.",
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

        # The table is retrievable by its renamed name (event_name CamelCased); a solo table has no
        # event_type discriminator, and both columns appear under their new names.
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

    def test_solo_table_name_casing(self):
        # A solo table's object name derives from event_name: a snake_case or all-lowercase name is
        # CamelCased, but a raw source id that already carries casing is kept verbatim rather than mangled
        # (to_camel_case("PtAB") would give "Ptab").
        interface = MockEventsInterface(event_payload="timestamps only")

        snake = interface.get_metadata()
        snake["Events"]["mock_events"]["event_types"]["events"]["event_name"] = "port_entries"
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=snake)
        assert "PortEntries" in nwbfile.events

        verbatim = interface.get_metadata()
        verbatim["Events"]["mock_events"]["event_types"]["events"]["event_name"] = "PtAB"
        other = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=other, metadata=verbatim)
        assert "PtAB" in other.events

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
        # Both event types route to one shared table (shared table_metadata_key + a declared EventTables
        # entry), so the writer pools them into a single time-sorted table with an event_type discriminator
        # column holding each type's event_name. Each type carries a categorical column (outcome) and a
        # numeric one (amplitude), so both fill kinds are exercised on the rows a column does not own.
        interface = MockEventsInterface(num_event_types=2, num_events=2, event_payload="multi value")
        metadata = {
            "Events": {
                "EventTables": {"pooled": {"table_name": "Choices", "description": "Pooled events."}},
                "mock_events": {
                    "event_types": {
                        "events_0": {
                            "event_name": "left",
                            "event_description": "Left-port events.",
                            "table_metadata_key": "pooled",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome_0",
                                    "column_categories": {"labels": {0: "go", 1: "no_go"}},
                                },
                                "amplitude": {"column_name": "amplitude_0"},
                            },
                        },
                        "events_1": {
                            "event_name": "right",
                            "event_description": "Right-port events.",
                            "table_metadata_key": "pooled",
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

        events = nwbfile.get_events_table("Choices")
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
        # event_type names each row's type by its event_name.
        assert list(events["timestamp"][:]) == pytest.approx([0.1, 0.2, 0.3, 0.4])
        assert list(events["event_type"][:]) == ["left", "right", "left", "right"]
        # Each type's columns are filled only on its own rows. On the other type's rows a categorical
        # column fills "" and a numeric column fills NaN.
        assert list(events["outcome_0"][:]) == ["go", "", "no_go", ""]
        assert list(events["outcome_1"][:]) == ["", "go", "", "no_go"]
        assert list(events["amplitude_0"][:]) == pytest.approx([0.0, float("nan"), 1.0, float("nan")], nan_ok=True)
        assert list(events["amplitude_1"][:]) == pytest.approx([float("nan"), 0.0, float("nan"), 1.0], nan_ok=True)
        # The discriminator carries a MeaningsTable mapping each event_name to its event_description.
        event_type_meanings = events.meanings_tables["event_type_meanings"]
        value_to_meaning = dict(zip(event_type_meanings["value"][:], event_type_meanings["meaning"][:]))
        assert value_to_meaning == {"left": "Left-port events.", "right": "Right-port events."}

    def test_merge_event_types_with_only_timestamps(self):
        # Pool two value-less types (empty columns) into one table: without event_type their rows
        # would be indistinguishable.
        interface = MockEventsInterface(num_event_types=2, num_events=2, event_payload="timestamps only")
        metadata = {
            "Events": {
                "EventTables": {"pooled": {"table_name": "Pooled", "description": "Pooled events."}},
                "mock_events": {
                    "event_types": {
                        "events_0": {
                            "event_name": "left",
                            "event_description": "Left events.",
                            "table_metadata_key": "pooled",
                            "columns": {},
                        },
                        "events_1": {
                            "event_name": "right",
                            "event_description": "Right events.",
                            "table_metadata_key": "pooled",
                            "columns": {},
                        },
                    }
                },
            }
        }
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        events = nwbfile.get_events_table("Pooled")
        assert set(events.colnames) == {"timestamp", "event_type"}
        # Both types' rows survive the pool: 2 events x 2 types, none dropped or duplicated.
        assert len(events) == 4
        # Staggered timestamps interleave the two types; event_type is the only thing telling
        # otherwise-identical (value-less) rows apart.
        assert list(events["timestamp"][:]) == pytest.approx([0.1, 0.2, 0.3, 0.4])
        assert list(events["event_type"][:]) == ["left", "right", "left", "right"]

    def test_merged_table_is_time_sorted(self):
        # One interface with two event types. The mock staggers each type's timestamps so the types
        # interleave in time, but each type is generated on its own: "events_0" (-> "left") fires at 0.1
        # and 0.3, "events_1" (-> "right") at 0.2 and 0.4. The payload is timestamps-only, hence the empty
        # "columns": {}.
        interface = MockEventsInterface(num_event_types=2, num_events=2, event_payload="timestamps only")

        # Each type on its own is chronological; the interleaving only appears once they are pooled.
        events_data = interface._get_events_data_dict()
        assert list(events_data["events_0"].timestamps) == pytest.approx([0.1, 0.3])
        assert list(events_data["events_1"].timestamps) == pytest.approx([0.2, 0.4])
        assert events_data["events_0"].payload == {}  # timestamps-only -> no value columns

        metadata = {
            "Events": {
                "EventTables": {"pooled": {"table_name": "Pooled", "description": "Pooled events."}},
                "mock_events": {
                    "event_types": {
                        "events_0": {
                            "event_name": "left",
                            "event_description": "Left events.",
                            "table_metadata_key": "pooled",
                        },
                        "events_1": {
                            "event_name": "right",
                            "event_description": "Right events.",
                            "table_metadata_key": "pooled",
                        },
                    }
                },
            }
        }
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        events = nwbfile.get_events_table("Pooled")
        timestamps = list(events["timestamp"][:])
        # The two types are appended as blocks, so the pre-sort order is [0.1, 0.3, 0.2, 0.4]; the
        # end-of-write re-sort interleaves them into a single chronological timeline.
        assert timestamps == pytest.approx([0.1, 0.2, 0.3, 0.4])
        # Each row survived the sort as a unit: event_type still pairs "left" with 0.1/0.3 and "right"
        # with 0.2/0.4 (a sort that moved only the timestamp column would break this).
        assert list(events["event_type"][:]) == ["left", "right", "left", "right"]

    def test_merge_across_two_interfaces(self):
        # Two separate interface instances (distinct metadata_key) route their single type into one shared
        # table via the same table_metadata_key and a declared EventTables entry. The second interface
        # appends to the table the first wrote: its column is backfilled on the existing rows, the existing
        # column is filled on its own rows, the discriminator's MeaningsTable is extended, and the pooled
        # table is re-sorted so it is globally time-ordered regardless of which interface ran first.
        metadata_key_a = "events_a"
        metadata_key_b = "events_b"
        interface_a = MockEventsInterface(metadata_key=metadata_key_a, num_events=2, event_payload="single value")
        interface_b = MockEventsInterface(metadata_key=metadata_key_b, num_events=2, event_payload="single value")
        metadata = {
            "Events": {
                "EventTables": {"shared": {"table_name": "Trials", "description": "Trials from two systems."}},
                metadata_key_a: {
                    "event_types": {
                        "events": {
                            "event_name": "acquisition",
                            "event_description": "From the acquisition system.",
                            "table_metadata_key": "shared",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome_a",
                                    "column_categories": {"labels": {0: "go", 1: "no_go"}},
                                }
                            },
                        }
                    }
                },
                metadata_key_b: {
                    "event_types": {
                        "events": {
                            "event_name": "auxiliary",
                            "event_description": "From the auxiliary board.",
                            "table_metadata_key": "shared",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome_b",
                                    "column_categories": {"labels": {0: "go", 1: "no_go"}},
                                }
                            },
                        }
                    }
                },
            }
        }
        nwbfile = mock_NWBFile()
        interface_a.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        interface_b.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # One shared table object, holding both interfaces' events.
        assert list(nwbfile.events.keys()) == ["Trials"]
        events = nwbfile.get_events_table("Trials")
        assert len(events) == 4
        assert set(events.colnames) == {"timestamp", "event_type", "outcome_a", "outcome_b"}
        # Globally time-sorted across interfaces (both fire at 0.1 and 0.2; stable order keeps A before B).
        assert list(events["timestamp"][:]) == pytest.approx([0.1, 0.1, 0.2, 0.2])
        assert list(events["event_type"][:]) == ["acquisition", "auxiliary", "acquisition", "auxiliary"]
        # Backfill: each interface's column is filled only on its own rows, "" elsewhere.
        assert list(events["outcome_a"][:]) == ["go", "", "no_go", ""]
        assert list(events["outcome_b"][:]) == ["", "go", "", "no_go"]
        # The discriminator's MeaningsTable was created by A and extended by B.
        event_type_meanings = events.meanings_tables["event_type_meanings"]
        value_to_meaning = dict(zip(event_type_meanings["value"][:], event_type_meanings["meaning"][:]))
        assert value_to_meaning == {
            "acquisition": "From the acquisition system.",
            "auxiliary": "From the auxiliary board.",
        }

    def test_duplicate_column_name_in_merge_raises(self):
        # Two event types writing the same column_name ("outcome_0") into one table is a collision,
        # not a shared column; it must raise rather than silently pool two streams into one column.
        interface = MockEventsInterface(num_event_types=2, event_payload="single value")
        metadata = {
            "Events": {
                "EventTables": {"pooled": {"table_name": "Pooled", "description": "Pooled events."}},
                "mock_events": {
                    "event_types": {
                        "events_0": {
                            "event_name": "left",
                            "event_description": "Left events.",
                            "table_metadata_key": "pooled",
                            "columns": {"outcome": {"column_name": "outcome_0"}},
                        },
                        "events_1": {
                            "event_name": "right",
                            "event_description": "Right events.",
                            "table_metadata_key": "pooled",
                            "columns": {"outcome": {"column_name": "outcome_0"}},
                        },
                    }
                },
            }
        }
        expected_error = (
            "Two event columns write the same column_name 'outcome_0'. Give each event column a unique column_name."
        )
        with pytest.raises(AssertionError, match=re.escape(expected_error)):
            interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)

    def test_merging_into_a_single_type_table_raises(self):
        # Two solo types resolving to the same table object name cannot share it: the first is written as
        # a single-type table (no discriminator), so the second has nowhere to record its identity. The
        # writer rejects it with a clear message rather than letting pynwb fail obscurely.
        interface = MockEventsInterface(num_event_types=2, event_payload="timestamps only")
        metadata = interface.get_metadata()
        metadata["Events"]["mock_events"]["event_types"]["events_0"]["event_name"] = "shared"
        metadata["Events"]["mock_events"]["event_types"]["events_1"]["event_name"] = "shared"
        expected_error = "An events table named 'Shared' already exists but is a single-type table"
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)
