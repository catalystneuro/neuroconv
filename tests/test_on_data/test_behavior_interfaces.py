import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from natsort import natsorted
from ndx_miniscope import Miniscope
from ndx_miniscope.utils import get_timestamps
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO
from pynwb.behavior import Position, SpatialSeries

from neuroconv.datainterfaces import (
    DeepLabCutInterface,
    FicTracDataInterface,
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

try:
    from .setup_paths import BEHAVIOR_DATA_PATH, OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH


class TestFicTracDataInterface(DataInterfaceTestMixin, unittest.TestCase):
    data_interface_cls = FicTracDataInterface
    interface_kwargs = [
        dict(
            file_path=str(BEHAVIOR_DATA_PATH / "FicTrac" / "sample" / "sample-20230724_113055.dat"),
            configuration_file_path=BEHAVIOR_DATA_PATH / "FicTrac" / "sample" / "config.txt",
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

                expected_metadata = f"configuration_metadata = {configuration_metadata}"
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

                expected_metadata = f"configuration_metadata = {configuration_metadata}"
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

    def run_conversion(self, nwbfile_path: str):
        metadata = self.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        if self.case == 1:  # set custom timestamps
            self.interface.set_aligned_timestamps(self._custom_timestamps_case_1)
            assert len(self.interface._timestamps) == 2330

        self.interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

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

            if self.case == 1:  # custom timestamps
                for pose_estimation in pose_estimation_series_in_nwb.values():
                    pose_timestamps = pose_estimation.timestamps
                    np.testing.assert_array_equal(pose_timestamps, self._custom_timestamps_case_1)


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
