from datetime import datetime

import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import EDFAnalogInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class TestEDFAnalogInterface:
    """Test suite for EDFAnalogInterface."""

    def test_interface_initialization_with_specific_channels(self):
        """
        Test initialization of EDFAnalogInterface with specific non-electrode channels.
        """
        file_path = ECEPHY_DATA_PATH / "edf" / "electrode_and_analog_data" / "electrode_and_analog_data.edf"

        # Get all available channels using static method
        available_channels = EDFAnalogInterface.get_available_channel_ids(file_path)

        # Define expected non-electrode channels
        expected_non_electrode_channels = ["TRIG", "OSAT", "PR", "Pleth"]

        # Test that expected channels are in available channels
        available_channels_set = set(available_channels)
        for channel in expected_non_electrode_channels:
            assert channel in available_channels_set, f"Expected channel {channel} not found in available channels"

        # Test that we can pass them and get them back
        interface = EDFAnalogInterface(file_path=file_path, channels_to_include=expected_non_electrode_channels)

        interface_channel_ids = interface.channel_ids
        assert len(interface_channel_ids) == len(expected_non_electrode_channels)

        # Convert to sets for comparison since order might differ
        expected_set = set(expected_non_electrode_channels)
        actual_set = set(str(ch_id) for ch_id in interface_channel_ids)
        assert actual_set == expected_set

    def test_invalid_channels_raises_error(self):
        """Test that specifying non-existent channels raises ValueError."""
        file_path = ECEPHY_DATA_PATH / "edf" / "electrode_and_analog_data" / "electrode_and_analog_data.edf"

        with pytest.raises(ValueError, match="Channels not found in EDF file"):
            EDFAnalogInterface(file_path=file_path, channels_to_include=["NonExistentChannel"])

    def test_custom_metadata_key(self):
        """Test custom metadata key."""
        file_path = ECEPHY_DATA_PATH / "edf" / "electrode_and_analog_data" / "electrode_and_analog_data.edf"
        custom_key = "CustomEDFTimeSeries"

        interface = EDFAnalogInterface(file_path=file_path, metadata_key=custom_key)
        assert interface.metadata_key == custom_key

        # Check that metadata uses the custom key
        metadata = interface.get_metadata()
        assert "TimeSeries" in metadata
        assert custom_key in metadata["TimeSeries"]

    def test_get_metadata(self):
        """Test metadata generation for EDF file."""
        file_path = ECEPHY_DATA_PATH / "edf" / "electrode_and_analog_data" / "electrode_and_analog_data.edf"
        interface = EDFAnalogInterface(file_path=file_path)
        metadata = interface.get_metadata()

        assert "TimeSeries" in metadata
        assert interface.metadata_key in metadata["TimeSeries"]

        # Check TimeSeries metadata structure
        ts_metadata = metadata["TimeSeries"][interface.metadata_key]
        assert "name" in ts_metadata
        assert "description" in ts_metadata
        assert "Non-electrical analog signals from EDF file" in ts_metadata["description"]

    def test_conversion_to_nwb(self, tmp_path):
        """Test conversion to NWB format."""
        file_path = ECEPHY_DATA_PATH / "edf" / "electrode_and_analog_data" / "electrode_and_analog_data.edf"
        interface = EDFAnalogInterface(file_path=file_path)

        # Get metadata and add required session_start_time
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        # Run conversion
        nwbfile_path = tmp_path / "edf_analog_test.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        # Verify the output
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            # Check that the TimeSeries was added to acquisition
            assert interface._time_series_name in nwbfile.acquisition
            time_series = nwbfile.acquisition[interface._time_series_name]

            # Check properties of the TimeSeries
            assert time_series.name == interface._time_series_name
            assert "Non-electrical analog signals from EDF file" in time_series.description

            # Check data dimensions
            assert len(time_series.data.shape) == 2  # [time, channels]
            assert time_series.data.shape[1] == len(interface.channel_ids)
            assert time_series.data.shape[0] > 0  # Should have time points

    def test_stub_conversion(self, tmp_path):
        """Test stub conversion."""
        file_path = ECEPHY_DATA_PATH / "edf" / "electrode_and_analog_data" / "electrode_and_analog_data.edf"
        interface = EDFAnalogInterface(file_path=file_path)

        # Get metadata and add required session_start_time
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        # Run stub conversion
        nwbfile_path = tmp_path / "edf_analog_stub_test.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True, stub_test=True)

        # Verify the output
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            # Check that the TimeSeries was added
            assert interface._time_series_name in nwbfile.acquisition
            time_series = nwbfile.acquisition[interface._time_series_name]

            # Check that data is present but smaller (stub)
            assert len(time_series.data.shape) == 2
            assert time_series.data.shape[0] > 0  # Should have some time points
            assert time_series.data.shape[1] == len(interface.channel_ids)
