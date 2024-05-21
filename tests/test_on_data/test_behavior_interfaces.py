import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import h5py
import numpy as np
import pandas as pd
import sleap_io
from hdmf.testing import TestCase
from natsort import natsorted
from ndx_facemap_motionsvd import MotionSVDMasks, MotionSVDSeries
from ndx_miniscope import Miniscope
from ndx_miniscope.utils import get_timestamps
from ndx_pose import PoseEstimation, PoseEstimationSeries
from numpy.testing import assert_array_equal
from parameterized import param, parameterized
from pynwb import NWBHDF5IO
from pynwb.behavior import EyeTracking, Position, PupilTracking, SpatialSeries

from neuroconv import NWBConverter
from neuroconv.datainterfaces import (
    DeepLabCutInterface,
    FacemapInterface,
    FicTracDataInterface,
    LightningPoseDataInterface,
    MiniscopeBehaviorInterface,
    NeuralynxNvtInterface,
    SLEAPInterface,
    VideoInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    DataInterfaceTestMixin,
    DeepLabCutInterfaceMixin,
    TemporalAlignmentMixin,
    VideoInterfaceMixin,
)
from neuroconv.utils import DeepDict

try:
    from .setup_paths import BEHAVIOR_DATA_PATH, OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH


class TestLightningPoseDataInterface(DataInterfaceTestMixin, TemporalAlignmentMixin, unittest.TestCase):
    data_interface_cls = LightningPoseDataInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds/test_vid.csv"),
        original_video_file_path=str(
            BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds/test_vid.mp4"
        ),
    )
    conversion_options = dict(reference_frame="(0,0) corresponds to the top left corner of the video.")
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls):
        cls.pose_estimation_name = "PoseEstimation"
        cls.original_video_height = 406
        cls.original_video_width = 396
        cls.expected_keypoint_names = [
            "paw1LH_top",
            "paw2LF_top",
            "paw3RF_top",
            "paw4RH_top",
            "tailBase_top",
            "tailMid_top",
            "nose_top",
            "obs_top",
            "paw1LH_bot",
            "paw2LF_bot",
            "paw3RF_bot",
            "paw4RH_bot",
            "tailBase_bot",
            "tailMid_bot",
            "nose_bot",
            "obsHigh_bot",
            "obsLow_bot",
        ]
        cls.expected_metadata = DeepDict(
            PoseEstimation=dict(
                name=cls.pose_estimation_name,
                description="Contains the pose estimation series for each keypoint.",
                scorer="heatmap_tracker",
                source_software="LightningPose",
            )
        )
        cls.expected_metadata[cls.pose_estimation_name].update(
            {
                keypoint_name: dict(
                    name=f"PoseEstimationSeries{keypoint_name}",
                    description=f"The estimated position (x, y) of {keypoint_name} over time.",
                )
                for keypoint_name in cls.expected_keypoint_names
            }
        )

        cls.test_data = pd.read_csv(cls.interface_kwargs["file_path"], header=[0, 1, 2])["heatmap_tracker"]

    def check_extracted_metadata(self, metadata: dict):
        self.assertEqual(
            metadata["NWBFile"]["session_start_time"],
            datetime(2023, 11, 9, 10, 14, 37, 0),
        )
        self.assertIn(self.pose_estimation_name, metadata["Behavior"])
        self.assertEqual(
            metadata["Behavior"][self.pose_estimation_name], self.expected_metadata[self.pose_estimation_name]
        )

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            self.assertIn("behavior", nwbfile.processing)
            self.assertIn(self.pose_estimation_name, nwbfile.processing["behavior"].data_interfaces)
            pose_estimation_container = nwbfile.processing["behavior"].data_interfaces[self.pose_estimation_name]
            self.assertIsInstance(pose_estimation_container, PoseEstimation)

            pose_estimation_metadata = self.expected_metadata[self.pose_estimation_name]
            self.assertEqual(pose_estimation_container.description, pose_estimation_metadata["description"])
            self.assertEqual(pose_estimation_container.scorer, pose_estimation_metadata["scorer"])
            self.assertEqual(pose_estimation_container.source_software, pose_estimation_metadata["source_software"])
            assert_array_equal(
                pose_estimation_container.dimensions[:], [[self.original_video_height, self.original_video_width]]
            )

            self.assertEqual(len(pose_estimation_container.pose_estimation_series), len(self.expected_keypoint_names))
            for keypoint_name in self.expected_keypoint_names:
                series_metadata = pose_estimation_metadata[keypoint_name]
                self.assertIn(series_metadata["name"], pose_estimation_container.pose_estimation_series)
                pose_estimation_series = pose_estimation_container.pose_estimation_series[series_metadata["name"]]
                self.assertIsInstance(pose_estimation_series, PoseEstimationSeries)
                self.assertEqual(pose_estimation_series.unit, "px")
                self.assertEqual(pose_estimation_series.description, series_metadata["description"])
                self.assertEqual(pose_estimation_series.reference_frame, self.conversion_options["reference_frame"])

                test_data = self.test_data[keypoint_name]
                assert_array_equal(pose_estimation_series.data[:], test_data[["x", "y"]].values)
                assert_array_equal(pose_estimation_series.confidence[:], test_data["likelihood"].values)


