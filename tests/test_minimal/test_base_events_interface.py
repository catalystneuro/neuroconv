"""Data-free tests of the shared events writer, driven by ``MockEventsInterface``."""

import re

import numpy as np
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
        # a solo type names its own table from its event_name. The entry holds nothing else: the default
        # mock type carries no description and no value columns, so get_metadata reports neither key
        # rather than emitting an empty description and an empty columns map.
        expected_metadata = {
            "mock_events": {
                "event_types": {
                    "events": {"event_name": "events"},
                },
            },
        }
        assert interface.get_metadata()["Events"] == expected_metadata

        overridden = MockEventsInterface(metadata_key="my_events").get_metadata()["Events"]
        assert set(overridden.keys()) == {"my_events"}

    def test_events_with_timestamps_only(self):
        interface = MockEventsInterface(event_payload="timestamps only")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        # The solo type "events" names its table by CamelCasing event_name ("events" -> "Events"), and
        # describes it from event_description, which nothing here set: the table's description stays
        # empty rather than being generated from the source id.
        events = nwbfile.get_events_table("Events")
        assert events.colnames == ("timestamp",)
        assert len(events) == 4
        assert events.description == ""

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
        # This mode declares meanings as well as labels, so the column earns a MeaningsTable.
        assert set(events.meanings_tables.keys()) == {"outcome_meanings"}

    def test_meanings_table_mapping(self):
        # A MeaningsTable holds a row per meaning the user filled in: explaining "go" and leaving "no_go"
        # blank gives a one-row table. The cells are unaffected, since they carry the display labels.
        interface = MockEventsInterface(event_payload="single value")
        metadata = interface.get_metadata()
        categories = metadata["Events"]["mock_events"]["event_types"]["events"]["columns"]["outcome"][
            "column_categories"
        ]
        categories["meanings"] = {0: "A go outcome.", 1: ""}
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        events = nwbfile.get_events_table("Events")
        assert list(events["outcome"][:]) == ["go", "no_go", "go", "no_go"]
        meanings_table = events.meanings_tables["outcome_meanings"]
        assert dict(zip(meanings_table["value"][:], meanings_table["meaning"][:])) == {"go": "A go outcome."}

    def test_empty_meanings_adds_no_meanings_table(self):
        # A meanings map whose entries are all blank explains nothing, so no MeaningsTable is written at
        # all. The column keeps its display labels.
        interface = MockEventsInterface(event_payload="single value")
        metadata = interface.get_metadata()
        categories = metadata["Events"]["mock_events"]["event_types"]["events"]["columns"]["outcome"][
            "column_categories"
        ]
        categories["meanings"] = {0: "", 1: ""}
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        events = nwbfile.get_events_table("Events")
        assert list(events["outcome"][:]) == ["go", "no_go", "go", "no_go"]
        assert (events.meanings_tables or {}) == {}

    def test_events_multi_value_payload(self):
        # A struct payload fans each field into its own column, on the same rows, one per way the writer
        # treats a value column: 'outcome' declares labels and meanings, 'cue' labels only, and
        # 'amplitude' no categories at all.
        interface = MockEventsInterface(num_events=3, event_payload="multi value")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        events = nwbfile.get_events_table("Events")
        assert set(events.colnames) == {"timestamp", "outcome", "cue", "amplitude"}
        assert list(events["outcome"][:]) == ["go", "no_go", "go"]
        assert list(events["cue"][:]) == ["tone", "tone", "light"]
        assert list(events["amplitude"][:]) == [0.0, 1.0, 2.0]
        # Only the column that declares meanings earns a MeaningsTable: 'cue' writes its display labels
        # without one, and 'amplitude' writes raw values.
        assert set(events.meanings_tables.keys()) == {"outcome_meanings"}

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
        metadata["Events"]["mock_events"]["event_types"]["events"]["columns"] = {"ghost": {"column_name": "ghost"}}
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

    def test_empty_event_description_does_not_create_meaning_rows_when_merged(self):
        # The discriminator's MeaningsTable holds a row per type the user described: describing one of
        # the two pooled types gives a one-row table.
        interface = MockEventsInterface(num_event_types=2, num_events=2)
        metadata = interface.get_metadata()
        event_types = metadata["Events"]["mock_events"]["event_types"]
        event_types["events_0"]["table_metadata_key"] = "pooled"
        event_types["events_1"]["table_metadata_key"] = "pooled"
        event_types["events_0"]["event_description"] = "Nose pokes into the reward port."
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        events = nwbfile.get_events_table("Pooled")
        assert "event_type" in events.colnames  # a merge always keeps its rows' identity
        meanings_table = events.meanings_tables["event_type_meanings"]
        assert dict(zip(meanings_table["value"][:], meanings_table["meaning"][:])) == {
            "events_0": "Nose pokes into the reward port."
        }

    def test_all_empty_event_descriptions_create_no_meanings_table_when_merged(self):
        # With neither type described the MeaningsTable would map each event_name to "", explaining
        # nothing, so it is not written at all. The event_type column still is: without it a bare
        # marker's row would lose its identity.
        interface = MockEventsInterface(num_event_types=2, num_events=2)
        metadata = interface.get_metadata()
        event_types = metadata["Events"]["mock_events"]["event_types"]
        event_types["events_0"]["table_metadata_key"] = "pooled"
        event_types["events_1"]["table_metadata_key"] = "pooled"
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        events = nwbfile.get_events_table("Pooled")
        assert "event_type" in events.colnames
        assert (events.meanings_tables or {}) == {}

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

    def test_two_event_types_with_same_name_errors(self):
        # Two event types with the same event_name resolve to the same table name, but neither asked to
        # combine (no shared table_metadata_key, no EventTables entry): they are two separate tables
        # colliding on a name. The writer rejects it and points at the two real fixes (rename, or combine
        # on purpose), rather than advising a merge that was never intended or letting pynwb fail obscurely.
        interface = MockEventsInterface(num_event_types=2, event_payload="timestamps only")
        metadata = interface.get_metadata()
        metadata["Events"]["mock_events"]["event_types"]["events_0"]["event_name"] = "shared"
        metadata["Events"]["mock_events"]["event_types"]["events_1"]["event_name"] = "shared"
        expected_error = "Event types 'events_0', 'events_1' resolve to the same events table name 'Shared'"
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)


