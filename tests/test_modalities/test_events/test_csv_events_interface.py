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
        with pytest.raises(AssertionError, match="only one role"):
            CSVEventsInterface(
                file_path=two_type_file,
                timestamps_column="onset",
                event_type_column="kind",
                value_columns=["kind"],
            )

    def test_get_metadata_does_not_set_session_start_time(self, interface):
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") is None

    def test_metadata_schema_is_valid(self, interface):
        Draft7Validator.check_schema(interface.get_metadata_schema())

    def test_single_type_metadata_keyed_by_file_stem(self, interface):
        event_types = interface.get_metadata()["Events"]["csv_events"]["event_types"]
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
        for event_type in metadata["Events"]["csv_events"]["event_types"].values():
            event_type["table_metadata_key"] = "events"

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert list(nwbfile.events.keys()) == ["Events"]
        events = nwbfile.get_events_table("Events")
        assert set(events.colnames) == {"timestamp", "event_type"}
        # Pooled rows are re-sorted chronologically, event_type naming each row's type.
        assert list(events["timestamp"][:]) == [1.0, 2.0, 3.0, 4.0, 5.0]
        assert list(events["event_type"][:]) == ["a", "b", "a", "b", "a"]
        # The discriminator carries a MeaningsTable mapping each type to its seeded description.
        event_type_meanings = events.meanings_tables["event_type_meanings"]
        assert set(event_type_meanings["value"][:]) == {"a", "b"}

    def test_headerless_int_columns(self, headerless_two_type_file):
        interface = CSVEventsInterface(file_path=headerless_two_type_file, timestamps_column=0, event_type_column=1)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert set(nwbfile.events.keys()) == {"A", "B"}
        assert list(nwbfile.get_events_table("A")["timestamp"][:]) == [1.0, 3.0, 5.0]
        assert list(nwbfile.get_events_table("B")["timestamp"][:]) == [2.0, 4.0]

    def test_numeric_value_column_is_plain(self, tmp_path):
        # A numeric value column is written as a plain column with no category mapping.
        file_path = tmp_path / "signal.csv"
        file_path.write_text("onset,amplitude\n1.0,0.5\n2.0,1.5\n3.0,2.5\n")
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column=None,
            value_columns=["amplitude"],
        )
        metadata = interface.get_metadata()
        # Numeric columns get no column_categories seeded.
        column = metadata["Events"]["csv_events"]["event_types"]["signal"]["columns"]["amplitude"]
        assert "column_categories" not in column

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        signal = nwbfile.get_events_table("Signal")
        assert set(signal.colnames) == {"timestamp", "amplitude"}
        assert list(signal["amplitude"][:]) == [0.5, 1.5, 2.5]
        assert not signal.meanings_tables  # no categorical column -> no MeaningsTable

    def test_non_numeric_value_column_is_categorical(self, tmp_path):
        # A non-numeric value column is seeded as a categorical column; relabelling a value in the
        # editable metadata maps through on write, proving the category path is used.
        file_path = tmp_path / "trial.csv"
        file_path.write_text("onset,outcome\n1.0,go\n2.0,no_go\n3.0,go\n")
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column=None,
            value_columns=["outcome"],
        )
        metadata = interface.get_metadata()
        labels = metadata["Events"]["csv_events"]["event_types"]["trial"]["columns"]["outcome"]["column_categories"][
            "labels"
        ]
        assert labels == {"go": "go", "no_go": "no_go"}  # seeded as an identity map
        labels["go"] = "GO"  # user renames a display label

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        trial = nwbfile.get_events_table("Trial")
        assert set(trial.colnames) == {"timestamp", "outcome"}
        assert list(trial["outcome"][:]) == ["GO", "no_go", "GO"]

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
        assert interface.get_metadata()["Events"]["csv_events"]["event_types"] == {}

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