class TestLightningPoseDataInterfaceWithStubTest(DataInterfaceTestMixin, TemporalAlignmentMixin, unittest.TestCase):
    data_interface_cls = LightningPoseDataInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds/test_vid.csv"),
        original_video_file_path=str(
            BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds/test_vid.mp4"
        ),
    )
    conversion_options = dict(stub_test=True)
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            pose_estimation_container = nwbfile.processing["behavior"].data_interfaces["PoseEstimation"]
            for pose_estimation_series in pose_estimation_container.pose_estimation_series.values():
                self.assertEqual(pose_estimation_series.data.shape[0], 10)
                self.assertEqual(pose_estimation_series.confidence.shape[0], 10)


class TestFicTracDataInterface(DataInterfaceTestMixin, unittest.TestCase):
    data_interface_cls = FicTracDataInterface
    interface_kwargs = [
        dict(
            file_path=str(BEHAVIOR_DATA_PATH / "FicTrac" / "sample" / "sample-20230724_113055.dat"),
            configuration_file_path=str(BEHAVIOR_DATA_PATH / "FicTrac" / "sample" / "config.txt"),
        ),
    ]

    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        expected_session_start_time = datetime(2023, 7, 24, 9, 30, 55, 440600, tzinfo=timezone.utc)
        assert metadata["NWBFile"]["session_start_time"] == expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):  # This is currently structured to be file-specific
        configuration_metadata = (
            '{"version": "v2.1.1", '
            '"build_date": "Jul 24 2023", '
            '"c2a_cnrs_xy": [191, 171, 128, 272, 20, 212, 99, 132], '
            '"c2a_r": [0.722445, -0.131314, -0.460878], '
            '"c2a_src": "c2a_cnrs_xy", '
            '"c2a_t": [-0.674396, 0.389373, 2.889648], '
            '"do_display": true, '
            '"max_bad_frames": -1, '
            '"opt_bound": 0.35, '
            '"opt_do_global": false, '
            '"opt_max_err": -1.0, '
            '"opt_max_evals": 50, '
            '"opt_tol": 0.001, '
            '"q_factor": 6, '
            '"roi_c": [-0.22939, 0.099969, 0.968187], '
            '"roi_circ": [63, 171, 81, 145, 106, 135, 150, 160], '
            '"roi_ignr": [[96, 156, 113, 147, 106, 128, 82, 130, 81, 150], '
            "[71, 213, 90, 219, 114, 218, 135, 211, 154, 196, 150, 217, 121, 228, 99, 234, 75, 225]], "
            '"roi_r": 0.124815, '
            '"save_debug": false, '
            '"save_raw": false, '
            '"src_fn": "sample.mp4", '
            '"src_fps": -1.0, '
            '"thr_ratio": 1.25, '
            '"thr_win_pc": 0.25, '
            '"vfov": 45.0}'
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()

            fictrac_position_container = nwbfile.processing["behavior"].data_interfaces["FicTrac"]
            assert isinstance(fictrac_position_container, Position)

            assert len(fictrac_position_container.spatial_series) == 10

            column_to_nwb_mapping = self.interface.column_to_nwb_mapping
            for data_dict in column_to_nwb_mapping.values():
                spatial_series_name = data_dict["spatial_series_name"]
                assert spatial_series_name in fictrac_position_container.spatial_series

                reference_frame = data_dict["reference_frame"]
                spatial_series = fictrac_position_container.spatial_series[spatial_series_name]
                assert reference_frame == spatial_series.reference_frame

                expected_units = "radians"
                assert spatial_series.unit == expected_units
                assert spatial_series.conversion == 1.0

                expected_metadata = f"{configuration_metadata}"
                assert spatial_series.comments == expected_metadata

                assert spatial_series.timestamps[0] == 0.0


class TestFicTracDataInterfaceWithRadius(DataInterfaceTestMixin, unittest.TestCase):
    data_interface_cls = FicTracDataInterface
    interface_kwargs = [
        dict(file_path=str(BEHAVIOR_DATA_PATH / "FicTrac" / "sample" / "sample-20230724_113055.dat"), radius=1.0),
    ]

    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        expected_session_start_time = datetime(2023, 7, 24, 9, 30, 55, 440600, tzinfo=timezone.utc)
        assert metadata["NWBFile"]["session_start_time"] == expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):  # This is currently structured to be file-specific
        configuration_metadata = (
            '{"version": "v2.1.1", '
            '"build_date": "Jul 24 2023", '
            '"c2a_cnrs_xy": [191, 171, 128, 272, 20, 212, 99, 132], '
            '"c2a_r": [0.722445, -0.131314, -0.460878], '
            '"c2a_src": "c2a_cnrs_xy", '
            '"c2a_t": [-0.674396, 0.389373, 2.889648], '
            '"do_display": true, '
            '"max_bad_frames": -1, '
            '"opt_bound": 0.35, '
            '"opt_do_global": false, '
            '"opt_max_err": -1.0, '
            '"opt_max_evals": 50, '
            '"opt_tol": 0.001, '
            '"q_factor": 6, '
            '"roi_c": [-0.22939, 0.099969, 0.968187], '
            '"roi_circ": [63, 171, 81, 145, 106, 135, 150, 160], '
            '"roi_ignr": [[96, 156, 113, 147, 106, 128, 82, 130, 81, 150], '
            "[71, 213, 90, 219, 114, 218, 135, 211, 154, 196, 150, 217, 121, 228, 99, 234, 75, 225]], "
            '"roi_r": 0.124815, '
            '"save_debug": false, '
            '"save_raw": false, '
            '"src_fn": "sample.mp4", '
            '"src_fps": -1.0, '
            '"thr_ratio": 1.25, '
            '"thr_win_pc": 0.25, '
            '"vfov": 45.0}'
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()

            fictrac_position_container = nwbfile.processing["behavior"].data_interfaces["FicTrac"]
            assert isinstance(fictrac_position_container, Position)

            assert len(fictrac_position_container.spatial_series) == 10

            column_to_nwb_mapping = self.interface.column_to_nwb_mapping
            for data_dict in column_to_nwb_mapping.values():
                spatial_series_name = data_dict["spatial_series_name"]
                assert spatial_series_name in fictrac_position_container.spatial_series

                reference_frame = data_dict["reference_frame"]
                spatial_series = fictrac_position_container.spatial_series[spatial_series_name]
                assert reference_frame == spatial_series.reference_frame
                expected_units = "meters"
                assert spatial_series.unit == expected_units
                assert spatial_series.conversion == self.interface.radius

                expected_metadata = f"{configuration_metadata}"
                assert spatial_series.comments == expected_metadata

                assert spatial_series.timestamps[0] == 0.0


class TestFicTracDataInterfaceTiming(TemporalAlignmentMixin, unittest.TestCase):
    data_interface_cls = FicTracDataInterface
    interface_kwargs = [dict(file_path=str(BEHAVIOR_DATA_PATH / "FicTrac" / "sample" / "sample-20230724_113055.dat"))]

    save_directory = OUTPUT_PATH


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
    interface_kwargs_item = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"),
        config_file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "config.yaml"),
        subject_name="ind1",
    )
    # intentional duplicate to workaround 2 tests with changes after interface construction
    interface_kwargs = [
        interface_kwargs_item,  # this is case=0, no custom timestamp
        interface_kwargs_item,  # this is case=1, with custom timestamp
    ]

    # custom timestamps only for case 1
    _custom_timestamps_case_1 = np.concatenate(
        (np.linspace(10, 110, 1000), np.linspace(150, 250, 1000), np.linspace(300, 400, 330))
    )

    save_directory = OUTPUT_PATH

    def run_custom_checks(self):
        self.check_custom_timestamps(nwbfile_path=self.nwbfile_path)

    def check_custom_timestamps(self, nwbfile_path: str):
        # TODO: Peel out into separate test class and replace this part with check_read_nwb
        if self.case != 1:  # set custom timestamps
            return

        metadata = self.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        self.interface.set_aligned_timestamps(self._custom_timestamps_case_1)
        assert len(self.interface._timestamps) == 2330

        self.interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "behavior" in nwbfile.processing
            processing_module_interfaces = nwbfile.processing["behavior"].data_interfaces
            assert "PoseEstimation" in processing_module_interfaces

            pose_estimation_series_in_nwb = processing_module_interfaces["PoseEstimation"].pose_estimation_series

            for pose_estimation in pose_estimation_series_in_nwb.values():
                pose_timestamps = pose_estimation.timestamps
                np.testing.assert_array_equal(pose_timestamps, self._custom_timestamps_case_1)

    def check_read_nwb(self, nwbfile_path: str):
        # TODO: move this to the upstream mixin
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
            ROI={"height": 720, "leftEdge": 0, "topEdge": 0, "width": 1280},
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
            roi = [self.device_metadata["ROI"]["height"], self.device_metadata["ROI"]["width"]]
            assert_array_equal(device.ROI[:], roi)

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