class TestSharedColumnAcrossEventTypes:
    """A value column shared across event types pooled into one ``EventsTable`` (issue #1786).

    All single-interface: one ``MockEventsInterface`` whose event types route to one table via a shared
    ``table_metadata_key`` and each declare the same ``column_name``. Identical declarations merge into one
    column filled from every type's rows; declarations that genuinely conflict (different description, or
    the same code mapped to different meanings) raise. Each test spells out its own metadata in full so it
    reads on its own.
    """

    def test_shared_column_across_merged_event_types(self):
        # The #1786 repro: two event types pooled into one table both write the same column_name
        # ("outcome") with identical specs. That is one shared column, filled from both types' rows, not a
        # collision. Formerly this tripped a uniqueness assert; now it merges.
        interface = MockEventsInterface(num_event_types=2, num_events=2, event_payload="single value")
        metadata = {
            "Events": {
                "EventTables": {"pooled": {"table_name": "Pooled", "description": "Pooled events."}},
                "mock_events": {
                    "event_types": {
                        "events_0": {
                            "event_name": "left",
                            "event_description": "Left events.",
                            "table_metadata_key": "pooled",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "column_categories": {
                                        "labels": {0: "go", 1: "no_go"},
                                        "meanings": {0: "A go outcome.", 1: "A no-go outcome."},
                                    },
                                }
                            },
                        },
                        "events_1": {
                            "event_name": "right",
                            "event_description": "Right events.",
                            "table_metadata_key": "pooled",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "column_categories": {
                                        "labels": {0: "go", 1: "no_go"},
                                        "meanings": {0: "A go outcome.", 1: "A no-go outcome."},
                                    },
                                }
                            },
                        },
                    }
                },
            }
        }
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        events = nwbfile.get_events_table("Pooled")
        # A single shared column, not outcome_0 / outcome_1.
        assert set(events.colnames) == {"timestamp", "event_type", "outcome"}
        assert len(events) == 4
        assert list(events["timestamp"][:]) == pytest.approx([0.1, 0.2, 0.3, 0.4])
        assert list(events["event_type"][:]) == ["left", "right", "left", "right"]
        # Every row is filled from its own type; no fill-value gaps ("" would mark an unowned row).
        assert list(events["outcome"][:]) == ["go", "go", "no_go", "no_go"]
        # Exactly one MeaningsTable for the shared column, created once.
        assert set(events.meanings_tables.keys()) == {"event_type_meanings", "outcome_meanings"}
        value_to_meaning = dict(
            zip(
                events.meanings_tables["outcome_meanings"]["value"][:],
                events.meanings_tables["outcome_meanings"]["meaning"][:],
            )
        )
        assert value_to_meaning == {"go": "A go outcome.", "no_go": "A no-go outcome."}

    def test_shared_column_with_conflicting_meanings_raises(self):
        # Same column_name and the same label "go", but the two types explain it with different meanings.
        # One MeaningsTable cannot map "go" to two meanings, so this must raise. (Two types giving the same
        # raw code different labels is NOT a conflict, codes are per-source; only a shared label with two
        # meanings is.)
        interface = MockEventsInterface(num_event_types=2, num_events=2, event_payload="single value")
        metadata = {
            "Events": {
                "EventTables": {"pooled": {"table_name": "Pooled", "description": "Pooled events."}},
                "mock_events": {
                    "event_types": {
                        "events_0": {
                            "event_name": "left",
                            "event_description": "Left events.",
                            "table_metadata_key": "pooled",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "column_categories": {
                                        "labels": {0: "go", 1: "no_go"},
                                        "meanings": {0: "went", 1: "withheld"},
                                    },
                                }
                            },
                        },
                        "events_1": {
                            "event_name": "right",
                            "event_description": "Right events.",
                            "table_metadata_key": "pooled",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "column_categories": {
                                        "labels": {0: "go", 1: "no_go"},
                                        "meanings": {0: "proceeded", 1: "withheld"},  # "go" means something else
                                    },
                                }
                            },
                        },
                    }
                },
            }
        }
        expected_error = (
            "Event types 'left' (interface 'mock_events') and 'right' (interface 'mock_events') disagree on "
            "column 'outcome' in the shared events table 'Pooled': label 'go' means 'went' vs 'proceeded'"
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)

    def test_shared_column_with_conflicting_description_raises(self):
        # Same column_name and categories, but the two types describe it differently. Merging would have to
        # silently drop one description, so it must raise.
        interface = MockEventsInterface(num_event_types=2, num_events=2, event_payload="single value")
        metadata = {
            "Events": {
                "EventTables": {"pooled": {"table_name": "Pooled", "description": "Pooled events."}},
                "mock_events": {
                    "event_types": {
                        "events_0": {
                            "event_name": "left",
                            "event_description": "Left events.",
                            "table_metadata_key": "pooled",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "description": "Outcome of the left port.",
                                    "column_categories": {"labels": {0: "go", 1: "no_go"}},
                                }
                            },
                        },
                        "events_1": {
                            "event_name": "right",
                            "event_description": "Right events.",
                            "table_metadata_key": "pooled",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "description": "Outcome of the right port.",
                                    "column_categories": {"labels": {0: "go", 1: "no_go"}},
                                }
                            },
                        },
                    }
                },
            }
        }
        expected_error = (
            "Event types 'left' (interface 'mock_events') and 'right' (interface 'mock_events') disagree on "
            "column 'outcome' in the shared events table 'Pooled': description 'Outcome of the left port.' vs "
            "'Outcome of the right port.'"
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)

    def test_shared_column_reusing_a_code_with_different_labels_merges(self):
        # Two types share the "outcome" column and both use raw code 0, but map it to different labels
        # (go vs left). Codes are per-source, so this is a valid heterogeneous merge, not a conflict: each
        # type's rows render its own label and the column holds the union. Regression: this used to raise a
        # spurious "raw value 0 is labeled 'go' vs 'left'".
        interface = MockEventsInterface(num_event_types=2, num_events=2, event_payload="single value")
        metadata = {
            "Events": {
                "EventTables": {"pooled": {"table_name": "Pooled", "description": "Pooled events."}},
                "mock_events": {
                    "event_types": {
                        "events_0": {
                            "event_name": "left",
                            "event_description": "Left events.",
                            "table_metadata_key": "pooled",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "column_categories": {"labels": {0: "go", 1: "no_go"}},
                                }
                            },
                        },
                        "events_1": {
                            "event_name": "right",
                            "event_description": "Right events.",
                            "table_metadata_key": "pooled",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "column_categories": {"labels": {0: "left", 1: "right"}},
                                }
                            },
                        },
                    }
                },
            }
        }
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)  # must not raise

        events = nwbfile.get_events_table("Pooled")
        assert set(events.colnames) == {"timestamp", "event_type", "outcome"}
        # Each type renders its own label for its own rows; the column is the union of both vocabularies.
        assert list(events["outcome"][:]) == ["go", "left", "no_go", "right"]


