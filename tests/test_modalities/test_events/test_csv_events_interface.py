import pytest
from jsonschema.validators import Draft7Validator
from pydantic import ValidationError
from pynwb import NWBHDF5IO
from pynwb.event import EventsTable
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import CSVEventsInterface

# A single-type event file: a single ``timestamps`` column written as one EventsTable named after
# the file stem, CamelCased ("ttl" -> "Ttl").
SINGLE_TYPE_TIMESTAMPS = [1.5, 2.5, 3.5, 4.5]

# A two-type event file: onset times tagged by a "kind" label. By default each distinct label becomes
# its own EventsTable ("a" -> "A", "b" -> "B"); "a" fires at 1/3/5 and "b" at 2/4.
TWO_TYPE_ROWS = [(1.0, "a"), (2.0, "b"), (3.0, "a"), (4.0, "b"), (5.0, "a")]


class TestCSVEventsInterface:
    @pytest.fixture
    def single_type_file(self, tmp_path):
        file_path = tmp_path / "ttl.csv"
        lines = ["timestamps"] + [str(value) for value in SINGLE_TYPE_TIMESTAMPS]
        file_path.write_text("\n".join(lines) + "\n")
        return file_path

    @pytest.fixture
    def interface(self, single_type_file):
        return CSVEventsInterface(
            file_path=single_type_file,
            timestamps_column="timestamps",
            event_type_column=None,
        )

    @pytest.fixture
    def two_type_file(self, tmp_path):
        file_path = tmp_path / "events.csv"
        lines = ["onset,kind"] + [f"{onset},{kind}" for onset, kind in TWO_TYPE_ROWS]
        file_path.write_text("\n".join(lines) + "\n")
        return file_path

    @pytest.fixture
    def headerless_two_type_file(self, tmp_path):
        file_path = tmp_path / "events_headerless.csv"
        lines = [f"{onset},{kind}" for onset, kind in TWO_TYPE_ROWS]
        file_path.write_text("\n".join(lines) + "\n")
        return file_path

    @pytest.fixture
    def single_type_file_with_nans(self, tmp_path):
        # Rows 2 and 4 have an empty timestamps cell, parsed by pandas as NaN and dropped. The cells
        # are quoted ("") so pandas reads them as empty-string values rather than skipping them as
        # blank lines (skip_blank_lines drops a bare empty line before it ever becomes a NaN row).
        file_path = tmp_path / "ttl.csv"
        file_path.write_text('timestamps\n1.5\n""\n3.5\n""\n5.5\n')
        return file_path

    @pytest.fixture
    def two_type_file_with_nans(self, tmp_path):
        # The "b" rows have an empty onset cell (NaN) and are dropped along with their labels, so "b"
        # never becomes an event type at all.
        file_path = tmp_path / "events.csv"
        file_path.write_text("onset,kind\n1.0,a\n,b\n3.0,a\n,b\n5.0,a\n")
        return file_path

    def test_event_type_column_is_required(self, single_type_file):
        """event_type_column has no default, so omitting it is an error."""
        with pytest.raises(ValidationError):
            CSVEventsInterface(file_path=single_type_file, timestamps_column="timestamps")

    def test_column_used_for_two_roles_raises(self, two_type_file):
        """A column assigned to more than one role is a construction mistake."""
        with pytest.raises(ValueError, match="only one role"):
            CSVEventsInterface(
                file_path=two_type_file,
                timestamps_column="onset",
                event_type_column="kind",
                value_columns=["kind"],
            )

    def test_mixed_name_and_index_specifiers_raise(self, two_type_file):
        """Column specifiers must all be names or all be positional indices, never a mix."""
        with pytest.raises(ValueError, match="mix header names and positional indices"):
            CSVEventsInterface(
                file_path=two_type_file,
                timestamps_column="onset",
                event_type_column=1,
            )

    def test_get_metadata_does_not_set_session_start_time(self, interface):
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") is None

    def test_metadata_schema_is_valid(self, interface):
        Draft7Validator.check_schema(interface.get_metadata_schema())

    def test_single_type_metadata_keyed_by_file_stem(self, interface):
        event_types = interface.get_metadata()["Events"]["ttl"]["event_types"]
        assert list(event_types) == ["ttl"]
        assert event_types["ttl"]["event_name"] == "ttl"
        assert "columns" not in event_types["ttl"]  # timestamp-only

    def test_labeled_metadata_has_one_event_type_per_label(self, two_type_file):
        interface = CSVEventsInterface(
            file_path=two_type_file,
            timestamps_column="onset",
            event_type_column="kind",
            metadata_key="my_events",
        )
        event_types = interface.get_metadata()["Events"]["my_events"]["event_types"]
        # First-appearance order: "a" before "b"; each becomes its own event type.
        assert list(event_types) == ["a", "b"]
        assert event_types["a"]["event_name"] == "a"
        assert event_types["b"]["event_name"] == "b"

    def test_single_type_writes_one_events_table(self, interface):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        ttl_events = nwbfile.get_events_table("Ttl")  # "ttl" CamelCased
        assert isinstance(ttl_events, EventsTable)
        assert ttl_events.colnames == ("timestamp",)
        assert list(ttl_events["timestamp"][:]) == SINGLE_TYPE_TIMESTAMPS

    def test_labeled_writes_separate_tables_by_default(self, two_type_file):
        interface = CSVEventsInterface(file_path=two_type_file, timestamps_column="onset", event_type_column="kind")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        # Each distinct label is its own table, and neither carries an event_type discriminator.
        assert set(nwbfile.events.keys()) == {"A", "B"}
        a_table = nwbfile.get_events_table("A")
        b_table = nwbfile.get_events_table("B")
        assert a_table.colnames == ("timestamp",)
        assert list(a_table["timestamp"][:]) == [1.0, 3.0, 5.0]
        assert list(b_table["timestamp"][:]) == [2.0, 4.0]

    def test_labeled_merged_into_one_table_via_metadata(self, two_type_file):
        # The user opts into a single pooled table with an event_type discriminator by pointing both
        # types' table_metadata_key at a shared key and declaring that table under EventTables.
        interface = CSVEventsInterface(file_path=two_type_file, timestamps_column="onset", event_type_column="kind")
        metadata = interface.get_metadata()
        metadata["Events"]["EventTables"] = {"events": {"table_name": "Events", "description": "Pooled CSV events."}}
        for event_type in metadata["Events"]["events"]["event_types"].values():
            event_type["table_metadata_key"] = "events"

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert list(nwbfile.events.keys()) == ["Events"]
        events = nwbfile.get_events_table("Events")
        assert set(events.colnames) == {"timestamp", "event_type"}
        # Pooled rows are re-sorted chronologically, event_type naming each row's type.
        assert list(events["timestamp"][:]) == [1.0, 2.0, 3.0, 4.0, 5.0]
        assert list(events["event_type"][:]) == ["a", "b", "a", "b", "a"]
        # No type was described, so the discriminator gets no MeaningsTable rather than one restating
        # each event_name back at the reader.
        assert not events.meanings_tables

    def test_merged_event_type_meanings_from_user_descriptions(self, two_type_file):
        # When the user describes the pooled types, the event_type discriminator carries a MeaningsTable
        # mapping each type to its description; an undescribed type earns no row.
        interface = CSVEventsInterface(file_path=two_type_file, timestamps_column="onset", event_type_column="kind")
        metadata = interface.get_metadata()
        metadata["Events"]["EventTables"] = {"events": {"table_name": "Events", "description": "Pooled CSV events."}}
        event_types = metadata["Events"]["events"]["event_types"]
        for event_type in event_types.values():
            event_type["table_metadata_key"] = "events"
        event_types["a"]["event_description"] = "Left choice."
        event_types["b"]["event_description"] = "Right choice."

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        events = nwbfile.get_events_table("Events")
        meanings_tables = list(events.meanings_tables.values())
        assert len(meanings_tables) == 1
        meanings = dict(zip(meanings_tables[0]["value"][:], meanings_tables[0]["meaning"][:]))
        assert meanings == {"a": "Left choice.", "b": "Right choice."}

    def test_merged_types_share_a_value_column(self, tmp_path):
        # Two event types pooled into one table share a value column: both seed the same "outcome"
        # column, so the merged table carries a single populated "outcome" (not one half-empty column
        # per type). This is the within-interface shared-column case the base interface enabled.
        file_path = tmp_path / "trials.csv"
        file_path.write_text("onset,kind,outcome\n1.0,a,hit\n2.0,b,miss\n3.0,a,miss\n4.0,b,hit\n5.0,a,hit\n")
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column="kind",
            value_columns=["outcome"],
        )
        metadata = interface.get_metadata()
        metadata["Events"]["EventTables"] = {"trials": {"table_name": "Trials", "description": "Pooled CSV trials."}}
        for event_type in metadata["Events"]["trials"]["event_types"].values():
            event_type["table_metadata_key"] = "trials"

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert list(nwbfile.events.keys()) == ["Trials"]
        trials = nwbfile.get_events_table("Trials")
        # A single shared "outcome" column, not "outcome" split per type.
        assert set(trials.colnames) == {"timestamp", "event_type", "outcome"}
        # Pooled rows are re-sorted chronologically; outcome stays row-aligned across both types.
        assert list(trials["timestamp"][:]) == [1.0, 2.0, 3.0, 4.0, 5.0]
        assert list(trials["event_type"][:]) == ["a", "b", "a", "b", "a"]
        assert list(trials["outcome"][:]) == ["hit", "miss", "miss", "hit", "hit"]

    def test_headerless_int_columns(self, headerless_two_type_file):
        interface = CSVEventsInterface(file_path=headerless_two_type_file, timestamps_column=0, event_type_column=1)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert set(nwbfile.events.keys()) == {"A", "B"}
        assert list(nwbfile.get_events_table("A")["timestamp"][:]) == [1.0, 3.0, 5.0]
        assert list(nwbfile.get_events_table("B")["timestamp"][:]) == [2.0, 4.0]

    def test_value_column_declares_only_its_name(self, tmp_path):
        # A value column seeds only its structural column_name: the CSV carries no codebook, so no
        # description and no column_categories are invented (numeric or not).
        file_path = tmp_path / "trial.csv"
        file_path.write_text("onset,amplitude,outcome\n1.0,0.5,go\n2.0,1.5,no_go\n3.0,2.5,go\n")
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column=None,
            value_columns=["amplitude", "outcome"],
        )
        columns = interface.get_metadata()["Events"]["trial"]["event_types"]["trial"]["columns"]
        assert columns["amplitude"] == {"column_name": "amplitude"}
        assert columns["outcome"] == {"column_name": "outcome"}

    def test_value_columns_carry_raw_values(self, tmp_path):
        # Both a numeric and a non-numeric value column write their raw cell values directly, with no
        # MeaningsTable, since nothing was annotated.
        file_path = tmp_path / "trial.csv"
        file_path.write_text("onset,amplitude,outcome\n1.0,0.5,go\n2.0,1.5,no_go\n3.0,2.5,go\n")
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column=None,
            value_columns=["amplitude", "outcome"],
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        trial = nwbfile.get_events_table("Trial")
        assert set(trial.colnames) == {"timestamp", "amplitude", "outcome"}
        assert list(trial["amplitude"][:]) == [0.5, 1.5, 2.5]
        assert list(trial["outcome"][:]) == ["go", "no_go", "go"]
        assert not trial.meanings_tables  # nothing annotated -> no MeaningsTable

    def test_numeric_value_column_with_blank_coerces_to_nan(self, tmp_path):
        # A numeric payload column with a blank cell: keep_default_na=False leaves the blank as the
        # literal '', which would otherwise promote the whole column to object strings. The per-column
        # sniff coerces it to float (the blank becoming NaN), while the categorical column stays raw.
        file_path = tmp_path / "trial.csv"
        file_path.write_text("onset,amplitude,outcome\n1.0,0.5,go\n2.0,,no_go\n3.0,0.9,go\n")
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column=None,
            value_columns=["amplitude", "outcome"],
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        trial = nwbfile.get_events_table("Trial")
        assert list(trial["amplitude"][:]) == pytest.approx([0.5, float("nan"), 0.9], nan_ok=True)
        assert list(trial["outcome"][:]) == ["go", "no_go", "go"]

    def test_value_column_codebook_added_in_metadata(self, tmp_path):
        # The auto-seed is gone, but the categorical path still works when the user supplies a codebook:
        # a labels map relabels the cells and a meanings map produces a MeaningsTable.
        file_path = tmp_path / "trial.csv"
        file_path.write_text("onset,outcome\n1.0,go\n2.0,no_go\n3.0,go\n")
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column=None,
            value_columns=["outcome"],
        )
        metadata = interface.get_metadata()
        metadata["Events"]["trial"]["event_types"]["trial"]["columns"]["outcome"]["column_categories"] = {
            "labels": {"go": "GO", "no_go": "NoGo"},
            "meanings": {"go": "reward delivered", "no_go": "no reward"},
        }

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        trial = nwbfile.get_events_table("Trial")
        assert set(trial.colnames) == {"timestamp", "outcome"}
        assert list(trial["outcome"][:]) == ["GO", "NoGo", "GO"]  # labels mapped through
        meanings_tables = list(trial.meanings_tables.values())
        assert len(meanings_tables) == 1
        meanings = dict(zip(meanings_tables[0]["value"][:], meanings_tables[0]["meaning"][:]))
        assert meanings == {"GO": "reward delivered", "NoGo": "no reward"}

    def test_durations_column(self, tmp_path):
        # A durations column makes the events durative; a blank cell becomes a NaN duration.
        file_path = tmp_path / "bouts.csv"
        file_path.write_text('onset,dur\n1.0,0.5\n2.0,0.25\n3.0,""\n')
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column=None,
            durations_column="dur",
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        bouts = nwbfile.get_events_table("Bouts")
        assert set(bouts.colnames) == {"timestamp", "duration"}
        assert list(bouts["timestamp"][:]) == [1.0, 2.0, 3.0]
        assert list(bouts["duration"][:]) == pytest.approx([0.5, 0.25, float("nan")], nan_ok=True)

    def test_time_unit_scales_timestamps(self, tmp_path):
        # A millisecond time unit divides the raw timestamps by 1000 to convert them to seconds.
        file_path = tmp_path / "ttl.csv"
        file_path.write_text("timestamps\n1500\n2500\n3500\n")
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="timestamps",
            event_type_column=None,
            time_unit="milliseconds",
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert list(nwbfile.get_events_table("Ttl")["timestamp"][:]) == pytest.approx([1.5, 2.5, 3.5])

    def test_time_unit_scales_timestamps_and_durations(self, tmp_path):
        # Timestamps and durations share the recording's time base, so both are scaled by the unit; a
        # blank duration stays NaN through the division.
        file_path = tmp_path / "bouts.csv"
        file_path.write_text('onset,dur\n1000,500\n2000,250\n3000,""\n')
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column=None,
            durations_column="dur",
            time_unit="milliseconds",
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        bouts = nwbfile.get_events_table("Bouts")
        assert list(bouts["timestamp"][:]) == pytest.approx([1.0, 2.0, 3.0])
        assert list(bouts["duration"][:]) == pytest.approx([0.5, 0.25, float("nan")], nan_ok=True)

    def test_time_unit_leaves_value_columns_unscaled(self, tmp_path):
        # value_columns are arbitrary payload, not time, so the unit conversion must not touch them.
        file_path = tmp_path / "trial.csv"
        file_path.write_text("onset,amplitude\n1000,500\n2000,250\n")
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column=None,
            value_columns=["amplitude"],
            time_unit="milliseconds",
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        trial = nwbfile.get_events_table("Trial")
        assert list(trial["timestamp"][:]) == pytest.approx([1.0, 2.0])
        assert list(trial["amplitude"][:]) == [500, 250]  # unscaled

    def test_missing_timestamps_are_dropped(self, single_type_file_with_nans):
        interface = CSVEventsInterface(
            file_path=single_type_file_with_nans,
            timestamps_column="timestamps",
            event_type_column=None,
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        ttl_events = nwbfile.get_events_table("Ttl")
        assert list(ttl_events["timestamp"][:]) == [1.5, 3.5, 5.5]

    def test_missing_timestamps_emit_warning(self, two_type_file_with_nans):
        interface = CSVEventsInterface(
            file_path=two_type_file_with_nans,
            timestamps_column="onset",
            event_type_column="kind",
        )
        with pytest.warns(UserWarning, match="Dropped 2 row"):
            interface.get_metadata()

    def test_missing_timestamps_drop_labels_in_step(self, two_type_file_with_nans):
        interface = CSVEventsInterface(
            file_path=two_type_file_with_nans,
            timestamps_column="onset",
            event_type_column="kind",
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        # Only the three "a" rows survive; "b" loses both rows and never becomes a table.
        assert set(nwbfile.events.keys()) == {"A"}
        assert list(nwbfile.get_events_table("A")["timestamp"][:]) == [1.0, 3.0, 5.0]

    def test_na_like_value_tokens_are_read_literally(self, tmp_path):
        # 'None', 'NA', 'null' and a blank cell are real, distinct category values here; the default
        # keep_default_na=False must keep them apart instead of collapsing them into one nan label.
        file_path = tmp_path / "trial.csv"
        file_path.write_text("onset,reward\n1.0,small\n2.0,None\n3.0,NA\n4.0,null\n5.0,\n6.0,large\n")
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column=None,
            value_columns=["reward"],
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        trial = nwbfile.get_events_table("Trial")
        assert list(trial["reward"][:]) == ["small", "None", "NA", "null", "", "large"]

    def test_read_kwargs_forwarded_to_read_csv(self, tmp_path):
        # A ';' separator with ',' as the decimal mark: only reachable through read_kwargs.
        file_path = tmp_path / "events.csv"
        file_path.write_text("onset;kind\n1,5;a\n2,5;b\n")
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column="kind",
            read_kwargs={"sep": ";", "decimal": ","},
        )
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert list(nwbfile.get_events_table("A")["timestamp"][:]) == [1.5]
        assert list(nwbfile.get_events_table("B")["timestamp"][:]) == [2.5]

    def test_empty_file_writes_no_table(self, tmp_path):
        file_path = tmp_path / "ttl.csv"
        file_path.write_text("timestamps\n")  # header only, no rows
        interface = CSVEventsInterface(file_path=file_path, timestamps_column="timestamps", event_type_column=None)
        assert interface.get_metadata()["Events"]["ttl"]["event_types"] == {}

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
        assert len(nwbfile.events) == 0

    def test_round_trip(self, interface, tmp_path):
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        nwbfile_path = tmp_path / "test_csv_events.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()
            read_events = read_nwbfile.get_events_table("Ttl")
            assert isinstance(read_events, EventsTable)
            assert list(read_events["timestamp"][:]) == SINGLE_TYPE_TIMESTAMPS
