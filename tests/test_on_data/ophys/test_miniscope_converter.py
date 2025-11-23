import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from warnings import warn

import pytest
from pynwb import NWBHDF5IO
from pynwb.image import ImageSeries
from pynwb.ophys import OnePhotonSeries

from neuroconv import ConverterPipe, NWBConverter
from neuroconv.converters import MiniscopeConverter
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH


class TestMiniscopeConverter:
    """Test MiniscopeConverter with dual miniscope setup and time alignment."""

    folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "dual_miniscope_with_config"
    config_file_path = folder_path / "UserConfigFile.json"

    def test_run_conversion(self, tmp_path):
        """Test conversion with dual miniscope setup, multiple sessions, and time alignment."""
        from pynwb import read_nwb

        # Create converter
        converter = MiniscopeConverter(
            folder_path=str(self.folder_path), user_configuration_file_path=str(self.config_file_path)
        )

        # Run conversion
        nwbfile_path = str(tmp_path / "test_miniscope_dual.nwb")
        converter.run_conversion(nwbfile_path=nwbfile_path, stub_test=True, stub_samples=2)

        # Read the NWB file
        nwbfile = read_nwb(nwbfile_path)

        # 1. Check session_start_time is the minimum across all sessions
        expected_min_start_time = datetime(2025, 6, 12, 15, 15, 4, 724000)
        assert nwbfile.session_start_time.replace(tzinfo=None) == expected_min_start_time

        # 2. Check that all 4 expected OnePhotonSeries exist
        # 2 devices (ACC_miniscope2, HPC_miniscope1) x 2 sessions (15_15_04, 15_26_31)
        assert "OnePhotonSeries2025_06_1215_15_04ACC_miniscope2" in nwbfile.acquisition
        assert "OnePhotonSeries2025_06_1215_15_04HPC_miniscope1" in nwbfile.acquisition
        assert "OnePhotonSeries2025_06_1215_26_31ACC_miniscope2" in nwbfile.acquisition
        assert "OnePhotonSeries2025_06_1215_26_31HPC_miniscope1" in nwbfile.acquisition

        assert len(nwbfile.acquisition) == 4

        # 3. Check that both devices exist
        assert "ACC_miniscope2" in nwbfile.devices
        assert "HPC_miniscope1" in nwbfile.devices

        # 4. Check that both imaging planes exist (one per device, not per session)
        assert "ImagingPlaneACC_miniscope2" in nwbfile.imaging_planes
        assert "ImagingPlaneHPC_miniscope1" in nwbfile.imaging_planes

        # 5. Verify time alignment - timestamps of later sessions should be shifted

        # Session 1 (15_15_04) - both devices should start at t=0
        series_acc_session1 = nwbfile.acquisition["OnePhotonSeries2025_06_1215_15_04ACC_miniscope2"]
        series_hpc_session1 = nwbfile.acquisition["OnePhotonSeries2025_06_1215_15_04HPC_miniscope1"]
        assert series_acc_session1.starting_time == 0.0
        assert series_hpc_session1.starting_time == 0.0

        # Session 2 (15_26_31) - both devices should start at t=686.452

        expected_offset = (
            datetime(2025, 6, 12, 15, 26, 31, 176000) - datetime(2025, 6, 12, 15, 15, 4, 724000)
        ).total_seconds()

        series_acc_session2 = nwbfile.acquisition["OnePhotonSeries2025_06_1215_26_31ACC_miniscope2"]
        series_hpc_session2 = nwbfile.acquisition["OnePhotonSeries2025_06_1215_26_31HPC_miniscope1"]
        assert series_acc_session2.starting_time == expected_offset
        assert series_hpc_session2.starting_time == expected_offset

        # 6. Verify each series has correct imaging plane link
        assert series_acc_session1.imaging_plane.name == "ImagingPlaneACC_miniscope2"
        assert series_hpc_session1.imaging_plane.name == "ImagingPlaneHPC_miniscope1"
        assert series_acc_session2.imaging_plane.name == "ImagingPlaneACC_miniscope2"
        assert series_hpc_session2.imaging_plane.name == "ImagingPlaneHPC_miniscope1"

        # 7. Verify stub test worked (only 2 frames per series)
        assert series_acc_session1.data.shape[0] == 2
        assert series_hpc_session1.data.shape[0] == 2
        assert series_acc_session2.data.shape[0] == 2
        assert series_hpc_session2.data.shape[0] == 2


