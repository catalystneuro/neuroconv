from datetime import datetime

import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import IntanAnalogInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

if not ECEPHY_DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {ECEPHY_DATA_PATH}!")


class TestIntanAnalogInterface:
    """Test suite for IntanAnalogInterface."""

    def test_interface_initialization_adc_stream_rhs_stim_data(self):
        """
        Test initialization of IntanAnalogInterface with ADC stream using RHS stim data.
        """
        file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
        interface = IntanAnalogInterface(file_path=file_path, stream_name="USB board ADC input channel")

        assert interface.stream_name == "USB board ADC input channel"
        assert interface.time_series_name == "TimeSeriesIntanADCInput"
        assert interface.recording_extractor is not None

        # Should have 8 ADC channels according to the README
        channel_names = interface.get_channel_names()
        assert len(channel_names) == 8
        assert all("ANALOG-IN" in name for name in channel_names)

    def test_interface_initialization_dc_stream_rhs_data(self):
        """
        Test initialization of IntanAnalogInterface with DC amplifier stream using RHS data.
        """
        file_path = ECEPHY_DATA_PATH / "intan" / "test_fcs_dc_250327_154333" / "info.rhs"
        interface = IntanAnalogInterface(file_path=file_path, stream_name="DC Amplifier channel")

        assert interface.stream_name == "DC Amplifier channel"
        assert interface.time_series_name == "TimeSeriesIntanDC"
        assert interface.recording_extractor is not None

    def test_interface_initialization_auxiliary_stream_rhd_data(self):
        """
        Test initialization of IntanAnalogInterface with auxiliary stream using RHD data.
        """
        file_path = ECEPHY_DATA_PATH / "intan" / "intan_fps_test_231117_052500" / "info.rhd"
        interface = IntanAnalogInterface(file_path=file_path, stream_name="RHD2000 auxiliary input channel")

        assert interface.stream_name == "RHD2000 auxiliary input channel"
        assert interface.time_series_name == "TimeSeriesIntanAuxiliary"

    def test_interface_initialization_adc_stream_rhd_data(self):
        """
        Test initialization of IntanAnalogInterface with ADC stream using RHD data.
        """
        file_path = ECEPHY_DATA_PATH / "intan" / "intan_fpc_test_231117_052630" / "info.rhd"
        interface = IntanAnalogInterface(file_path=file_path, stream_name="USB board ADC input channel")

        assert interface.stream_name == "USB board ADC input channel"
        assert interface.time_series_name == "TimeSeriesIntanADCInput"

    def test_invalid_stream_name(self):
        """Test that invalid stream names raise appropriate errors."""
        file_path = ECEPHY_DATA_PATH / "intan" / "intan_fps_test_231117_052500" / "info.rhd"

        with pytest.raises(ValueError, match="Invalid stream_name"):
            IntanAnalogInterface(file_path=file_path, stream_name="Invalid Stream Name")

    def test_custom_time_series_metadata_key(self):
        """Test custom time series metadata key using RHS stim data with ADC channels."""
        file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
        custom_key = "CustomTimeSeries"

        interface = IntanAnalogInterface(
            file_path=file_path, stream_name="USB board ADC input channel", metadata_key=custom_key
        )
        assert interface.metadata_key == custom_key

        # Check that metadata uses the custom key
        metadata = interface.get_metadata()
        assert "TimeSeries" in metadata
        assert custom_key in metadata["TimeSeries"]

    def test_get_metadata_rhd_file(self):
        """Test metadata generation for RHD file."""
        file_path = ECEPHY_DATA_PATH / "intan" / "intan_fps_test_231117_052500" / "info.rhd"
        interface = IntanAnalogInterface(file_path=file_path, stream_name="RHD2000 auxiliary input channel")
        metadata = interface.get_metadata()

        assert "Devices" in metadata
        assert "TimeSeries" in metadata
        assert interface.metadata_key in metadata["TimeSeries"]
        assert interface.time_series_name in metadata["TimeSeries"][interface.metadata_key]

        # Check device metadata for RHD
        device = metadata["Devices"][0]
        assert device["name"] == "Intan"
        assert device["manufacturer"] == "Intan"
        assert "RHD Recording System" in device["description"]

    def test_get_metadata_rhs_file(self):
        """Test metadata generation for RHS file."""
        file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
        interface = IntanAnalogInterface(file_path=file_path, stream_name="USB board ADC input channel")
        metadata = interface.get_metadata()

        assert "Devices" in metadata
        assert "TimeSeries" in metadata
        assert interface.metadata_key in metadata["TimeSeries"]
        assert interface.time_series_name in metadata["TimeSeries"][interface.metadata_key]

        # Check device metadata for RHS
        device = metadata["Devices"][0]
        assert device["name"] == "Intan"
        assert device["manufacturer"] == "Intan"
        assert "RHS Stim/Recording System" in device["description"]

    def test_get_channel_names_adc_channels(self):
        """Test channel names retrieval for ADC channels in RHS stim data."""
        file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
        interface = IntanAnalogInterface(file_path=file_path, stream_name="USB board ADC input channel")
        channel_names = interface.get_channel_names()

        assert isinstance(channel_names, list)
        assert len(channel_names) == 8  # According to README: 8 ADC channels
        assert all(isinstance(name, str) for name in channel_names)
        assert all("ANALOG-IN" in name for name in channel_names)

    def test_conversion_to_nwb_adc_channels(self, tmp_path):
        """Test conversion to NWB format using RHS stim data with ADC channels."""
        file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
        interface = IntanAnalogInterface(file_path=file_path, stream_name="USB board ADC input channel")

        # Get metadata and add required session_start_time
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        # Run conversion
        nwbfile_path = tmp_path / "intan_analog_adc_test.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        # Verify the output
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            # Check that the TimeSeries was added to acquisition
            assert interface.time_series_name in nwbfile.acquisition
            time_series = nwbfile.acquisition[interface.time_series_name]

            # Check properties of the TimeSeries
            assert time_series.name == interface.time_series_name
            assert "USB board ADC input channels" in time_series.description

            # Check data dimensions - should have 8 ADC channels
            assert len(time_series.data.shape) == 2  # [time, channels]
            assert time_series.data.shape[1] == 8  # 8 ADC channels
            assert time_series.data.shape[0] > 0  # Should have time points

    def test_stub_conversion_dc_channels(self, tmp_path):
        """Test stub conversion using DC amplifier channels from RHS data."""
        file_path = ECEPHY_DATA_PATH / "intan" / "test_fcs_dc_250327_154333" / "info.rhs"
        interface = IntanAnalogInterface(file_path=file_path, stream_name="DC Amplifier channel")

        # Get metadata and add required session_start_time
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        # Run stub conversion
        nwbfile_path = tmp_path / "intan_analog_dc_stub_test.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True, stub_test=True)

        # Verify the output
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            # Check that the TimeSeries was added
            assert interface.time_series_name in nwbfile.acquisition
            time_series = nwbfile.acquisition[interface.time_series_name]

            # Check that data is present but smaller (stub)
            assert len(time_series.data.shape) == 2
            assert time_series.data.shape[0] > 0  # Should have some time points
            assert time_series.data.shape[1] == len(interface.get_channel_names())
            assert "DC amplifier channels" in time_series.description
