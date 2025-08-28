import pytest

from neuroconv.datainterfaces.ecephys.sorted_converter import _SortedConverterPipe
from neuroconv.nwbconverter import ConverterPipe
from neuroconv.tools.testing.mock_interfaces import (
    MockRecordingInterface,
    MockSortingInterface,
)


class TestSortedConverterPipe:

    def test_multi_interface_with_unique_unit_ids(self):
        """Test _SortedConverterPipe with multiple interfaces and unique unit IDs."""
        # Create first recording interface
        recording1 = MockRecordingInterface(num_channels=4, durations=[0.100])
        recording1.recording_extractor = recording1.recording_extractor.rename_channels(["A1", "A2", "A3", "A4"])

        # Create second recording interface
        recording2 = MockRecordingInterface(num_channels=3, durations=[0.100])
        recording2.recording_extractor = recording2.recording_extractor.rename_channels(["B1", "B2", "B3"])
        # Set different es_key to avoid naming conflicts
        recording2.es_key = "ElectricalSeries2"

        # Create sorting interfaces with unique unit IDs
        sorting1 = MockSortingInterface(num_units=2, durations=[0.100])
        sorting1.sorting_extractor = sorting1.sorting_extractor.rename_units(["unit_a", "unit_b"])

        sorting2 = MockSortingInterface(num_units=2, durations=[0.100])
        sorting2.sorting_extractor = sorting2.sorting_extractor.rename_units(["unit_c", "unit_d"])

        # Create a mock converter with both interfaces
        mock_converter = ConverterPipe(data_interfaces={"interface1": recording1, "interface2": recording2})

        sorting_configuration = [
            {
                "interface_name": "interface1",
                "sorting_interface": sorting1,
                "unit_ids_to_channel_ids": {"unit_a": ["A1", "A2"], "unit_b": ["A3", "A4"]},
            },
            {
                "interface_name": "interface2",
                "sorting_interface": sorting2,
                "unit_ids_to_channel_ids": {"unit_c": ["B1"], "unit_d": ["B2", "B3"]},
            },
        ]

        converter = _SortedConverterPipe(converter=mock_converter, sorting_configuration=sorting_configuration)

        # Create NWB file and test
        nwbfile = converter.create_nwbfile()
        units_df = nwbfile.units.to_dataframe()

        # Should have 4 units total with original names (no conflicts)
        assert len(units_df) == 4
        unit_names = set(units_df["unit_name"])
        assert unit_names == {"unit_a", "unit_b", "unit_c", "unit_d"}

    def test_multi_interface_with_non_unique_unit_ids(self):
        """Test that _SortedConverterPipe handles non-unique unit IDs across interfaces."""
        # Create recording interfaces
        recording1 = MockRecordingInterface(num_channels=4, durations=[0.100])
        recording1.recording_extractor = recording1.recording_extractor.rename_channels(["A1", "A2", "A3", "A4"])

        recording2 = MockRecordingInterface(num_channels=3, durations=[0.100])
        recording2.recording_extractor = recording2.recording_extractor.rename_channels(["B1", "B2", "B3"])
        # Set different es_key to avoid naming conflicts
        recording2.es_key = "ElectricalSeries2"

        # Create sorting interfaces with overlapping unit IDs
        sorting1 = MockSortingInterface(num_units=2, durations=[0.100])
        # Keep default unit IDs ("0", "1") to create conflicts

        sorting2 = MockSortingInterface(num_units=2, durations=[0.100])
        # Keep default unit IDs ("0", "1") to create conflicts

        # Create a mock converter with both interfaces
        mock_converter = ConverterPipe(data_interfaces={"interface1": recording1, "interface2": recording2})

        sorting_configuration = [
            {
                "interface_name": "interface1",
                "sorting_interface": sorting1,
                "unit_ids_to_channel_ids": {"0": ["A1", "A2"], "1": ["A3", "A4"]},
            },
            {
                "interface_name": "interface2",
                "sorting_interface": sorting2,
                "unit_ids_to_channel_ids": {"0": ["B1"], "1": ["B2", "B3"]},
            },
        ]

        converter = _SortedConverterPipe(converter=mock_converter, sorting_configuration=sorting_configuration)

        # Create NWB file and test
        nwbfile = converter.create_nwbfile()
        units_df = nwbfile.units.to_dataframe()

        # Should have 4 units total with renamed units due to conflicts
        assert len(units_df) == 4
        unit_names = set(units_df["unit_name"])
        expected_names = {"interface1_unit_0", "interface1_unit_1", "interface2_unit_0", "interface2_unit_1"}
        assert unit_names == expected_names

    def test_empty_sorting_configuration_error(self):
        """Test that empty sorting configuration raises appropriate error."""
        mock_converter = ConverterPipe(
            data_interfaces={"probe1": MockRecordingInterface(num_channels=4, durations=[0.100])}
        )

        with pytest.raises(ValueError, match="_SortedConverterPipe requires at least one sorting configuration"):
            _SortedConverterPipe(converter=mock_converter, sorting_configuration=[])

    def test_non_existent_interface_error(self):
        """Test that referencing non-existent interface raises error."""
        mock_converter = ConverterPipe(
            data_interfaces={"probe1": MockRecordingInterface(num_channels=4, durations=[0.100])}
        )
        sorting_configuration = [
            {
                "interface_name": "probe2",  # This interface doesn't exist
                "sorting_interface": MockSortingInterface(num_units=2, durations=[0.100]),
                "unit_ids_to_channel_ids": {"0": ["ch1"], "1": ["ch2"]},
            }
        ]

        with pytest.raises(ValueError, match="Interface 'probe2' not found in recording_interfaces"):
            _SortedConverterPipe(converter=mock_converter, sorting_configuration=sorting_configuration)

    def test_invalid_channel_mapping(self):
        """Test that invalid channel mappings raise appropriate errors."""
        recording_interface = MockRecordingInterface(num_channels=4, durations=[0.100])
        recording_interface.recording_extractor = recording_interface.recording_extractor.rename_channels(
            ["ch1", "ch2", "ch3", "ch4"]
        )

        sorting_interface = MockSortingInterface(num_units=2, durations=[0.100])
        sorting_interface.sorting_extractor = sorting_interface.sorting_extractor.rename_units(["unit1", "unit2"])

        mock_converter = ConverterPipe(data_interfaces={"probe1": recording_interface})

        # Test mapping with non-existent channel
        invalid_channel_mapping = [
            {
                "interface_name": "probe1",
                "sorting_interface": sorting_interface,
                "unit_ids_to_channel_ids": {"unit1": ["ch1", "ch5"], "unit2": ["ch2"]},  # ch5 doesn't exist
            }
        ]

        with pytest.raises(ValueError, match="Inexistent channel IDs {'ch5'} referenced in mapping for unit unit1"):
            _SortedConverterPipe(converter=mock_converter, sorting_configuration=invalid_channel_mapping)

    def test_incomplete_unit_mapping(self):
        """Test that incomplete unit mappings raise appropriate errors."""
        recording_interface = MockRecordingInterface(num_channels=4, durations=[0.100])
        recording_interface.recording_extractor = recording_interface.recording_extractor.rename_channels(
            ["ch1", "ch2", "ch3", "ch4"]
        )

        sorting_interface = MockSortingInterface(num_units=3, durations=[0.100])
        sorting_interface.sorting_extractor = sorting_interface.sorting_extractor.rename_units(
            ["unit1", "unit2", "unit3"]
        )

        mock_converter = ConverterPipe(data_interfaces={"probe1": recording_interface})

        # Test mapping missing some units
        incomplete_mapping = [
            {
                "interface_name": "probe1",
                "sorting_interface": sorting_interface,
                "unit_ids_to_channel_ids": {
                    "unit1": ["ch1"],
                    "unit2": ["ch2"],
                    # unit3 is missing
                },
            }
        ]

        with pytest.raises(ValueError, match="Units {'unit3'} from sorting interface have no channel mapping"):
            _SortedConverterPipe(converter=mock_converter, sorting_configuration=incomplete_mapping)