class TestMiniscopeConverterTyeLabLegacy:
    """Test MiniscopeConverter with Tye Lab legacy folder structure."""

    @pytest.fixture(autouse=True)
    def setup_class_fixture(self):
        """Set up test fixtures for legacy Tye Lab data."""
        self.folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5")
        self.converter = MiniscopeConverter(folder_path=self.folder_path)
        self.test_dir = Path(tempfile.mkdtemp())

        self.stub_frames = 2
        self.conversion_options = dict(stub_test=True, stub_frames=self.stub_frames)

        self.device_name = "Miniscope"
        self.device_metadata = dict(
            name=self.device_name,
            compression="FFV1",
            deviceType="Miniscope_V3",
            frameRate="15FPS",
            framesPerFile=1000,
            gain="High",
            led0=47,
        )

        self.behavcam_name = "BehavCam2"
        self.behavcam_metadata = dict(
            name=self.behavcam_name,
            compression="MJPG",
            deviceType="WebCam-1920x1080",
            framesPerFile=1000,
            ROI={"height": 720, "leftEdge": 0, "topEdge": 0, "width": 1280},
        )

        self.image_series_name = "BehavCamImageSeries"
        self.photon_series_name = "OnePhotonSeriesMiniscope"

        yield

        # Teardown
        try:
            shutil.rmtree(self.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {self.test_dir}! Please remove it manually.")

    def _assert_nwbfile_structure(self, nwbfile_path: str):
        """Helper method to assert NWB file structure."""
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.session_start_time.replace(tzinfo=None) == datetime(2021, 10, 7, 15, 3, 28, 635)

            assert self.device_name in nwbfile.devices
            assert self.behavcam_name in nwbfile.devices
            assert self.photon_series_name in nwbfile.acquisition
            assert isinstance(nwbfile.acquisition[self.photon_series_name], OnePhotonSeries)
            assert self.image_series_name in nwbfile.acquisition
            assert isinstance(nwbfile.acquisition[self.image_series_name], ImageSeries)

    def test_converter_metadata(self):
        """Test that metadata is correctly extracted from legacy format."""
        metadata = self.converter.get_metadata()
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 10, 7, 15, 3, 28, 635)
        assert metadata["Ophys"]["Device"][0] == self.device_metadata
        assert metadata["Behavior"]["Device"][0] == self.behavcam_metadata

    def test_run_conversion(self):
        """Test basic conversion to NWB."""
        nwbfile_path = str(self.test_dir / "test_miniscope_converter.nwb")
        self.converter.run_conversion(nwbfile_path=nwbfile_path)

        self._assert_nwbfile_structure(nwbfile_path=nwbfile_path)

    def test_run_conversion_add_conversion_options(self):
        """Test conversion with stub options."""
        nwbfile_path = str(self.test_dir / "test_miniscope_converter_conversion_options.nwb")
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            **self.conversion_options,
        )

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        num_frames = nwbfile.acquisition[self.photon_series_name].data.shape[0]
        assert num_frames == self.stub_frames

    def test_run_conversion_updated_metadata(self):
        """Test conversion with updated metadata."""
        metadata = self.converter.get_metadata()
        # Update device names and their links
        test_device_name = "TestMiniscope"
        test_behavcam_name = "TestBehavCam"
        metadata["Ophys"]["Device"][0].update(name=test_device_name)
        metadata["Ophys"]["ImagingPlane"][0].update(device=test_device_name)
        metadata["Behavior"]["Device"][0].update(name=test_behavcam_name)
        metadata["Behavior"]["ImageSeries"][0].update(device=test_behavcam_name)

        nwbfile_path = str(self.test_dir / "test_miniscope_converter_updated_metadata.nwb")
        self.converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert test_device_name in nwbfile.devices
            assert test_behavcam_name in nwbfile.devices
            assert nwbfile.devices[test_device_name] == nwbfile.imaging_planes["ImagingPlaneMiniscope"].device
            assert nwbfile.devices[test_behavcam_name] == nwbfile.acquisition[self.image_series_name].device

    def test_converter_in_converter(self):
        """Test MiniscopeConverter within another NWBConverter."""

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestMiniscopeConverter=MiniscopeConverter)

        converter = TestConverter(
            source_data=dict(
                TestMiniscopeConverter=dict(folder_path=self.folder_path),
            )
        )

        nwbfile_path = str(self.test_dir / "test_miniscope_converter_in_nwbconverter.nwb")
        converter.run_conversion(nwbfile_path=nwbfile_path)

        self._assert_nwbfile_structure(nwbfile_path)

    def test_converter_conversion_options(self):
        """Test MiniscopeConverter in NWBConverter with conversion options."""

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestMiniscopeConverter=MiniscopeConverter)

        nwbfile_path = str(self.test_dir / "test_miniscope_converter_in_nwbconverter_conversion_options.nwb")
        converter = TestConverter(
            source_data=dict(
                TestMiniscopeConverter=dict(folder_path=self.folder_path),
            )
        )
        conversion_options = dict(TestMiniscopeConverter=self.conversion_options)
        converter.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        num_frames = nwbfile.acquisition[self.photon_series_name].data.shape[0]
        assert num_frames == self.stub_frames

    def test_converter_in_converter_pipe(self):
        """Test MiniscopeConverter in ConverterPipe."""
        converter_pipe = ConverterPipe(data_interfaces=[self.converter])

        nwbfile_path = self.test_dir / "test_miniscope_converter_in_converter_pipe.nwb"
        converter_pipe.run_conversion(nwbfile_path=nwbfile_path)

        self._assert_nwbfile_structure(nwbfile_path=nwbfile_path)

    def test_converter_in_converter_pipe_conversion_options(self):
        """Test MiniscopeConverter in ConverterPipe with conversion options."""
        converter_pipe = ConverterPipe(data_interfaces=[self.converter])

        nwbfile_path = self.test_dir / "test_miniscope_converter_in_converter_pipe_conversion_options.nwb"
        conversion_options = dict(MiniscopeConverter=self.conversion_options)
        converter_pipe.run_conversion(nwbfile_path=nwbfile_path, conversion_options=conversion_options)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
        num_frames = nwbfile.acquisition[self.photon_series_name].data.shape[0]
        assert num_frames == self.stub_frames
