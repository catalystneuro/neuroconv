import ndx_events
import pytest
from jsonschema.validators import Draft7Validator
from pydantic import ValidationError
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import CSVEventsInterface

# A single-type event file: a single ``timestamps`` column written as one Events object named after
# the file stem ("ttl").
SINGLE_TYPE_TIMESTAMPS = [1.5, 2.5, 3.5, 4.5]

# A two-type event file: onset times tagged by a "kind" label. Written as one LabeledEvents with
# the onsets in file order plus a per-event code into the label vocabulary. Labels are ordered by
# first appearance: "a" (code 0) before "b" (code 1).
TWO_TYPE_ROWS = [(1.0, "a"), (2.0, "b"), (3.0, "a"), (4.0, "b"), (5.0, "a")]
EXPECTED_LABELED_TIMESTAMPS = [1.0, 2.0, 3.0, 4.0, 5.0]
EXPECTED_LABELED_DATA = [0, 1, 0, 1, 0]
EXPECTED_LABELS = ["a", "b"]


class TestCSVEventsInterface:
    @pytest.fixture
    def single_type_file(self, tmp_path):
        file_path = tmp_path / "ttl.csv"
        lines = ["timestamps"] + [str(value) for value in SINGLE_TYPE_TIMESTAMPS]
        file_path.write_text("\n".join(lines) + "\n")
        return file_path

    @pytest.fixture
    def interface(self, single_type_file):
        return CSVEventsInterface(file_path=single_type_file, timestamps_column="timestamps", event_type_column=None)

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
        # The "b" rows have an empty onset cell (NaN) and are dropped along with their labels.
        file_path = tmp_path / "events.csv"
        file_path.write_text("onset,kind\n1.0,a\n,b\n3.0,a\n,b\n5.0,a\n")
        return file_path

    def test_event_type_column_is_required(self, single_type_file):
        """event_type_column has no default, so omitting it is an error."""
        with pytest.raises(ValidationError):
            CSVEventsInterface(file_path=single_type_file, timestamps_column="timestamps")

    def test_get_metadata_does_not_set_session_start_time(self, interface):
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") is None

    def test_metadata_schema_is_valid(self, interface):
        Draft7Validator.check_schema(interface.get_metadata_schema())

    def test_single_type_metadata_keyed_by_file_stem(self, interface):
        event_types = interface.get_metadata()["Events"]["csv_events"]["event_types"]
        assert list(event_types) == ["ttl"]
        assert event_types["ttl"]["column_name"] == "ttl"

    def test_labeled_metadata_keyed_by_file_stem(self, two_type_file):
        interface = CSVEventsInterface(
            file_path=two_type_file, timestamps_column="onset", event_type_column="kind", metadata_key="my_events"
        )
        event_types = interface.get_metadata()["Events"]["my_events"]["event_types"]
        assert list(event_types) == ["events"]
        assert event_types["events"]["column_categories"]["labels"] == {"a": "a", "b": "b"}

    def test_single_type_writes_one_events_object(self, interface):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        ttl_events = nwbfile.acquisition["ttl"]
        assert isinstance(ttl_events, ndx_events.Events)
        assert list(ttl_events.timestamps[:]) == SINGLE_TYPE_TIMESTAMPS

    def test_event_type_column_writes_labeled_events(self, two_type_file):
        interface = CSVEventsInterface(file_path=two_type_file, timestamps_column="onset", event_type_column="kind")
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        labeled = nwbfile.acquisition["events"]
        assert isinstance(labeled, ndx_events.LabeledEvents)
        assert list(labeled.timestamps[:]) == EXPECTED_LABELED_TIMESTAMPS
        assert list(labeled.data[:]) == EXPECTED_LABELED_DATA
        assert list(labeled.labels) == EXPECTED_LABELS

    def test_headerless_int_columns_write_labeled_events(self, headerless_two_type_file):
        interface = CSVEventsInterface(file_path=headerless_two_type_file, timestamps_column=0, event_type_column=1)
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        labeled = nwbfile.acquisition["events_headerless"]
        assert isinstance(labeled, ndx_events.LabeledEvents)
        assert list(labeled.timestamps[:]) == EXPECTED_LABELED_TIMESTAMPS
        assert list(labeled.data[:]) == EXPECTED_LABELED_DATA
        assert list(labeled.labels) == EXPECTED_LABELS

    def test_missing_timestamps_are_dropped(self, single_type_file_with_nans):
        interface = CSVEventsInterface(
            file_path=single_type_file_with_nans, timestamps_column="timestamps", event_type_column=None
        )
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        ttl_events = nwbfile.acquisition["ttl"]
        assert list(ttl_events.timestamps[:]) == [1.5, 3.5, 5.5]

    def test_missing_timestamps_emit_warning(self, two_type_file_with_nans):
        interface = CSVEventsInterface(
            file_path=two_type_file_with_nans, timestamps_column="onset", event_type_column="kind"
        )
        with pytest.warns(UserWarning, match="Dropped 2 row"):
            interface.get_metadata()

    def test_missing_timestamps_drop_labels_in_step(self, two_type_file_with_nans):
        interface = CSVEventsInterface(
            file_path=two_type_file_with_nans, timestamps_column="onset", event_type_column="kind"
        )
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        labeled = nwbfile.acquisition["events"]
        # Only the three "a" rows survive; "b" never appears in the vocabulary.
        assert list(labeled.timestamps[:]) == [1.0, 3.0, 5.0]
        assert list(labeled.data[:]) == [0, 0, 0]
        assert list(labeled.labels) == ["a"]

    def test_non_numeric_timestamps_are_dropped(self, tmp_path):
        # A stray header artifact and a garbage token in the timestamps column coerce to NaN and are
        # dropped along with their labels; the surviving 'None'/'null' labels stay literal.
        file_path = tmp_path / "reward.csv"
        file_path.write_text("onset,reward\n1.0,small\nbad,None\n3.0,null\n---,large\n5.0,small\n")
        interface = CSVEventsInterface(file_path=file_path, timestamps_column="onset", event_type_column="reward")
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        labeled = nwbfile.acquisition["reward"]
        # Rows 'bad' and '---' drop out; 'None' and 'large' never enter the vocabulary.
        assert list(labeled.timestamps[:]) == [1.0, 3.0, 5.0]
        assert list(labeled.labels) == ["small", "null"]
        assert list(labeled.data[:]) == [0, 1, 0]

    def test_na_like_label_tokens_are_read_literally(self, tmp_path):
        # 'None', 'NA', 'null' and a blank cell are real, distinct category values here; the default
        # keep_default_na=False must keep them apart instead of collapsing them into one nan label.
        file_path = tmp_path / "reward.csv"
        file_path.write_text("onset,reward\n1.0,small\n2.0,None\n3.0,NA\n4.0,null\n5.0,\n6.0,large\n")
        interface = CSVEventsInterface(file_path=file_path, timestamps_column="onset", event_type_column="reward")
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        labeled = nwbfile.acquisition["reward"]
        assert list(labeled.timestamps[:]) == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        assert list(labeled.labels) == ["small", "None", "NA", "null", "", "large"]
        assert list(labeled.data[:]) == [0, 1, 2, 3, 4, 5]

    def test_read_kwargs_forwarded_to_read_csv(self, tmp_path):
        # A ';' separator with ',' as the decimal mark: only reachable through read_kwargs.
        file_path = tmp_path / "ttl.csv"
        file_path.write_text("onset;kind\n1,5;a\n2,5;b\n")
        interface = CSVEventsInterface(
            file_path=file_path,
            timestamps_column="onset",
            event_type_column="kind",
            read_kwargs={"sep": ";", "decimal": ","},
        )
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        labeled = nwbfile.acquisition["ttl"]
        assert list(labeled.timestamps[:]) == [1.5, 2.5]
        assert list(labeled.labels) == ["a", "b"]

    def test_round_trip(self, interface, tmp_path):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = tmp_path / "test_csv_events.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()
            read_events = read_nwbfile.acquisition["ttl"]
            assert isinstance(read_events, ndx_events.Events)
            assert list(read_events.timestamps[:]) == SINGLE_TYPE_TIMESTAMPS
