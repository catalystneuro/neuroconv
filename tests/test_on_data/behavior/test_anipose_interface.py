import numpy as np
from numpy.testing import assert_array_equal
from pynwb import read_nwb

from neuroconv.datainterfaces import AniposeInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH

ANIPOSE_DATA_PATH = BEHAVIOR_DATA_PATH / "anipose"
MOUSE_SESSION_PATH = ANIPOSE_DATA_PATH / "pose_input_format" / "deeplabcut_h5" / "020920_preDTreaches_day2" / "JiDT12"
MOUSE_FILE_NAME = "preDT2_JiDT12_reach14_miss.csv"
FLY_FILE_NAME = "05272019_fly1_0 R3C2  str-cw-0.03 sec.csv"


class _AniposeInterfaceTestMixin(DataInterfaceTestMixin):
    """Every object the metadata declares is in the file, of the type, name and shape the metadata says.

    ``PoseEstimationInterfaceTestMixin`` checks ``PoseEstimation`` containers only, and Anipose writes a
    ``MultiCameraPoseEstimation`` whose per-camera ``PoseEstimation`` entries have no series.
    """

    expected_temporal_alignment_keys = ("anipose",)

    def check_read_nwb(self, nwbfile_path: str):
        from ndx_pose import CalibratedCamera, MultiCameraPoseEstimation

        metadata = self.interface.get_metadata()
        container_entry = metadata["Pose"]["MultiCameraPoseEstimations"]["anipose"]
        nwbfile = read_nwb(nwbfile_path)
        container = nwbfile.processing["behavior"][container_entry["name"]]
        assert isinstance(container, MultiCameraPoseEstimation)
        assert container.source_software == "Anipose"
        assert list(container.skeleton.nodes[:]) == metadata["Pose"]["Skeletons"]["anipose"]["nodes"]

        num_frames = len(self.interface.temporal_alignment["anipose"].get_times())
        for series_entry in container_entry["PoseEstimationSeries"].values():
            series = container.pose_estimation_series[series_entry["name"]]
            assert series.data.shape == (num_frames, 3)
            assert series.confidence.shape == (num_frames,)
            assert series.reference_frame == series_entry.get("reference_frame", "unknown")

        camera_metadata_keys = container_entry.get("pose_estimation_metadata_keys", [])
        assert len(container.pose_estimations) == len(camera_metadata_keys)
        for camera_metadata_key in camera_metadata_keys:
            device_entry = metadata["Devices"][
                metadata["Pose"]["PoseEstimations"][camera_metadata_key]["device_metadata_key"]
            ]
            device = nwbfile.devices[device_entry["name"]]
            assert isinstance(device, CalibratedCamera)
            assert_array_equal(device.intrinsic_matrix[:], device_entry["intrinsic_matrix"])
            assert_array_equal(device.rotation_matrix[:], device_entry["rotation_matrix"])
            assert_array_equal(device.translation_vector[:], device_entry["translation_vector"])
        nwbfile.read_io.close()


class TestAniposeInterfaceOptimizationReflectedAxes(_AniposeInterfaceTestMixin):
    """The paper fly: six cameras, spatiotemporal optimization, axes whose transform is a reflection."""

    data_interface_cls = AniposeInterface
    interface_kwargs = dict(
        file_path=str(
            ANIPOSE_DATA_PATH / "triangulation" / "optimization_reflected_axes" / "Fly 1_0" / "pose-3d" / FLY_FILE_NAME
        ),
        calibration_file_path=str(
            ANIPOSE_DATA_PATH / "triangulation" / "optimization_reflected_axes" / "Calibration" / "calibration.toml"
        ),
        sampling_rate=300.0,
    )
    save_directory = OUTPUT_PATH

    expected_number_of_keypoints = 30
    expected_number_of_frames = 100
    expected_camera_names = ["A", "B", "C", "D", "E", "F"]
    expected_rate = 300.0
    expected_first_series_name = "PoseEstimationSeriesL1A"
    # Frame 0 of keypoint L1A: L1A_x, L1A_y, L1A_z and L1A_score
    expected_first_position = [0.0029918028152885, -0.0014553043929743, -0.0037652705010748]
    expected_first_confidence = 0.9975504875183104
    expected_transform_determinant = -1.0

    def check_extracted_metadata(self, metadata: dict):
        container_entry = metadata["Pose"]["MultiCameraPoseEstimations"]["anipose"]
        assert len(metadata["Pose"]["Skeletons"]["anipose"]["nodes"]) == self.expected_number_of_keypoints
        camera_names = [
            metadata["Pose"]["PoseEstimations"][key]["device_metadata_key"]
            for key in container_entry["pose_estimation_metadata_keys"]
        ]
        assert camera_names == self.expected_camera_names
        for camera_name in self.expected_camera_names:
            assert metadata["Devices"][camera_name]["type"] == "CalibratedCamera"
        matrix, _ = self.interface._transform
        assert np.isclose(np.linalg.det(matrix), self.expected_transform_determinant)
        for series_entry in container_entry["PoseEstimationSeries"].values():
            assert series_entry["reference_frame"].startswith(
                "The world frame of the camera calibration that Anipose triangulated with, transformed by the axes"
            )

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        series = nwbfile.processing["behavior"]["PoseEstimationAnipose"].pose_estimation_series[
            self.expected_first_series_name
        ]
        assert series.data.shape == (self.expected_number_of_frames, 3)
        assert series.rate == self.expected_rate
        assert series.get_starting_time() == 0.0
        assert_array_equal(series.data[0], self.expected_first_position)
        assert series.confidence[0] == self.expected_first_confidence
        nwbfile.read_io.close()


