import ndx_events
import pytest
from jsonschema.validators import Draft7Validator
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import CSVEventsInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH

CSV_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "CSV" / "sample_data_csv_1"

# Onset times in Sample_TTL.csv (the single event CSV in the folder).
EXPECTED_TTL_TIMESTAMPS = [
    139.238440990448,
    190.68911623954773,
    270.35009026527405,
    330.88094210624695,
    410.86189556121826,
]


class TestCSVEventsInterface:
    @pytest.fixture
    def interface(self):
        return CSVEventsInterface(folder_path=CSV_FOLDER)

    def test_default_event_names_discovers_only_event_csv(self, interface):
        """Auto-discovery picks the single-column TTL CSV and excludes the data CSVs."""
        assert interface._get_event_names() == ["Sample_TTL"]

    def test_get_metadata_does_not_set_session_start_time(self, interface):
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") is None

    def test_default_event_metadata(self, interface):
        events_metadata = interface.get_metadata()["Behavior"]["CSVEvents"]["Events"]
        assert len(events_metadata) == 1
        event = events_metadata[0]
        assert event["file_name"] == "Sample_TTL"
        assert event["name"] == "Sample_TTL"

    def test_selected_event_names(self):
        interface = CSVEventsInterface(folder_path=CSV_FOLDER, event_names=["Sample_TTL"])
        events_metadata = interface.get_metadata()["Behavior"]["CSVEvents"]["Events"]
        assert [event["file_name"] for event in events_metadata] == ["Sample_TTL"]

    def test_metadata_schema_is_valid(self, interface):
        Draft7Validator.check_schema(interface.get_metadata_schema())

    def test_add_to_nwbfile_writes_events(self, interface):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        behavior_module = nwbfile.processing["behavior"]
        ttl_events = behavior_module.data_interfaces["Sample_TTL"]
        assert isinstance(ttl_events, ndx_events.Events)
        assert list(ttl_events.timestamps[:]) == EXPECTED_TTL_TIMESTAMPS

    def test_round_trip(self, interface, tmp_path):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = tmp_path / "test_csv_events.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()
            read_events = read_nwbfile.processing["behavior"].data_interfaces["Sample_TTL"]
            assert isinstance(read_events, ndx_events.Events)
            assert list(read_events.timestamps[:]) == EXPECTED_TTL_TIMESTAMPS