class TestNeuralynxNvtInterface(DataInterfaceTestMixin, TemporalAlignmentMixin, unittest.TestCase):
    data_interface_cls = NeuralynxNvtInterface
    interface_kwargs = dict(file_path=str(BEHAVIOR_DATA_PATH / "neuralynx" / "test.nvt"))
    conversion_options = dict(add_angle=True)
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):  # This is currently structured to be file-specific
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert isinstance(nwbfile.acquisition["NvtPosition"].spatial_series["NvtSpatialSeries"], SpatialSeries)
            assert isinstance(
                nwbfile.acquisition["NvtCompassDirection"].spatial_series["NvtAngleSpatialSeries"], SpatialSeries
            )

    def check_metadata(self):
        super().check_metadata()
        metadata = self.interface.get_metadata()
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 5, 15, 10, 35, 29)


class CustomTestSLEAPInterface(TestCase):
    savedir = OUTPUT_PATH

    @parameterized.expand(
        [
            param(
                data_interface=SLEAPInterface,
                interface_kwargs=dict(
                    file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "predictions_1.2.7_provenance_and_tracking.slp"),
                ),
            )
        ]
    )
    def test_sleap_to_nwb_interface(self, data_interface, interface_kwargs):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}.nwb")

        interface = SLEAPInterface(**interface_kwargs)
        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        slp_predictions_path = interface_kwargs["file_path"]
        labels = sleap_io.load_slp(slp_predictions_path)

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            # Test matching number of processing modules
            number_of_videos = len(labels.videos)
            assert len(nwbfile.processing) == number_of_videos

            # Test processing module naming as video
            processing_module_name = "SLEAP_VIDEO_000_20190128_113421"
            assert processing_module_name in nwbfile.processing

            # For this case we have as many containers as tracks
            # Each track usually represents a subject
            processing_module = nwbfile.processing[processing_module_name]
            processing_module_interfaces = processing_module.data_interfaces
            assert len(processing_module_interfaces) == len(labels.tracks)

            # Test name of PoseEstimation containers
            extracted_container_names = processing_module_interfaces.keys()
            for track in labels.tracks:
                expected_track_name = f"track={track.name}"
                assert expected_track_name in extracted_container_names

            # Test one PoseEstimation container
            container_name = f"track={track.name}"
            pose_estimation_container = processing_module_interfaces[container_name]
            # Test that the skeleton nodes are store as nodes in containers
            expected_node_names = [node.name for node in labels.skeletons[0]]
            assert expected_node_names == list(pose_estimation_container.nodes[:])

            # Test that each PoseEstimationSeries is named as a node
            for node_name in pose_estimation_container.nodes[:]:
                assert node_name in pose_estimation_container.pose_estimation_series

    @parameterized.expand(
        [
            param(
                data_interface=SLEAPInterface,
                interface_kwargs=dict(
                    file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "melanogaster_courtship.slp"),
                    video_file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "melanogaster_courtship.mp4"),
                ),
            )
        ]
    )
    def test_sleap_interface_timestamps_propagation(self, data_interface, interface_kwargs):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}.nwb")

        interface = SLEAPInterface(**interface_kwargs)
        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        slp_predictions_path = interface_kwargs["file_path"]
        labels = sleap_io.load_slp(slp_predictions_path)

        from neuroconv.datainterfaces.behavior.sleap.sleap_utils import (
            extract_timestamps,
        )

        expected_timestamps = set(extract_timestamps(interface_kwargs["video_file_path"]))

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            # Test matching number of processing modules
            number_of_videos = len(labels.videos)
            assert len(nwbfile.processing) == number_of_videos

            # Test processing module naming as video
            video_name = Path(labels.videos[0].filename).stem
            processing_module_name = f"SLEAP_VIDEO_000_{video_name}"

            # For this case we have as many containers as tracks
            processing_module_interfaces = nwbfile.processing[processing_module_name].data_interfaces

            extracted_container_names = processing_module_interfaces.keys()
            for track in labels.tracks:
                expected_track_name = f"track={track.name}"
                assert expected_track_name in extracted_container_names

                container_name = f"track={track.name}"
                pose_estimation_container = processing_module_interfaces[container_name]

                # Test that each PoseEstimationSeries is named as a node
                for node_name in pose_estimation_container.nodes[:]:
                    pose_estimation_series = pose_estimation_container.pose_estimation_series[node_name]
                    extracted_timestamps = pose_estimation_series.timestamps[:]

                    # Some frames do not have predictions associated with them, so we test for sub-set
                    assert set(extracted_timestamps).issubset(expected_timestamps)


