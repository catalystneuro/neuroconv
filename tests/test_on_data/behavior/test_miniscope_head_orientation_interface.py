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

        # Check that session_start_time was extracted correctly
        from datetime import datetime

        assert "NWBFile" in metadata
        assert "session_start_time" in metadata["NWBFile"]
        expected_start_time = datetime(2025, 6, 12, 15, 26, 31, 176000)
        assert metadata["NWBFile"]["session_start_time"] == expected_start_time

    def test_nwb_conversion(self, tmp_path):
        """Test data is correctly written to NWB file."""
        interface = MiniscopeHeadOrientationInterface(file_path=self.headOrientation_file_path)
        metadata = interface.get_metadata()
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
        assert timeseries.rate is None

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
        custom_key = "CustomHeadOrientation"
        interface = MiniscopeHeadOrientationInterface(file_path=self.headOrientation_file_path, metadata_key=custom_key)

        # Verify metadata uses custom key
        metadata = interface.get_metadata()
        assert custom_key in metadata["TimeSeries"]
        assert metadata["TimeSeries"][custom_key]["name"] == custom_key

        # Verify NWB conversion uses custom key
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

    def test_timestamps_unifom(self, tmp_path):
        """Test uniform timestamp detection and always_write_timestamps parameter."""
        interface = MiniscopeHeadOrientationInterface(file_path=self.headOrientation_file_path)
        metadata = interface.get_metadata()

        # Set uniform timestamps at 30 Hz (consistent with Miniscope frame rate)
        num_samples = len(interface._quaternion_data)
        uniform_timestamps = np.arange(num_samples) / 30.0
        interface.set_aligned_timestamps(uniform_timestamps)

        # Test default behavior with uniform timestamps (should use rate)
        nwbfile_path_default = tmp_path / "test_default_timestamps.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path_default, metadata=metadata)

        nwbfile_default = read_nwb(nwbfile_path_default)
        timeseries_default = nwbfile_default.processing["behavior"].data_interfaces[
            "TimeSeriesMiniscopeHeadOrientation"
        ]

        # With uniform timestamps, should use rate instead of explicit timestamps
        assert timeseries_default.rate == 30.0
        assert timeseries_default.starting_time == 0.0