class TestAniposeInterfaceOptimizationWithoutAxes(_AniposeInterfaceTestMixin):
    """The marmoset: two cameras named "1" and "2", spatiotemporal optimization, no axes."""

    data_interface_cls = AniposeInterface
    interface_kwargs = dict(
        file_path=str(
            ANIPOSE_DATA_PATH
            / "triangulation"
            / "optimization_without_axes"
            / "2019_04_15"
            / "pose-3d"
            / "2019_04_15_session1_event013_.csv"
        ),
        calibration_file_path=str(
            ANIPOSE_DATA_PATH
            / "triangulation"
            / "optimization_without_axes"
            / "2019_04_15"
            / "calibration"
            / "calibration.toml"
        ),
        sampling_rate=200.0,
    )
    save_directory = OUTPUT_PATH

    expected_number_of_keypoints = 11
    expected_number_of_frames = 100
    expected_camera_names = ["1", "2"]
    expected_rate = 200.0
    expected_first_series_name = "PoseEstimationSeriesHandD"
    # Frame 0 of keypoint hand_d: hand_d_x, hand_d_y, hand_d_z and hand_d_score
    expected_first_position = [8.53072311888649, 6.153198516702616, 0.7558163066758957]
    expected_first_confidence = 0.879741273565824
    expected_reference_frame = "The world frame of the camera calibration that Anipose triangulated with."

    def check_extracted_metadata(self, metadata: dict):
        container_entry = metadata["Pose"]["MultiCameraPoseEstimations"]["anipose"]
        assert len(metadata["Pose"]["Skeletons"]["anipose"]["nodes"]) == self.expected_number_of_keypoints
        camera_names = [
            metadata["Pose"]["PoseEstimations"][key]["device_metadata_key"]
            for key in container_entry["pose_estimation_metadata_keys"]
        ]
        assert camera_names == self.expected_camera_names
        for series_entry in container_entry["PoseEstimationSeries"].values():
            assert series_entry["reference_frame"] == self.expected_reference_frame

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        series = nwbfile.processing["behavior"]["PoseEstimationAnipose"].pose_estimation_series[
            self.expected_first_series_name
        ]
        assert series.data.shape == (self.expected_number_of_frames, 3)
        assert series.rate == self.expected_rate
        assert series.get_starting_time() == 0.0
        assert_array_equal(series.data[0], self.expected_first_position)
        assert series.confidence[0] == self.expected_first_confidence
        nwbfile.read_io.close()