class TestEventsAcrossInterfaces:
    """Events written by several interfaces into one shared ``EventsTable``, the converter-pipeline pattern.

    A converter (``NWBConverter``/``ConverterPipe``) adds each interface in turn by calling its
    ``add_to_nwbfile`` on the same file; these tests reproduce that by hand with two ``MockEventsInterface``
    instances (distinct ``metadata_key``) routing into one table via a shared ``table_metadata_key`` and a
    declared ``EventTables`` entry. The second interface appends to the table the first wrote, which is a
    different write path from the single-interface merges in ``TestMockEventsInterface``.
    """

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

    def test_shared_column_across_two_interfaces(self):
        # The cross-interface counterpart of TestSharedColumnAcrossEventTypes.test_shared_column_across_merged_event_types:
        # both interfaces write the SAME column_name ("outcome") with identical categories. The second
        # interface appends to the first's column instead of getting its own, so it is one shared column
        # filled from both, not outcome_a / outcome_b with fill-value gaps.
        interface_a = MockEventsInterface(metadata_key="events_a", num_events=2, event_payload="single value")
        interface_b = MockEventsInterface(metadata_key="events_b", num_events=2, event_payload="single value")
        shared_outcome = {
            "column_name": "outcome",
            "column_categories": {
                "labels": {0: "go", 1: "no_go"},
                "meanings": {0: "A go outcome.", 1: "A no-go outcome."},
            },
        }
        metadata = {
            "Events": {
                "EventTables": {"shared": {"table_name": "Trials", "description": "Trials from two systems."}},
                "events_a": {
                    "event_types": {
                        "events": {
                            "event_name": "acquisition",
                            "event_description": "From the acquisition system.",
                            "table_metadata_key": "shared",
                            "columns": {"outcome": shared_outcome},
                        }
                    }
                },
                "events_b": {
                    "event_types": {
                        "events": {
                            "event_name": "auxiliary",
                            "event_description": "From the auxiliary board.",
                            "table_metadata_key": "shared",
                            "columns": {"outcome": dict(shared_outcome)},
                        }
                    }
                },
            }
        }
        nwbfile = mock_NWBFile()
        interface_a.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        interface_b.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        events = nwbfile.get_events_table("Trials")
        assert set(events.colnames) == {"timestamp", "event_type", "outcome"}
        assert len(events) == 4
        assert list(events["event_type"][:]) == ["acquisition", "auxiliary", "acquisition", "auxiliary"]
        # One shared column, every row filled from its own interface, no "" gaps.
        assert list(events["outcome"][:]) == ["go", "go", "no_go", "no_go"]
        # A created the outcome MeaningsTable; B reused it rather than duplicating.
        assert set(events.meanings_tables.keys()) == {"event_type_meanings", "outcome_meanings"}

    def test_unset_table_metadata_key_is_not_shared_across_interfaces(self):
        # An unset table_metadata_key defaults to each type's own event_type_source_id, a per-type handle,
        # NOT a shared table. Two solo types in different interfaces that both leave it unset are not a merge,
        # even though they happen to share the default source id "events". Each writes its own table named from
        # its event_name, with its own independent outcome column, so the differing labels are not a conflict.
        interface_a = MockEventsInterface(metadata_key="events_a", num_events=2, event_payload="single value")
        interface_b = MockEventsInterface(metadata_key="events_b", num_events=2, event_payload="single value")
        metadata = {
            "Events": {
                "events_a": {
                    "event_types": {
                        "events": {
                            "event_name": "left",
                            "event_description": "Left events.",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "column_categories": {"labels": {0: "go", 1: "no_go"}},
                                }
                            },
                        }
                    }
                },
                "events_b": {
                    "event_types": {
                        "events": {
                            "event_name": "right",
                            "event_description": "Right events.",
                            # Same column_name, different labels: a conflict ONLY if these shared a table.
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "column_categories": {"labels": {0: "left", 1: "right"}},
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

        # Two separate solo tables named from each type's event_name, not one merged table.
        assert set(nwbfile.events.keys()) == {"Left", "Right"}
        left = nwbfile.get_events_table("Left")
        right = nwbfile.get_events_table("Right")
        # A solo table has no event_type discriminator, and each carries its own independent outcome column.
        assert "event_type" not in left.colnames
        assert "event_type" not in right.colnames
        assert list(left["outcome"][:]) == ["go", "no_go"]
        assert list(right["outcome"][:]) == ["left", "right"]

    def test_cross_interface_conflicting_shared_column_errors(self):
        # Two interfaces route into one declared shared table and both write column "outcome", agreeing on the
        # label "go" but explaining it with different meanings. That is a genuine cross-interface conflict (one
        # MeaningsTable cannot map "go" two ways); the validator catches it up front (on the first interface's
        # write, before anything is added) with a message naming both types and their interfaces.
        interface_a = MockEventsInterface(metadata_key="events_a", num_events=2, event_payload="single value")
        interface_b = MockEventsInterface(metadata_key="events_b", num_events=2, event_payload="single value")
        metadata = {
            "Events": {
                "EventTables": {"shared": {"table_name": "Trials", "description": "Trials from two systems."}},
                "events_a": {
                    "event_types": {
                        "events": {
                            "event_name": "acquisition",
                            "event_description": "From the acquisition system.",
                            "table_metadata_key": "shared",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "column_categories": {
                                        "labels": {0: "go", 1: "no_go"},
                                        "meanings": {0: "went", 1: "withheld"},
                                    },
                                }
                            },
                        }
                    }
                },
                "events_b": {
                    "event_types": {
                        "events": {
                            "event_name": "auxiliary",
                            "event_description": "From the auxiliary board.",
                            "table_metadata_key": "shared",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "column_categories": {
                                        "labels": {0: "go", 1: "no_go"},
                                        "meanings": {0: "proceeded", 1: "withheld"},  # "go" means something else
                                    },
                                }
                            },
                        }
                    }
                },
            }
        }
        expected_error = (
            "Event types 'acquisition' (interface 'events_a') and 'auxiliary' (interface 'events_b') disagree "
            "on column 'outcome' in the shared events table 'Trials': label 'go' means 'went' vs 'proceeded'"
        )
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            interface_a.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)

    def test_cross_interface_heterogeneous_shared_column_keeps_all_meanings(self):
        # Two interfaces write one shared "outcome" column. They agree on the codes they both declare (0, 1),
        # and interface B additionally declares a code A never does (2 -> "abort"). The declarations are
        # consistent on the intersection, so they merge; B's extra meaning must be added to the column's
        # MeaningsTable rather than dropped (the bug this fixes).
        interface_a = MockEventsInterface(metadata_key="events_a", num_events=2, event_payload="single value")
        interface_b = MockEventsInterface(metadata_key="events_b", num_events=2, event_payload="single value")
        shared_labels = {0: "go", 1: "no_go"}
        shared_meanings = {0: "A go outcome.", 1: "A no-go outcome."}
        metadata = {
            "Events": {
                "EventTables": {"shared": {"table_name": "Trials", "description": "Trials from two systems."}},
                "events_a": {
                    "event_types": {
                        "events": {
                            "event_name": "acquisition",
                            "event_description": "From the acquisition system.",
                            "table_metadata_key": "shared",
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "column_categories": {"labels": shared_labels, "meanings": shared_meanings},
                                }
                            },
                        }
                    }
                },
                "events_b": {
                    "event_types": {
                        "events": {
                            "event_name": "auxiliary",
                            "event_description": "From the auxiliary board.",
                            "table_metadata_key": "shared",
                            # Agrees on 0/1, adds 2 -> "abort" that A never declares.
                            "columns": {
                                "outcome": {
                                    "column_name": "outcome",
                                    "column_categories": {
                                        "labels": {**shared_labels, 2: "abort"},
                                        "meanings": {**shared_meanings, 2: "An aborted trial."},
                                    },
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

        events = nwbfile.get_events_table("Trials")
        # One MeaningsTable for the shared column, holding the union of both interfaces' meanings, including
        # B's "abort", which the old writer dropped because the column already existed when B appended.
        value_to_meaning = dict(
            zip(
                events.meanings_tables["outcome_meanings"]["value"][:],
                events.meanings_tables["outcome_meanings"]["meaning"][:],
            )
        )
        assert value_to_meaning == {
            "go": "A go outcome.",
            "no_go": "A no-go outcome.",
            "abort": "An aborted trial.",
        }

    def test_combining_into_an_existing_single_type_table_errors(self):
        # An interface writes its one event type as its own table "Trials" without knowing the table will be
        # shared (it was handed only its own metadata). A second interface then arrives with metadata that
        # declares "Trials" as a shared table and routes its type there. The existing "Trials" has no
        # event_type column and its rows' type was never recorded, so combining errors rather than mislabeling
        # those rows. This only arises with partial metadata; a converter hands every interface the merged
        # metadata, so the first writer would build "Trials" as a shared table from the start.
        interface_a = MockEventsInterface(metadata_key="events_a", num_events=2, event_payload="timestamps only")
        interface_b = MockEventsInterface(metadata_key="events_b", num_events=2, event_payload="timestamps only")
        nwbfile = mock_NWBFile()

        metadata_a = interface_a.get_metadata()
        metadata_a["Events"]["events_a"]["event_types"]["events"]["event_name"] = "Trials"
        interface_a.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata_a)  # writes a single-type table "Trials"

        metadata_b = interface_b.get_metadata()
        metadata_b["Events"]["EventTables"] = {"shared": {"table_name": "Trials", "description": "Trials."}}
        metadata_b["Events"]["events_b"]["event_types"]["events"]["table_metadata_key"] = "shared"
        expected_error = "already exists but holds a single event type"
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            interface_b.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata_b)


class TestEventsTemporalAlignment:
    """Gross temporal alignment on ``BaseEventsInterface``: ``interface.alignment.shift_times`` offsets event times at write.

    The mock's single "events" type has native timestamps ``[0.1, 0.2, 0.3, 0.4]``.
    """

    def test_unshifted_events_are_written_at_native_times(self):
        interface = MockEventsInterface()
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        written = np.asarray(nwbfile.get_events_table("Events")["timestamp"][:])
        np.testing.assert_allclose(written, [0.1, 0.2, 0.3, 0.4])

    def test_shift_times_offsets_written_timestamps_and_accumulates(self):
        # Relative and rigid: repeated shifts sum, and the written events move by the total.
        interface = MockEventsInterface()
        interface.alignment.shift_times(1.0)
        interface.alignment.shift_times(0.5)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        written = np.asarray(nwbfile.get_events_table("Events")["timestamp"][:])
        np.testing.assert_allclose(written, [1.6, 1.7, 1.8, 1.9])

    def test_shift_preserves_durations(self):
        # A shift moves timestamps but leaves each event's duration unchanged.
        interface = MockEventsInterface(event_extent="event with duration")
        interface.alignment.shift_times(5.0)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        events = nwbfile.get_events_table("Events")
        np.testing.assert_allclose(np.asarray(events["timestamp"][:]), [5.1, 5.2, 5.3, 5.4])
        np.testing.assert_allclose(np.asarray(events["duration"][:]), [0.05, 0.05, 0.05, 0.05])