class TestVideoConversions(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video_files = list((BEHAVIOR_DATA_PATH / "videos" / "CFR").iterdir())
        cls.video_files.sort()
        cls.number_of_video_files = len(cls.video_files)
        cls.aligned_segment_starting_times = [0.0, 50.0, 100.0, 150.0, 175.0]

    def _get_metadata(self):
        """TODO: temporary helper function to fetch new metadata each time; need to debug in follow-up."""
        self.metadata = self.converter.get_metadata()
        self.metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        self.image_series_name = self.metadata["Behavior"]["Videos"][0]["name"]

    def test_real_videos(self):
        # TODO - merge this with the data mixin in follow-up
        for file_index, (file_path, segment_starting_time) in enumerate(
            zip(self.video_files, self.aligned_segment_starting_times)
        ):
            self.file_index = file_index

            class VideoTestNWBConverter(NWBConverter):
                data_interface_classes = dict(Video=VideoInterface)

            source_data = dict(Video=dict(file_paths=[file_path]))
            self.converter = VideoTestNWBConverter(source_data)
            self.interface = self.converter.data_interface_objects["Video"]
            self.interface.set_aligned_segment_starting_times(
                aligned_segment_starting_times=[self.aligned_segment_starting_times[self.file_index]]
            )

            self.check_video_set_aligned_starting_times()
            self.check_video_custom_module()
            self.check_video_chunking()

    def check_video_set_aligned_starting_times(self):
        self._get_metadata()
        conversion_options = dict(Video=dict(external_mode=False))
        nwbfile_path = OUTPUT_PATH / "check_video_starting_times.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert self.image_series_name in nwbfile.acquisition
            self.image_series = nwbfile.acquisition[self.image_series_name]

            if self.image_series.starting_time is not None:
                assert self.aligned_segment_starting_times[self.file_index] == self.image_series.starting_time
            else:
                assert self.aligned_segment_starting_times[self.file_index] == self.image_series.timestamps[0]

    def check_video_custom_module(self):
        self._get_metadata()
        module_name = "TestModule"
        module_description = "This is a test module."
        conversion_options = dict(
            Video=dict(
                external_mode=False,
                module_name=module_name,
                module_description=module_description,
            )
        )
        nwbfile_path = OUTPUT_PATH / "test_video_custom_module.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert module_name in nwbfile.processing
            assert module_description == nwbfile.processing[module_name].description
            assert self.image_series_name in nwbfile.processing[module_name].data_interfaces

    def check_video_chunking(self):
        self._get_metadata()
        conversion_options = dict(Video=dict(external_mode=False, stub_test=True, chunk_data=False))
        nwbfile_path = OUTPUT_PATH / "check_video_chunking.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert self.image_series_name in nwbfile.acquisition
            assert nwbfile.acquisition[self.image_series_name].data.chunks is not None

    def check_external_mode(self):
        self._get_metadata()
        conversion_options = dict(Video=dict(external_mode=True))
        nwbfile_path = OUTPUT_PATH / "check_external_mode.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert self.image_series_name in nwbfile.acquisition
            assert nwbfile.acquisition[self.image_series_name].external_file[0] == str(
                self.video_files[self.file_index]
            )

    def check_video_stub(self):
        self._get_metadata()
        conversion_options = dict(Video=dict(external_mode=False, stub_test=True))
        nwbfile_path = OUTPUT_PATH / "check_video_stub.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert self.image_series_name in nwbfile.acquisition
            assert nwbfile.acquisition[self.image_series_name].data.shape[0] == 10


class TestFacemapInterface(DataInterfaceTestMixin, TemporalAlignmentMixin, unittest.TestCase):

    data_interface_cls = FacemapInterface
    interface_kwargs = dict(
        mat_file_path=str(BEHAVIOR_DATA_PATH / "Facemap" / "facemap_output_test.mat"),
        video_file_path=str(BEHAVIOR_DATA_PATH / "Facemap" / "raw_behavioral_video.avi"),
        first_n_components=3,
    )
    conversion_options = dict()
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls):

        cls.eye_tracking_module = "EyeTracking"
        cls.eye_com_expected_metadata = dict(
            name="eye_center_of_mass",
            description="The position of the eye measured in degrees.",
            reference_frame="unknown",
            unit="degrees",
        )

        cls.pupil_tracking_module = "PupilTracking"
        cls.pupil_area_expected_metadata = dict(
            name="pupil_area",
            description="Area of pupil.",
            unit="unknown",
        )
        cls.pupil_area_raw_expected_metadata = dict(
            name="pupil_area_raw",
            description="Raw unprocessed area of pupil.",
            unit="unknown",
        )

        cls.motion_masks_module = "MotionSVDMasks"
        cls.motion_masks_expected_metadata = dict(
            name="MotionSVDMasks",
            description="Motion masks",
        )
        cls.motion_series_module = "MotionSVDSeries"
        cls.motion_series_expected_metadata = dict(
            name="MotionSVDSeries",
            description="Motion SVD components",
        )
        with h5py.File(cls.interface_kwargs["mat_file_path"], "r") as file:
            cls.eye_tracking_test_data = file["proc"]["pupil"]["com"][:].T
            cls.pupil_area_test_data = file["proc"]["pupil"]["area"][:].T
            cls.pupil_area_raw_test_data = file["proc"]["pupil"]["area_raw"][:].T

    def check_extracted_metadata(self, metadata: dict):

        self.assertIn(self.eye_tracking_module, metadata["Behavior"])
        self.assertEqual(self.eye_com_expected_metadata, metadata["Behavior"]["EyeTracking"])

        self.assertIn(self.pupil_tracking_module, metadata["Behavior"])
        self.assertEqual(self.pupil_area_expected_metadata, metadata["Behavior"]["PupilTracking"]["area"])
        self.assertEqual(self.pupil_area_raw_expected_metadata, metadata["Behavior"]["PupilTracking"]["area_raw"])

        self.assertIn(self.motion_masks_module, metadata["Behavior"])
        self.assertEqual(self.motion_masks_expected_metadata, metadata["Behavior"]["MotionSVDMasks"])

        self.assertIn(self.motion_series_module, metadata["Behavior"])
        self.assertEqual(self.motion_series_expected_metadata, metadata["Behavior"]["MotionSVDSeries"])

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            self.assertIn("behavior", nwbfile.processing)

            self.assertIn(self.eye_tracking_module, nwbfile.processing["behavior"].data_interfaces)
            eye_tracking_container = nwbfile.processing["behavior"].data_interfaces[self.eye_tracking_module]
            self.assertIsInstance(eye_tracking_container, EyeTracking)
            eye_tracking_spatial_series = eye_tracking_container.spatial_series["eye_center_of_mass"]
            self.assertEqual(eye_tracking_spatial_series.data.shape, self.eye_tracking_test_data.shape)
            assert_array_equal(eye_tracking_spatial_series.data[:], self.eye_tracking_test_data)

            self.assertIn(self.pupil_tracking_module, nwbfile.processing["behavior"].data_interfaces)
            pupil_tracking_container = nwbfile.processing["behavior"].data_interfaces[self.pupil_tracking_module]
            self.assertIsInstance(pupil_tracking_container, PupilTracking)
            pupil_area_time_series = pupil_tracking_container.time_series["pupil_area"]
            self.assertEqual(pupil_area_time_series.data.shape, self.pupil_area_test_data.shape)
            assert_array_equal(pupil_area_time_series.data[:], self.pupil_area_test_data)
            pupil_area_raw_time_series = pupil_tracking_container.time_series["pupil_area_raw"]
            self.assertEqual(pupil_area_raw_time_series.data.shape, self.pupil_area_raw_test_data.shape)
            assert_array_equal(pupil_area_raw_time_series.data[:], self.pupil_area_raw_test_data)

            self.assertIn("MotionSVDMasksMultivideo", nwbfile.processing["behavior"].data_interfaces)
            motion_masks_container = nwbfile.processing["behavior"].data_interfaces["MotionSVDMasksMultivideo"]
            self.assertIsInstance(motion_masks_container, MotionSVDMasks)
            assert_array_equal(motion_masks_container.processed_frame_dimension[:], [295, 288])
            assert_array_equal(motion_masks_container.mask_coordinates[:], [49, 0, 294, 287])
            self.assertEqual(motion_masks_container.downsampling_factor, 4.0)
            self.assertEqual(motion_masks_container["image_mask"].shape[0], 3)
            self.assertIn("MotionSVDSeriesMultivideo", nwbfile.processing["behavior"].data_interfaces)
            motion_seires_container = nwbfile.processing["behavior"].data_interfaces["MotionSVDSeriesMultivideo"]
            self.assertIsInstance(motion_seires_container, MotionSVDSeries)
            self.assertEqual(motion_seires_container.data.shape[0], 18078)
            self.assertIn("MotionSVDMasksROI1", nwbfile.processing["behavior"].data_interfaces)
            motion_masks_container = nwbfile.processing["behavior"].data_interfaces["MotionSVDMasksROI1"]
            self.assertIsInstance(motion_masks_container, MotionSVDMasks)
            assert_array_equal(motion_masks_container.processed_frame_dimension[:], [295, 288])
            assert_array_equal(motion_masks_container.mask_coordinates[:], [147, 112, 279, 240])
            self.assertEqual(motion_masks_container.downsampling_factor, 4.0)
            self.assertEqual(motion_masks_container["image_mask"].shape[0], 3)
            self.assertIn("MotionSVDSeriesROI1", nwbfile.processing["behavior"].data_interfaces)
            motion_seires_container = nwbfile.processing["behavior"].data_interfaces["MotionSVDSeriesROI1"]
            self.assertIsInstance(motion_seires_container, MotionSVDSeries)
            self.assertEqual(motion_seires_container.data.shape[0], 18078)


if __name__ == "__main__":
    unittest.main()