class TestAniposeInterfaceRansacNonOrthogonalAxes(_AniposeInterfaceTestMixin):
    """The paper fly triangulated with RANSAC by Anipose 1.1.24, whose axes transform is not orthogonal."""

    data_interface_cls = AniposeInterface
    interface_kwargs = dict(
        file_path=str(
            ANIPOSE_DATA_PATH
            / "triangulation"
            / "ransac_non_orthogonal_axes_version_1_1_24"
            / "Fly 1_0"
            / "pose-3d"
            / FLY_FILE_NAME
        ),
        calibration_file_path=str(
            ANIPOSE_DATA_PATH
            / "triangulation"
            / "ransac_non_orthogonal_axes_version_1_1_24"
            / "Calibration"
            / "calibration.toml"
        ),
        sampling_rate=300.0,
    )
    save_directory = OUTPUT_PATH

    expected_number_of_keypoints = 30
    expected_number_of_frames = 100
    expected_camera_names = ["A", "B", "C", "D", "E", "F"]
    expected_rate = 300.0
    expected_first_series_name = "PoseEstimationSeriesL1A"
    # Frame 0 of keypoint L1A: L1A_x, L1A_y, L1A_z and L1A_score
    expected_first_position = [-0.0047898294815674, 0.0015891421091172, 0.0015655430903009]
    expected_first_confidence = 0.9975504875183104

    def check_extracted_metadata(self, metadata: dict):
        container_entry = metadata["Pose"]["MultiCameraPoseEstimations"]["anipose"]
        assert len(metadata["Pose"]["Skeletons"]["anipose"]["nodes"]) == self.expected_number_of_keypoints
        camera_names = [
            metadata["Pose"]["PoseEstimations"][key]["device_metadata_key"]
            for key in container_entry["pose_estimation_metadata_keys"]
        ]
        assert camera_names == self.expected_camera_names
        # Rows x and z of M are not perpendicular
        matrix, _ = self.interface._transform
        assert not np.allclose(matrix @ matrix.T, np.eye(3))

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        series = nwbfile.processing["behavior"]["PoseEstimationAnipose"].pose_estimation_series[
            self.expected_first_series_name
        ]
        assert series.data.shape == (self.expected_number_of_frames, 3)
        assert series.rate == self.expected_rate
        assert series.get_starting_time() == 0.0
        assert_array_equal(series.data[0], self.expected_first_position)
        assert series.confidence[0] == self.expected_first_confidence
        nwbfile.read_io.close()


class TestAniposeInterfacePlainTriangulation(_AniposeInterfaceTestMixin):
    """The paper mouse: two cameras, plain triangulation, hyphenated keypoint names, about half the points NaN."""

    data_interface_cls = AniposeInterface
    interface_kwargs = dict(
        file_path=str(MOUSE_SESSION_PATH / "pose-3d" / MOUSE_FILE_NAME),
        calibration_file_path=str(MOUSE_SESSION_PATH / "calibration" / "calibration.toml"),
        sampling_rate=200.0,
    )
    save_directory = OUTPUT_PATH

    expected_keypoint_names = ["l-base", "l-edge", "l-middle", "r-base", "r-edge", "r-middle"]
    expected_number_of_frames = 112
    expected_camera_names = ["cam1", "cam2"]
    expected_rate = 200.0
    expected_first_series_name = "PoseEstimationSeriesLBase"
    # Frame 0 of keypoint l-base: l-base_x, l-base_y, l-base_z and l-base_score
    expected_first_position = [3.718712567602676, 23.39811090916537, 645.528881281094]
    expected_first_confidence = 0.9983834624290466
    expected_fraction_of_missing_positions = 0.5
    expected_reference_frame = "The world frame of the camera calibration that Anipose triangulated with."

    def check_extracted_metadata(self, metadata: dict):
        container_entry = metadata["Pose"]["MultiCameraPoseEstimations"]["anipose"]
        assert metadata["Pose"]["Skeletons"]["anipose"]["nodes"] == self.expected_keypoint_names
        camera_names = [
            metadata["Pose"]["PoseEstimations"][key]["device_metadata_key"]
            for key in container_entry["pose_estimation_metadata_keys"]
        ]
        assert camera_names == self.expected_camera_names
        for series_entry in container_entry["PoseEstimationSeries"].values():
            assert series_entry["reference_frame"] == self.expected_reference_frame

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        container = nwbfile.processing["behavior"]["PoseEstimationAnipose"]
        series = container.pose_estimation_series[self.expected_first_series_name]
        assert series.data.shape == (self.expected_number_of_frames, 3)
        assert series.rate == self.expected_rate
        assert series.get_starting_time() == 0.0
        assert_array_equal(series.data[0], self.expected_first_position)
        assert series.confidence[0] == self.expected_first_confidence
        positions = np.stack([series.data[:] for series in container.pose_estimation_series.values()])
        assert np.isnan(positions).mean() == self.expected_fraction_of_missing_positions
        nwbfile.read_io.close()


