import numpy as np
from pynwb import read_nwb

from neuroconv.datainterfaces import MiniscopeHeadOrientationInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH

HEAD_ORIENTATION_FILE_PATH = (
    OPHYS_DATA_PATH
    / "imaging_datasets"
    / "Miniscope"
    / "dual_miniscope_with_config"
    / "researcher_name/experiment_name/animal_name"
    / "2025_06_12/15_26_31/HPC_miniscope1/headOrientation.csv"
)


class TestMiniscopeHeadOrientationInterfaceConversion(DataInterfaceTestMixin):
    data_interface_cls = MiniscopeHeadOrientationInterface
    interface_kwargs = dict(file_path=str(HEAD_ORIENTATION_FILE_PATH))
    expected_temporal_alignment_keys = ("TimeSeriesMiniscopeHeadOrientation",)
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        timeseries = nwbfile.processing["behavior"].data_interfaces["TimeSeriesMiniscopeHeadOrientation"]
        np.testing.assert_array_equal(timeseries.data[:], self.interface._quaternion_data)
        nwbfile.read_io.close()


class TestSingleMiniscopeHeadOrientationInterfaceConversion(DataInterfaceTestMixin):
    """The only single-scope head orientation file, and the only one whose first timestamp is negative."""

    data_interface_cls = MiniscopeHeadOrientationInterface
    interface_kwargs = dict(
        file_path=str(
            OPHYS_DATA_PATH
            / "imaging_datasets"
            / "Miniscope"
            / "single_miniscope_with_head_orientation"
            / "Dr_Miniscope/Linear_Track_Test/ID42/2025_05_23/09_53_05/Miniscope/headOrientation.csv"
        )
    )
    expected_temporal_alignment_keys = ("TimeSeriesMiniscopeHeadOrientation",)
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        timeseries = nwbfile.processing["behavior"].data_interfaces["TimeSeriesMiniscopeHeadOrientation"]
        np.testing.assert_array_equal(timeseries.timestamps[:], [-0.025, 0.010, 0.042])
        nwbfile.read_io.close()


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
        interface.temporal_alignment.shift_times(10.0)
        aligned_timestamps = interface.temporal_alignment["TimeSeriesMiniscopeHeadOrientation"].get_times()

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
        interface.temporal_alignment["TimeSeriesMiniscopeHeadOrientation"].set_times(uniform_timestamps)

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
