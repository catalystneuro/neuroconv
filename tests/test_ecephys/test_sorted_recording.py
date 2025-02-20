import pytest

from neuroconv.converters import SortedRecordingConverter
from neuroconv.tools.testing.mock_interfaces import (
    MockRecordingInterface,
    MockSortingInterface,
)


class TestSortedRecordingConverter:

    def basic_test(self):

        recording_interface = MockRecordingInterface(num_channels=4, durations=[0.100])
        recording_extractor = recording_interface.recording_extractor
        recording_extractor = recording_extractor.rename_channels(new_channel_ids=["A", "B", "C"])
        recording_interface.recording_extractor = recording_extractor

        sorting_interface = MockSortingInterface(num_units=5, durations=[0.100])
        sorting_extractor = sorting_interface.sorting_extractor
        sorting_extractor = sorting_extractor.rename_units(new_unit_ids=["a", "b", "c", "d", "e"])
        sorting_interface.sorting_extractor = sorting_extractor

        unit_ids_to_channel_ids = {
            "a": ["A"],
            "b": ["B"],
            "c": ["C"],
            "d": ["A", "B"],
            "e": ["C", "A"],
        }
        sorted_recording_interface = SortedRecordingConverter(
            recording_interface=recording_interface,
            sorting_interface=sorting_interface,
            unit_ids_to_channel_ids=unit_ids_to_channel_ids,
        )

        nwbfile = sorted_recording_interface.create_nwbfile()

        # Test that the region in the units table points to the correct electrodes
        expected_unit_electrode_indices = {
            "a": [0],
            "b": [1],
            "c": [2],
            "d": [0, 1],
            "e": [2, 0],
        }
        unit_table = nwbfile.units
        for unit_row in unit_table.to_dataframe().itertuples(index=False):

            # Neuroconv write unit_ids as unit_names
            unit_id = unit_row.unit_name

            unit_electrode_table_region = unit_row.electrodes
            expected_unit_electrode_indices = expected_unit_electrode_indices[unit_id]
            assert unit_electrode_table_region == expected_unit_electrode_indices

    def test_invalid_channel_mapping(self):
        """Test that invalid channel mappings raise appropriate errors."""
        recording_interface = MockRecordingInterface(num_channels=4, durations=[0.100])
        recording_extractor = recording_interface.recording_extractor
        recording_extractor = recording_extractor.rename_channels(new_channel_ids=["ch1", "ch2", "ch3", "ch4"])
        recording_interface.recording_extractor = recording_extractor

        sorting_interface = MockSortingInterface(num_units=3, durations=[0.100])
        sorting_extractor = sorting_interface.sorting_extractor
        sorting_extractor = sorting_extractor.rename_units(new_unit_ids=["unit1", "unit2", "unit3"])
        sorting_interface.sorting_extractor = sorting_extractor

        # Test mapping with non-existent channel
        invalid_channel_mapping = {"unit1": ["ch1", "ch5"], "unit2": ["ch2"], "unit3": ["ch3"]}  # ch5 doesn't exist

        with pytest.raises(ValueError, match="Inexistent channel IDs {'ch5'} referenced in mapping for unit unit1"):
            SortedRecordingConverter(
                recording_interface=recording_interface,
                sorting_interface=sorting_interface,
                unit_ids_to_channel_ids=invalid_channel_mapping,
            )

        # Test mapping missing some units
        incomplete_mapping = {
            "unit1": ["ch1"],
            "unit2": ["ch2"],
            # unit3 is missing
        }

        with pytest.raises(ValueError, match="Units {'unit3'} from sorting interface have no channel mapping"):
            SortedRecordingConverter(
                recording_interface=recording_interface,
                sorting_interface=sorting_interface,
                unit_ids_to_channel_ids=incomplete_mapping,
            )
