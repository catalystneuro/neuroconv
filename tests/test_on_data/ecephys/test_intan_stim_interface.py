from datetime import datetime

import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import IntanStimInterface

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class TestIntanStimInterface:
    """Test suite for IntanStimInterface."""

    def test_initialization_single_file_format(self):
        """Test initialization with a single-file RHS recording containing stim channels."""
        file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
        interface = IntanStimInterface(file_path=file_path)

        assert interface._stream_name == "Stim channel"
        assert interface.recording_extractor is not None

    def test_initialization_file_per_channel_format(self):
        """Test initialization with a file-per-channel RHS recording."""
        file_path = ECEPHY_DATA_PATH / "intan" / "test_fpc_stim_250327_151617" / "info.rhs"
        interface = IntanStimInterface(file_path=file_path)

        assert interface._stream_name == "Stim channel"
        assert interface.recording_extractor is not None

    def test_initialization_file_per_signal_format_multistim(self):
        """Test initialization with a multi-stim file-per-signal RHS recording."""
        file_path = (
            ECEPHY_DATA_PATH / "intan" / "rhs_fpc_multistim_240514_082243" / "rhs_fpc_multistim_240514_082243.rhs"
        )
        interface = IntanStimInterface(file_path=file_path)

        assert interface.recording_extractor is not None

    def test_rhd_file_raises_error(self):
        """Test that .rhd files raise a ValueError since stim channels are RHS-only."""
        file_path = ECEPHY_DATA_PATH / "intan" / "intan_fps_test_231117_052500" / "info.rhd"

        with pytest.raises(ValueError, match="only supports .rhs files"):
            IntanStimInterface(file_path=file_path)

    def test_channel_names_follow_stim_pattern(self):
        """Test that channel names follow the {amplifier_channel}_STIM naming convention."""
        file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
        interface = IntanStimInterface(file_path=file_path)
        channel_names = interface.get_channel_names()

        assert isinstance(channel_names, list)
        assert len(channel_names) > 0
        assert all(isinstance(name, str) for name in channel_names)
        assert all(name.endswith("_STIM") for name in channel_names)

    def test_channel_names_small_dataset(self):
        """Test channel count for a small dataset with 4 stim channels."""
        file_path = ECEPHY_DATA_PATH / "intan" / "test_fpc_stim_250327_151617" / "info.rhs"
        interface = IntanStimInterface(file_path=file_path)
        channel_names = interface.get_channel_names()

        assert len(channel_names) == 4

    def test_custom_metadata_key(self):
        """Test that a custom metadata_key is accepted and stored."""
        file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
        custom_key = "MyStimTimeSeries"

        interface = IntanStimInterface(file_path=file_path, metadata_key=custom_key)
        assert interface.metadata_key == custom_key

        metadata = interface.get_metadata()
        assert "TimeSeries" in metadata
        assert custom_key in metadata["TimeSeries"]

    def test_get_metadata_structure(self):
        """Test that get_metadata returns expected device and TimeSeries entries."""
        file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
        interface = IntanStimInterface(file_path=file_path)
        metadata = interface.get_metadata()

        assert "Devices" in metadata
        assert "TimeSeries" in metadata

        device = metadata["Devices"][0]
        assert device["name"] == "Intan"
        assert device["manufacturer"] == "Intan"
        assert "RHS Stim/Recording System" in device["description"]

        ts_meta = metadata["TimeSeries"][interface.metadata_key]
        assert ts_meta["name"] == "TimeSeriesIntanStim"
        assert "Amperes" in ts_meta["description"] or "amperes" in ts_meta["description"].lower()

    def test_conversion_to_nwb_units_are_amperes(self, tmp_path):
        """Test that converted NWB file stores stim data with unit='A' (Amperes)."""
        file_path = ECEPHY_DATA_PATH / "intan" / "test_fpc_stim_250327_151617" / "info.rhs"
        interface = IntanStimInterface(file_path=file_path)

        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        nwbfile_path = tmp_path / "intan_stim_test.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            assert "TimeSeriesIntanStim" in nwbfile.acquisition
            time_series = nwbfile.acquisition["TimeSeriesIntanStim"]

            assert time_series.unit == "A"
            assert len(time_series.data.shape) == 2
            assert time_series.data.shape[0] > 0
            assert time_series.data.shape[1] == len(interface.get_channel_names())

    def test_stub_conversion(self, tmp_path):
        """Test stub conversion writes a smaller dataset."""
        file_path = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
        interface = IntanStimInterface(file_path=file_path)

        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        nwbfile_path = tmp_path / "intan_stim_stub_test.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True, stub_test=True)

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            assert "TimeSeriesIntanStim" in nwbfile.acquisition
            time_series = nwbfile.acquisition["TimeSeriesIntanStim"]

            assert len(time_series.data.shape) == 2
            assert time_series.data.shape[1] == len(interface.get_channel_names())
            # Stub should be smaller than full dataset (100 samples)
            assert time_series.data.shape[0] <= 100
