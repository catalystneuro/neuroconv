import shutil
import tempfile
from datetime import datetime, timezone
from importlib.metadata import version as importlib_version
from pathlib import Path
from warnings import warn

import pytest
from hdmf.testing import TestCase
from packaging import version
from pynwb import NWBHDF5IO
from pynwb.image import ImageSeries

from neuroconv.converters import DANNCEConverter
from neuroconv.tools import get_module

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH

ndx_pose_version = version.parse(importlib_version("ndx-pose"))


@pytest.mark.skipif(
    ndx_pose_version < version.parse("0.3.0"),
    reason="DANNCEInterface requires ndx-pose version >= 0.3.0",
)
class TestDANNCEConverter(TestCase):
    """
    Real-data coverage for combining DANNCEInterface with one ExternalVideoInterface per camera,
    verifying the converter correctly links each camera's source video (written first) into the
    DANNCE MultiCameraPoseEstimation container via ``source_videos``.
    """

    @classmethod
    def setUpClass(cls) -> None:
        dannce_folder_path = BEHAVIOR_DATA_PATH / "dannce"
        cls.camera_names = ["Camera1", "Camera2"]
        cls.video_file_paths = {
            camera_name: [str(dannce_folder_path / "videos" / f"{camera_name}.mp4")]
            for camera_name in cls.camera_names
        }

        cls.converter = DANNCEConverter(
            file_path=str(dannce_folder_path / "save_data_MAX.mat"),
            video_file_paths=cls.video_file_paths,
            sampling_rate=30.0,
            calibration_path=str(dannce_folder_path / "calibration"),
            metadata_key="PoseEstimationDANNCE",
        )

        cls.test_dir = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_expected_metadata(self):
        metadata = self.converter.get_metadata()

        assert "Camera1" in metadata["Devices"]
        assert "Camera2" in metadata["Devices"]

        videos_metadata = metadata["Behavior"]["ExternalVideos"]
        assert set(videos_metadata.keys()) == {"video_Camera1", "video_Camera2"}
        assert videos_metadata["video_Camera1"]["name"] == "VideoCamera1"

        container = metadata["Behavior"]["Pose"]["PoseEstimations"]["PoseEstimationDANNCE"]
        assert container["device_metadata_keys"] == self.camera_names

    def test_run_conversion(self):
        nwbfile_path = str(self.test_dir / "test_dannce_converter.nwb")
        metadata = self.converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now(timezone.utc)
        metadata["Subject"] = dict(subject_id="mouse1", species="Mus musculus", sex="U")
        self.converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, stub_test=True)

        self.assertNWBFileStructure(nwbfile_path=nwbfile_path)

    def assertNWBFileStructure(self, nwbfile_path: str):
        from ndx_pose import CalibratedCamera, MultiCameraPoseEstimation

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()

            # Each camera's source video was written as an ImageSeries to acquisition.
            for camera_name in self.camera_names:
                video_name = f"Video{camera_name}"
                assert video_name in nwbfile.acquisition
                assert isinstance(nwbfile.acquisition[video_name], ImageSeries)

            behavior = get_module(nwbfile=nwbfile, name="behavior")
            pe = behavior.data_interfaces["PoseEstimationDANNCE"]
            assert isinstance(pe, MultiCameraPoseEstimation)
            assert len(pe.pose_estimations) == len(self.camera_names)

            # Exactly one Device per camera -- the video's ImageSeries and DANNCE's per-camera
            # PoseEstimation child must share the same calibrated Device, not each create their own
            # (e.g. no separate "VideoCameraN Camera Device" alongside "CameraN").
            assert set(nwbfile.devices.keys()) == set(self.camera_names)

            for camera_name in self.camera_names:
                device = nwbfile.devices[camera_name]
                assert isinstance(device, CalibratedCamera)

                video = nwbfile.acquisition[f"Video{camera_name}"]
                assert video.device is device

                camera_pose_estimation = pe.pose_estimations[f"{camera_name}PoseEstimation"]
                assert camera_pose_estimation.device is device
                assert camera_pose_estimation.source_video is video

            for pose_estimation_series in pe.pose_estimation_series.values():
                assert pose_estimation_series.data.shape[0] == 100  # stub_test truncates DANNCE to 100 frames
