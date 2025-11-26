import numpy as np
import pytest
from pynwb import read_nwb

from neuroconv.datainterfaces import MiniscopeHeadOrientationInterface
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH

HAVE_TEST_DATA = (OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "dual_miniscope_with_config").exists()


@pytest.mark.skipif(not HAVE_TEST_DATA, reason="Test data not available")
class TestMiniscopeHeadOrientationInterface:
    """Test MiniscopeHeadOrientationInterface."""

    data_path = OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "dual_miniscope_with_config"
    headOrientation_file_path = (
        data_path
        / "researcher_name/experiment_name/animal_name"
        / "2025_06_12/15_26_31/HPC_miniscope1/headOrientation.csv"
    )

    def test_interface_initialization(self):
        """Test interface can be initialized with headOrientation.csv file."""
        interface = MiniscopeHeadOrientationInterface(file_path=self.headOrientation_file_path)

        assert interface is not None
        timestamps = interface.get_timestamps()
        assert len(timestamps) > 0

    def test_read_quaternion_data(self):
        """Test quaternion data is correctly read with 4 components."""
        interface = MiniscopeHeadOrientationInterface(file_path=self.headOrientation_file_path)

        quaternion_data = interface._quaternion_data
        assert quaternion_data.shape[1] == 4  # qw, qx, qy, qz
        assert quaternion_data.shape[0] == len(interface.get_timestamps())

    def test_metadata_generation(self):
        """Test metadata contains correct structure for head orientation."""
        interface = MiniscopeHeadOrientationInterface(file_path=self.headOrientation_file_path)
        metadata = interface.get_metadata()

        assert "TimeSeries" in metadata
        assert "TimeSeriesMiniscopeHeadOrientation" in metadata["TimeSeries"]
        timeseries_metadata = metadata["TimeSeries"]["TimeSeriesMiniscopeHeadOrientation"]
        assert timeseries_metadata["unit"] == "n.a."
        assert timeseries_metadata["name"] == "TimeSeriesMiniscopeHeadOrientation"

        # Check that description includes device information and quaternion convention
        description = timeseries_metadata["description"]
        assert "BNO055 IMU sensor" in description
        assert "Miniscope_V4_BNO" in description  # deviceType
        assert "HPC_miniscope1" in description  # deviceName
        assert "Hamilton" in description  # Quaternion convention

        # Check that session_start_time was extracted
        assert "NWBFile" in metadata
        assert "session_start_time" in metadata["NWBFile"]

    def test_nwb_conversion(self, tmp_path):
        """Test data is correctly written to NWB file."""
        from datetime import datetime

        interface = MiniscopeHeadOrientationInterface(file_path=self.headOrientation_file_path)
        metadata = interface.get_metadata()
        # Add required NWBFile metadata
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        nwbfile_path = tmp_path / "test_head_orientation.nwb"

        interface.run_conversion(
            nwbfile_path=nwbfile_path,
            metadata=metadata,
        )

        # Verify NWB structure
        nwbfile = read_nwb(nwbfile_path)

        assert "behavior" in nwbfile.processing
        behavior_module = nwbfile.processing["behavior"]
        assert "TimeSeriesMiniscopeHeadOrientation" in behavior_module.data_interfaces

        timeseries = behavior_module.data_interfaces["TimeSeriesMiniscopeHeadOrientation"]
        assert timeseries.data.shape[1] == 4  # quaternions
        assert timeseries.unit == "n.a."
        assert len(timeseries.timestamps) > 0

    def test_temporal_alignment(self):
        """Test temporal alignment methods work correctly."""
        interface = MiniscopeHeadOrientationInterface(file_path=self.headOrientation_file_path)

        original_timestamps = interface.get_original_timestamps()
        interface.set_aligned_starting_time(aligned_starting_time=10.0)
        aligned_timestamps = interface.get_timestamps()

        # All timestamps should be shifted by 10 seconds
        assert np.allclose(aligned_timestamps, original_timestamps + 10.0)

    def test_custom_metadata_key(self, tmp_path):
        """Test interface with custom metadata_key parameter."""
        from datetime import datetime

        custom_key = "CustomHeadOrientation"
        interface = MiniscopeHeadOrientationInterface(file_path=self.headOrientation_file_path, metadata_key=custom_key)

        # Verify metadata uses custom key
        metadata = interface.get_metadata()
        assert custom_key in metadata["TimeSeries"]
        assert metadata["TimeSeries"][custom_key]["name"] == custom_key

        # Verify NWB conversion uses custom key
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        nwbfile_path = tmp_path / "test_custom_metadata_key.nwb"

        interface.run_conversion(
            nwbfile_path=nwbfile_path,
            metadata=metadata,
        )

        # Verify custom key is used in NWB file
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        assert custom_key in behavior_module.data_interfaces
        assert behavior_module.data_interfaces[custom_key].name == custom_key

    def test_timestamps_writing_modes(self, tmp_path):
        """Test uniform timestamp detection and always_write_timestamps parameter."""
        from datetime import datetime

        from neuroconv.utils import calculate_regular_series_rate

        interface = MiniscopeHeadOrientationInterface(file_path=self.headOrientation_file_path)
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        # Check if timestamps are uniform
        timestamps = interface.get_timestamps()
        rate = calculate_regular_series_rate(series=timestamps)

        # Test default behavior (should use rate if timestamps are uniform)
        nwbfile_path_default = tmp_path / "test_default_timestamps.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path_default, metadata=metadata)

        nwbfile_default = read_nwb(nwbfile_path_default)
        timeseries_default = nwbfile_default.processing["behavior"].data_interfaces[
            "TimeSeriesMiniscopeHeadOrientation"
        ]

        # If timestamps are uniform, default should use rate; otherwise timestamps
        if rate:
            assert timeseries_default.rate is not None
            assert timeseries_default.starting_time is not None
        else:
            assert timeseries_default.timestamps is not None

        # Test always_write_timestamps=True (should always write explicit timestamps)
        nwbfile_path_forced = tmp_path / "test_forced_timestamps.nwb"
        interface.run_conversion(
            nwbfile_path=nwbfile_path_forced, metadata=metadata, overwrite=True, always_write_timestamps=True
        )

        nwbfile_forced = read_nwb(nwbfile_path_forced)
        timeseries_forced = nwbfile_forced.processing["behavior"].data_interfaces["TimeSeriesMiniscopeHeadOrientation"]

        # Verify that forced timestamps writes explicit timestamps
        assert timeseries_forced.timestamps is not None
        assert len(timeseries_forced.timestamps) == len(interface.get_timestamps())
