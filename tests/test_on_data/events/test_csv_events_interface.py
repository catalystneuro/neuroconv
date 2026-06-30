import ndx_events
import pytest
from jsonschema.validators import Draft7Validator
from pydantic import ValidationError
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import CSVEventsInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH

CSV_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "CSV" / "sample_data_csv_1"
SAMPLE_TTL_FILE = CSV_FOLDER / "Sample_TTL.csv"

# Onset times in Sample_TTL.csv (a single-column ``timestamps`` event file).
EXPECTED_TTL_TIMESTAMPS = [
    139.238440990448,
    190.68911623954773,
    270.35009026527405,
    330.88094210624695,
    410.86189556121826,
]

# A two-type event file: onset times tagged by a "kind" label. Written as one LabeledEvents with
# the onsets in file order plus a per-event code into the label vocabulary. Labels are ordered by
# first appearance: "a" (code 0) before "b" (code 1).
TWO_TYPE_ROWS = [(1.0, "a"), (2.0, "b"), (3.0, "a"), (4.0, "b"), (5.0, "a")]
EXPECTED_LABELED_TIMESTAMPS = [1.0, 2.0, 3.0, 4.0, 5.0]
EXPECTED_LABELED_DATA = [0, 1, 0, 1, 0]
EXPECTED_LABELS = ["a", "b"]


class TestCSVEventsInterface:
    @pytest.fixture
    def interface(self):
        return CSVEventsInterface(file_path=SAMPLE_TTL_FILE, timestamps_column="timestamps", event_type_column=None)

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

    def test_event_type_column_is_required(self):
        """event_type_column has no default, so omitting it is an error."""
        with pytest.raises(ValidationError):
            CSVEventsInterface(file_path=SAMPLE_TTL_FILE, timestamps_column="timestamps")

    def test_get_metadata_does_not_set_session_start_time(self, interface):
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") is None

    def test_metadata_schema_is_valid(self, interface):
        Draft7Validator.check_schema(interface.get_metadata_schema())

    def test_single_type_metadata_keyed_by_file_stem(self, interface):
        event_columns = interface.get_metadata()["Events"]["csv_events"]["event_columns"]
        assert list(event_columns) == ["Sample_TTL"]
        assert event_columns["Sample_TTL"]["column_name"] == "Sample_TTL"

    def test_labeled_metadata_keyed_by_file_stem(self, two_type_file):
        interface = CSVEventsInterface(
            file_path=two_type_file, timestamps_column="onset", event_type_column="kind", metadata_key="my_events"
        )
        event_columns = interface.get_metadata()["Events"]["my_events"]["event_columns"]
        assert list(event_columns) == ["events"]
        assert event_columns["events"]["column_categories"]["labels"] == {"a": "a", "b": "b"}

    def test_single_type_writes_one_events_object(self, interface):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        ttl_events = nwbfile.acquisition["Sample_TTL"]
        assert isinstance(ttl_events, ndx_events.Events)
        assert list(ttl_events.timestamps[:]) == EXPECTED_TTL_TIMESTAMPS

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

    def test_round_trip(self, interface, tmp_path):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = tmp_path / "test_csv_events.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()
            read_events = read_nwbfile.acquisition["Sample_TTL"]
            assert isinstance(read_events, ndx_events.Events)
            assert list(read_events.timestamps[:]) == EXPECTED_TTL_TIMESTAMPS