class TestAniposeInterfaceFiltered3D(_AniposeInterfaceTestMixin):
    """The paper mouse's `pose-3d-filtered` CSV from Anipose 1.1.24, which has the columns of a pose-3d CSV."""

    data_interface_cls = AniposeInterface
    interface_kwargs = dict(
        file_path=str(
            ANIPOSE_DATA_PATH
            / "pipeline_stages"
            / "filtered_3d_version_1_1_24"
            / "020920_preDTreaches_day2"
            / "JiDT12"
            / "pose-3d-filtered"
            / MOUSE_FILE_NAME
        ),
        sampling_rate=200.0,
    )
    save_directory = OUTPUT_PATH

    expected_keypoint_names = ["l-base", "l-edge", "l-middle", "r-base", "r-edge", "r-middle"]
    expected_number_of_frames = 112
    expected_rate = 200.0
    expected_first_series_name = "PoseEstimationSeriesLBase"
    # Frame 0 of keypoint l-base: l-base_x, l-base_y, l-base_z and l-base_score
    expected_first_position = [3.649568556358379, 23.37080236936909, 645.318513010053]
    expected_first_confidence = 0.9983834624290466

    def check_extracted_metadata(self, metadata: dict):
        container_entry = metadata["Pose"]["MultiCameraPoseEstimations"]["anipose"]
        assert metadata["Pose"]["Skeletons"]["anipose"]["nodes"] == self.expected_keypoint_names
        # No calibration given, so no cameras
        assert "pose_estimation_metadata_keys" not in container_entry
        assert not metadata["Pose"]["PoseEstimations"]

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        series = nwbfile.processing["behavior"]["PoseEstimationAnipose"].pose_estimation_series[
            self.expected_first_series_name
        ]
        assert series.data.shape == (self.expected_number_of_frames, 3)
        assert series.rate == self.expected_rate
        assert series.get_starting_time() == 0.0
        assert_array_equal(series.data[0], self.expected_first_position)
        assert series.confidence[0] == self.expected_first_confidence
        nwbfile.read_io.close()


class TestAniposeInterfaceWithoutTransformColumns(_AniposeInterfaceTestMixin):
    """The paper mouse triangulated by Anipose 0.5.2, whose pose-3d CSV predates the `M_*` and `center_*` columns."""

    data_interface_cls = AniposeInterface
    interface_kwargs = dict(
        file_path=str(
            ANIPOSE_DATA_PATH
            / "binary_data_layout"
            / "without_transform_columns_version_0_5_2"
            / "020920_preDTreaches_day2"
            / "JiDT12"
            / "pose-3d"
            / MOUSE_FILE_NAME
        ),
        calibration_file_path=str(
            ANIPOSE_DATA_PATH
            / "binary_data_layout"
            / "without_transform_columns_version_0_5_2"
            / "020920_preDTreaches_day2"
            / "JiDT12"
            / "calibration"
            / "calibration.toml"
        ),
        sampling_rate=200.0,
    )
    save_directory = OUTPUT_PATH

    expected_keypoint_names = ["l-base", "l-edge", "l-middle", "r-base", "r-edge", "r-middle"]
    expected_number_of_frames = 112
    expected_camera_names = ["cam1", "cam2"]
    expected_rate = 200.0
    expected_first_series_name = "PoseEstimationSeriesLBase"
    # Frame 0 of keypoint l-base: l-base_x, l-base_y, l-base_z and l-base_score
    expected_first_position = [3.718712567602676, 23.39811090916537, 645.528881281094]
    expected_first_confidence = 0.9983834624290466

    def check_extracted_metadata(self, metadata: dict):
        container_entry = metadata["Pose"]["MultiCameraPoseEstimations"]["anipose"]
        assert metadata["Pose"]["Skeletons"]["anipose"]["nodes"] == self.expected_keypoint_names
        camera_names = [
            metadata["Pose"]["PoseEstimations"][key]["device_metadata_key"]
            for key in container_entry["pose_estimation_metadata_keys"]
        ]
        assert camera_names == self.expected_camera_names
        # The file does not record the frame transform
        for series_entry in container_entry["PoseEstimationSeries"].values():
            assert "reference_frame" not in series_entry

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        series = nwbfile.processing["behavior"]["PoseEstimationAnipose"].pose_estimation_series[
            self.expected_first_series_name
        ]
        assert series.data.shape == (self.expected_number_of_frames, 3)
        assert series.rate == self.expected_rate
        assert series.get_starting_time() == 0.0
        assert_array_equal(series.data[0], self.expected_first_position)
        assert series.confidence[0] == self.expected_first_confidence
        nwbfile.read_io.close()


