import unittest
from datetime import datetime
from pathlib import Path

import numpy as np
from natsort import natsorted
from ndx_miniscope import Miniscope
from ndx_miniscope.utils import get_timestamps
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import (
    DeepLabCutInterface,
    MiniscopeBehaviorInterface,
    SLEAPInterface,
    VideoInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    DataInterfaceTestMixin,
    DeepLabCutInterfaceMixin,
    TemporalAlignmentMixin,
    VideoInterfaceMixin,
)

try:
    from .setup_paths import BEHAVIOR_DATA_PATH, OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH


class TestVideoInterface(VideoInterfaceMixin, unittest.TestCase):
    data_interface_cls = VideoInterface
    interface_kwargs = [
        dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_avi.avi")]),
        dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_flv.flv")]),
        dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_mov.mov")]),
        dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_mp4.mp4")]),
        dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_wmv.wmv")]),
    ]
    save_directory = OUTPUT_PATH


class TestDeepLabCutInterface(DeepLabCutInterfaceMixin, unittest.TestCase):
    data_interface_cls = DeepLabCutInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"),
        config_file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "config.yaml"),
        subject_name="ind1",
    )
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):  # This is currently structured to be file-specific
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "behavior" in nwbfile.processing
            processing_module_interfaces = nwbfile.processing["behavior"].data_interfaces
            assert "PoseEstimation" in processing_module_interfaces

            pose_estimation_series_in_nwb = processing_module_interfaces["PoseEstimation"].pose_estimation_series
            expected_pose_estimation_series = ["ind1_leftear", "ind1_rightear", "ind1_snout", "ind1_tailbase"]

            expected_pose_estimation_series_are_in_nwb_file = [
                pose_estimation in pose_estimation_series_in_nwb for pose_estimation in expected_pose_estimation_series
            ]

            assert all(expected_pose_estimation_series_are_in_nwb_file)


class TestSLEAPInterface(DataInterfaceTestMixin, TemporalAlignmentMixin, unittest.TestCase):
    data_interface_cls = SLEAPInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "predictions_1.2.7_provenance_and_tracking.slp"),
        video_file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "melanogaster_courtship.mp4"),
    )
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):  # This is currently structured to be file-specific
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "SLEAP_VIDEO_000_20190128_113421" in nwbfile.processing
            processing_module_interfaces = nwbfile.processing["SLEAP_VIDEO_000_20190128_113421"].data_interfaces
            assert "track=track_0" in processing_module_interfaces

            pose_estimation_series_in_nwb = processing_module_interfaces["track=track_0"].pose_estimation_series
            expected_pose_estimation_series = [
                "abdomen",
                "eyeL",
                "eyeR",
                "forelegL4",
                "forelegR4",
                "head",
                "hindlegL4",
                "hindlegR4",
                "midlegL4",
                "midlegR4",
                "thorax",
                "wingL",
                "wingR",
            ]
            self.assertCountEqual(first=pose_estimation_series_in_nwb, second=expected_pose_estimation_series)


class TestMiniscopeInterface(DataInterfaceTestMixin, unittest.TestCase):
    data_interface_cls = MiniscopeBehaviorInterface
    interface_kwargs = dict(folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5"))
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls) -> None:
        folder_path = Path(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5")
        cls.device_name = "BehavCam2"
        cls.image_series_name = "BehavCamImageSeries"

        cls.device_metadata = dict(
            name=cls.device_name,
            compression="MJPG",
            deviceType="WebCam-1920x1080",
            framesPerFile=1000,
            ROI=[720, 1280],
        )
        cls.starting_frames = np.array([0, 5, 10])  # there are 5 frames in each of the three avi files
        cls.external_files = [str(file) for file in list(natsorted(folder_path.glob("*/BehavCam*/0.avi")))]
        cls.timestamps = get_timestamps(folder_path=str(folder_path), file_pattern="BehavCam*/timeStamps.csv")

    def check_extracted_metadata(self, metadata: dict):
        self.assertEqual(
            metadata["NWBFile"]["session_start_time"],
            datetime(2021, 10, 7, 15, 3, 28, 635),
        )
        self.assertEqual(metadata["Behavior"]["Device"][0], self.device_metadata)

        image_series_metadata = metadata["Behavior"]["ImageSeries"][0]
        self.assertEqual(image_series_metadata["name"], self.image_series_name)
        self.assertEqual(image_series_metadata["device"], self.device_name)
        self.assertEqual(image_series_metadata["unit"], "px")
        self.assertEqual(image_series_metadata["dimension"], [1280, 720])  # width x height

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            # Check device metadata
            self.assertIn(self.device_name, nwbfile.devices)
            device = nwbfile.devices[self.device_name]
            self.assertIsInstance(device, Miniscope)
            self.assertEqual(device.compression, self.device_metadata["compression"])
            self.assertEqual(device.deviceType, self.device_metadata["deviceType"])
            self.assertEqual(device.framesPerFile, self.device_metadata["framesPerFile"])
            assert_array_equal(device.ROI[:], self.device_metadata["ROI"])

            # Check ImageSeries
            self.assertIn(self.image_series_name, nwbfile.acquisition)
            image_series = nwbfile.acquisition[self.image_series_name]
            self.assertEqual(image_series.format, "external")
            assert_array_equal(image_series.starting_frame, self.starting_frames)
            assert_array_equal(image_series.dimension[:], [1280, 720])
            self.assertEqual(image_series.unit, "px")
            self.assertEqual(device, nwbfile.acquisition[self.image_series_name].device)
            assert_array_equal(image_series.timestamps[:], self.timestamps)
            assert_array_equal(image_series.external_file[:], self.external_files)
