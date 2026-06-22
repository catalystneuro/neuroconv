import ndx_events
import numpy as np
import pytest
from jsonschema.validators import Draft7Validator
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import NPMEventsInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH

NPM_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "NPM" / "sampleData_NPM_4"

# Onset times (in the raw Timestamp time base, seconds) and their type labels from
# PagCeAVgatFear_1442_ts0.csv. The second column holds boolean True/False annotations, which split
# into two event stores of five timestamps each.
EXPECTED_VALUE_TO_TIMESTAMPS = {
    "True": [24233.706688, 24348.892736, 24440.805728, 24558.94976, 24656.243808],
    "False": [24261.742688, 24376.91072, 24468.843712, 24586.99376, 24684.305792],
}


class TestNPMEventsInterface:
    @pytest.fixture
    def interface(self):
        return NPMEventsInterface(folder_path=NPM_FOLDER)

    def test_discovers_two_column_event_csv(self, interface):
        """Auto-discovery picks the two-column event CSV; the multi-column raw signal CSV is
        excluded (it belongs to the fiber photometry interface)."""
        assert [path.name for path in interface._event_file_paths()] == ["PagCeAVgatFear_1442_ts0.csv"]

    def test_get_metadata_does_not_set_session_start_time(self, interface):
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") is None

    def test_default_event_metadata_splits_by_label(self, interface):
        events_metadata = interface.get_metadata()["Behavior"]["NPMEvents"]["Events"]
        assert [event["value"] for event in events_metadata] == list(EXPECTED_VALUE_TO_TIMESTAMPS)
        assert all(event["name"] == event["value"] for event in events_metadata)

    def test_metadata_schema_is_valid(self, interface):
        Draft7Validator.check_schema(interface.get_metadata_schema())

    def test_original_timestamps(self, interface):
        original_timestamps = interface.get_original_timestamps()
        assert set(original_timestamps) == set(EXPECTED_VALUE_TO_TIMESTAMPS)
        for value, expected in EXPECTED_VALUE_TO_TIMESTAMPS.items():
            np.testing.assert_allclose(original_timestamps[value], expected, rtol=1e-12)

    def test_time_unit_scaling(self):
        """A millisecond time unit divides the raw onset times by 1000."""
        interface = NPMEventsInterface(folder_path=NPM_FOLDER, time_unit="milliseconds")
        timestamps = interface.get_original_timestamps()
        np.testing.assert_allclose(timestamps["True"], np.array(EXPECTED_VALUE_TO_TIMESTAMPS["True"]) / 1e3, rtol=1e-12)

    def test_set_aligned_starting_time(self, interface):
        """Shifting by minus the first onset time places the first event at zero."""
        first_timestamp = EXPECTED_VALUE_TO_TIMESTAMPS["True"][0]
        interface.set_aligned_starting_time(aligned_starting_time=-first_timestamp)
        timestamps = interface.get_timestamps()
        np.testing.assert_allclose(timestamps["True"][0], 0.0, atol=1e-6)
        np.testing.assert_allclose(
            timestamps["False"][0],
            EXPECTED_VALUE_TO_TIMESTAMPS["False"][0] - first_timestamp,
            rtol=1e-9,
        )

    def test_add_to_nwbfile_writes_one_events_object_per_label(self, interface):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        behavior_module = nwbfile.processing["behavior"]
        assert set(behavior_module.data_interfaces) == set(EXPECTED_VALUE_TO_TIMESTAMPS)
        for value, expected in EXPECTED_VALUE_TO_TIMESTAMPS.items():
            events = behavior_module.data_interfaces[value]
            assert isinstance(events, ndx_events.Events)
            np.testing.assert_allclose(list(events.timestamps[:]), expected, rtol=1e-12)

    def test_round_trip(self, interface, tmp_path):
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = tmp_path / "test_npm_events.nwb"
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()
            read_events = read_nwbfile.processing["behavior"].data_interfaces["True"]
            assert isinstance(read_events, ndx_events.Events)
            np.testing.assert_allclose(
                list(read_events.timestamps[:]), EXPECTED_VALUE_TO_TIMESTAMPS["True"], rtol=1e-12
            )