class TestAniposeInterfaceParenthesizedKeypointNames(_AniposeInterfaceTestMixin):
    """A Cheese3D mouse face with keypoint names such as `nose(bottom)` and `pad(center)`, and no calibration."""

    data_interface_cls = AniposeInterface
    interface_kwargs = dict(
        file_path=str(
            ANIPOSE_DATA_PATH
            / "keypoint_names"
            / "parenthesized"
            / "pose-3d"
            / "20231102_B15_3D-structure_anes_000_10-42-30.csv"
        ),
        # The CSV records no frame rate, so this one is only a test input
        sampling_rate=100.0,
    )
    save_directory = OUTPUT_PATH

    expected_number_of_keypoints = 28
    expected_number_of_frames = 300
    expected_rate = 100.0
    expected_first_series_name = "PoseEstimationSeriesNoseBottom"
    # Frame 0 of keypoint nose(bottom): nose(bottom)_x, nose(bottom)_y, nose(bottom)_z and nose(bottom)_score
    expected_first_position = [0.9602760377116142, -9.289249638960849, 20.603071687685038]
    expected_first_confidence = 0.9997912049293518

    def check_extracted_metadata(self, metadata: dict):
        nodes = metadata["Pose"]["Skeletons"]["anipose"]["nodes"]
        assert len(nodes) == self.expected_number_of_keypoints
        # The `pad(center)_*` columns are a keypoint, not the frame transform's `center_*` columns
        assert "pad(center)" in nodes
        assert "pad(center)" in metadata["Pose"]["MultiCameraPoseEstimations"]["anipose"]["PoseEstimationSeries"]
        assert not metadata["Pose"]["PoseEstimations"]

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        series = nwbfile.processing["behavior"]["PoseEstimationAnipose"].pose_estimation_series[
            self.expected_first_series_name
        ]
        assert series.data.shape == (self.expected_number_of_frames, 3)
        assert series.rate == self.expected_rate
        assert series.get_starting_time() == 0.0
        assert_array_equal(series.data[0], self.expected_first_position)
        assert series.confidence[0] == self.expected_first_confidence
        nwbfile.read_io.close()


class TestAniposeCalibrationFiles:
    """The calibration files on gin without pose files of their own, read beside the paper mouse's pose-3d CSV."""

    file_path = MOUSE_SESSION_PATH / "pose-3d" / MOUSE_FILE_NAME

    def test_fisheye_cameras_say_so_in_their_description(self):
        calibration_file_path = (
            ANIPOSE_DATA_PATH / "acquisition_setup" / "fisheye_five_cameras" / "calibration" / "calibration.toml"
        )
        interface = AniposeInterface(
            file_path=self.file_path, calibration_file_path=calibration_file_path, sampling_rate=200.0
        )
        devices = interface.get_metadata()["Devices"]

        expected_camera_names = [
            "CAMERA_192_168_10_14",
            "CAMERA_192_168_10_18",
            "CAMERA_192_168_10_20",
            "CAMERA_192_168_10_32",
            "CAMERA_192_168_10_38",
        ]
        expected_description = "Fisheye lens model (OpenCV fisheye): the distortion coefficients are k1, k2, k3 and k4."
        assert list(devices) == expected_camera_names
        for camera_name in expected_camera_names:
            assert devices[camera_name]["description"] == expected_description
            assert len(devices[camera_name]["distortion_coefficients"]) == 4

    def test_twelve_cameras_keep_the_order_of_the_file(self):
        calibration_file_path = (
            ANIPOSE_DATA_PATH / "acquisition_setup" / "twelve_cameras" / "calibration" / "calibration.toml"
        )
        interface = AniposeInterface(
            file_path=self.file_path, calibration_file_path=calibration_file_path, sampling_rate=200.0
        )
        devices = interface.get_metadata()["Devices"]

        # The tables cam_0 to cam_11 in file order, not sorted as strings (cam_0, cam_1, cam_10, ...)
        expected_camera_names = [
            "cam088",
            "cam091",
            "cam574",
            "cam581",
            "cam592",
            "cam593",
            "cam678",
            "cam680",
            "cam712",
            "cam746",
            "cam898",
            "cam899",
        ]
        assert list(devices) == expected_camera_names

    def test_matlab_written_calibration(self):
        calibration_file_path = (
            ANIPOSE_DATA_PATH
            / "calibration_writer"
            / "matlab_without_metadata_table"
            / "calibration"
            / "calibration.toml"
        )
        interface = AniposeInterface(
            file_path=self.file_path, calibration_file_path=calibration_file_path, sampling_rate=200.0
        )
        devices = interface.get_metadata()["Devices"]

        expected_camera_names = ["1", "2", "3", "4", "5", "6", "7", "8"]
        # Camera "1": the skew term of `matrix` and `translation`, in metres
        expected_first_intrinsic_matrix = [
            [1532.121059, 0.001715, 621.975895],
            [0.0, 1531.009154, 371.073227],
            [0.0, 0.0, 1.0],
        ]
        expected_first_translation_vector = [-0.274234, 0.845163, 5.908844]
        assert list(devices) == expected_camera_names
        assert_array_equal(devices["1"]["intrinsic_matrix"], expected_first_intrinsic_matrix)
        assert_array_equal(devices["1"]["translation_vector"], expected_first_translation_vector)
