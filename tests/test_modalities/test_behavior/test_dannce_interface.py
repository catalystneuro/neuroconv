from datetime import datetime

import numpy as np
import pytest
from ndx_pose import CalibratedCamera, MultiCameraPoseEstimation
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO, NWBFile
from pynwb.image import ImageSeries
from pynwb.testing.mock.file import mock_NWBFile, mock_Subject
from scipy.io import savemat

from neuroconv.datainterfaces import DANNCEInterface


@pytest.fixture
def dannce_mat_file(tmp_path):
    """Create a synthetic DANNCE prediction .mat file."""
    n_samples = 100
    n_landmarks = 5

    rng = np.random.default_rng(42)
    pred = rng.standard_normal((n_samples, 3, n_landmarks))
    p_max = rng.random((n_samples, n_landmarks))
    sample_id = np.arange(n_samples, dtype="float64").reshape(1, -1)  # shape (1, n_samples) like real DANNCE

    file_path = tmp_path / "save_data_AVG.mat"
    savemat(str(file_path), dict(pred=pred, p_max=p_max, sampleID=sample_id))
    return file_path, n_samples, n_landmarks, pred, p_max


@pytest.fixture
def frametimes_npy_file(tmp_path, dannce_mat_file):
    """Create a synthetic frametimes.npy file sized to the DANNCE fixture."""
    _, n_samples, _, _, _ = dannce_mat_file
    n_video_frames = n_samples + 50  # a few more frames than DANNCE predictions
    frame_indices = np.arange(1, n_video_frames + 1, dtype="float64")
    seconds = np.linspace(0.0, 3.0, n_video_frames, dtype="float64")
    frametimes = np.stack([frame_indices, seconds], axis=0)  # shape (2, n_video_frames)

    file_path = tmp_path / "frametimes.npy"
    np.save(str(file_path), frametimes)
    return file_path, seconds


@pytest.fixture
def multi_animal_dannce_mat_file(tmp_path):
    """Create a synthetic multi-animal (sDANNCE-style) prediction .mat file (2 animals)."""
    n_samples = 80
    n_animals = 2
    n_landmarks = 5

    rng = np.random.default_rng(7)
    pred = rng.standard_normal((n_samples, n_animals, 3, n_landmarks))
    p_max = rng.random((n_samples, n_animals, n_landmarks))
    sample_id = np.arange(n_samples, dtype="float64").reshape(1, -1)

    file_path = tmp_path / "save_data_AVG0.mat"
    savemat(str(file_path), dict(pred=pred, p_max=p_max, sampleID=sample_id))
    return file_path, n_samples, n_animals, n_landmarks, pred, p_max


def _synthetic_calibration_values(camera_index: int) -> dict:
    """Deterministic per-camera calibration values, shared by the calibration fixtures below."""
    return dict(
        intrinsic_matrix=np.eye(3) * (camera_index + 1),
        rotation_matrix=np.eye(3),
        translation_vector=np.array([1.0, 2.0, 3.0]) * (camera_index + 1),
        distortion_coefficients=np.array([0.1, 0.2, 0.01, 0.02]),
    )


@pytest.fixture
def hires_params_calibration_dir(tmp_path):
    """Create a directory of 'hires_camN_params.mat' files (one per camera), plus a decoy '.old' file."""
    calibration_dir = tmp_path / "calibration"
    calibration_dir.mkdir()

    camera_names = ["Camera1", "Camera2"]
    for i, camera_name in enumerate(camera_names):
        values = _synthetic_calibration_values(i)
        savemat(
            str(calibration_dir / f"hires_cam{i + 1}_params.mat"),
            dict(
                K=values["intrinsic_matrix"],
                r=values["rotation_matrix"],
                t=values["translation_vector"].reshape(1, 3),
                RDistort=values["distortion_coefficients"][:2].reshape(1, 2),
                TDistort=values["distortion_coefficients"][2:].reshape(1, 2),
            ),
        )
    # Backup file that must NOT be picked up by the 'hires_camN_params.mat' glob.
    (calibration_dir / "hires_cam1_params.mat.old").write_text("not a real calibration file")

    return calibration_dir, camera_names


@pytest.fixture
def calibration_json_file(tmp_path):
    """Create a 'calibration.json' file with 'camera_names' and 'camera_params'."""
    import json

    camera_names = ["Camera1", "Camera2"]
    camera_params = []
    for i in range(len(camera_names)):
        values = _synthetic_calibration_values(i)
        camera_params.append(
            dict(
                camera_matrix=values["intrinsic_matrix"].tolist(),
                rotation_matrix=values["rotation_matrix"].tolist(),
                translation_vector=[[v] for v in values["translation_vector"].tolist()],
                r_distort=values["distortion_coefficients"][:2].tolist(),
                t_distort=values["distortion_coefficients"][2:].tolist(),
            )
        )

    file_path = tmp_path / "calibration.json"
    with open(file_path, "w") as f:
        json.dump(dict(camera_names=camera_names, camera_params=camera_params, n_cameras=len(camera_names)), f)

    return file_path, camera_names


@pytest.fixture
def label3d_calibration_mat_file(tmp_path):
    """Create a Label3D-style '*_dannce.mat' file with 'camnames' and 'params'."""
    camera_names = ["Camera1", "Camera2"]
    params = np.empty((1, len(camera_names)), dtype=object)
    for i in range(len(camera_names)):
        values = _synthetic_calibration_values(i)
        params[0, i] = {
            "K": values["intrinsic_matrix"],
            "r": values["rotation_matrix"],
            "t": values["translation_vector"],
            "RDistort": values["distortion_coefficients"][:2],
            "TDistort": values["distortion_coefficients"][2:],
        }

    file_path = tmp_path / "sampleCAL_test_dannce.mat"
    savemat(
        str(file_path),
        dict(camnames=np.array(camera_names, dtype=object), params=params),
    )
    return file_path, camera_names


class TestDANNCEInterfaceInit:
    def test_initialization_with_sampling_rate(self, dannce_mat_file):
        file_path, n_samples, n_landmarks, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)

        assert interface._pred.shape == (n_samples, 3, n_landmarks)
        assert interface._p_max.shape == (n_samples, n_landmarks)
        assert interface._sample_id.shape == (n_samples,)

    def test_default_landmark_names(self, dannce_mat_file):
        file_path, _, n_landmarks, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)

        expected_names = [f"landmark_{i}" for i in range(n_landmarks)]
        assert interface._landmark_names == expected_names

    def test_custom_landmark_names(self, dannce_mat_file):
        file_path, _, n_landmarks, _, _ = dannce_mat_file
        names = [f"joint_{i}" for i in range(n_landmarks)]
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0, landmark_names=names)

        assert interface._landmark_names == names

    def test_wrong_landmark_count_raises(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        with pytest.raises(ValueError, match="does not match the number of landmarks"):
            DANNCEInterface(file_path=file_path, sampling_rate=30.0, landmark_names=["a", "b"])

    def test_invalid_file_suffix_raises(self, tmp_path):
        bad_file = tmp_path / "data.csv"
        bad_file.touch()
        with pytest.raises(IOError, match="Only .mat files are supported"):
            DANNCEInterface(file_path=bad_file, sampling_rate=30.0)


class TestDANNCEInterfaceAnimalIndex:
    """Coverage for multi-animal (sDANNCE-style) 4D 'pred' input, selected via animal_index."""

    def test_animal_index_0_slices_correctly(self, multi_animal_dannce_mat_file):
        file_path, n_samples, _, n_landmarks, pred, p_max = multi_animal_dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, animal_index=0, sampling_rate=30.0)

        assert interface._pred.shape == (n_samples, 3, n_landmarks)
        assert interface._p_max.shape == (n_samples, n_landmarks)
        assert_array_equal(interface._pred, pred[:, 0, :, :])
        assert_array_equal(interface._p_max, p_max[:, 0, :])

    def test_animal_index_1_slices_correctly(self, multi_animal_dannce_mat_file):
        file_path, n_samples, _, n_landmarks, pred, p_max = multi_animal_dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, animal_index=1, sampling_rate=30.0)

        assert interface._pred.shape == (n_samples, 3, n_landmarks)
        assert_array_equal(interface._pred, pred[:, 1, :, :])
        assert_array_equal(interface._p_max, p_max[:, 1, :])

    def test_out_of_range_animal_index_raises(self, multi_animal_dannce_mat_file):
        file_path, _, n_animals, _, _, _ = multi_animal_dannce_mat_file
        with pytest.raises(IndexError, match="out of range"):
            DANNCEInterface(file_path=file_path, animal_index=n_animals, sampling_rate=30.0)

    def test_4d_pred_without_animal_index_raises(self, multi_animal_dannce_mat_file):
        file_path = multi_animal_dannce_mat_file[0]
        with pytest.raises(ValueError, match="explicit animal axis"):
            DANNCEInterface(file_path=file_path, sampling_rate=30.0)

    def test_3d_pred_with_animal_index_raises(self, dannce_mat_file):
        file_path = dannce_mat_file[0]
        with pytest.raises(ValueError, match="already single-animal"):
            DANNCEInterface(file_path=file_path, animal_index=0, sampling_rate=30.0)


class TestDANNCEInterfaceTimestamps:
    def test_timestamps_from_sampling_rate(self, dannce_mat_file):
        file_path, n_samples, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)

        timestamps = interface.get_timestamps()
        expected = np.arange(n_samples, dtype="float64") / 30.0
        np.testing.assert_allclose(timestamps, expected)

    def test_get_original_timestamps(self, dannce_mat_file):
        file_path, n_samples, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)

        timestamps = interface.get_original_timestamps()
        expected = np.arange(n_samples, dtype="float64") / 30.0
        np.testing.assert_allclose(timestamps, expected)

    def test_no_timestamps_raises(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path)

        with pytest.raises(ValueError, match="Cannot compute original timestamps"):
            interface.get_timestamps()

    def test_set_aligned_timestamps(self, dannce_mat_file):
        file_path, n_samples, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path)

        custom_timestamps = np.linspace(10.0, 20.0, n_samples)
        interface.set_aligned_timestamps(custom_timestamps)

        np.testing.assert_array_equal(interface.get_timestamps(), custom_timestamps)

    def test_set_aligned_timestamps_overrides_sampling_rate(self, dannce_mat_file):
        file_path, n_samples, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)

        custom_timestamps = np.linspace(10.0, 20.0, n_samples)
        interface.set_aligned_timestamps(custom_timestamps)

        np.testing.assert_array_equal(interface.get_timestamps(), custom_timestamps)

    def test_timestamps_from_frametimes_file(self, dannce_mat_file, frametimes_npy_file):
        file_path, n_samples, _, _, _ = dannce_mat_file
        frametimes_path, seconds = frametimes_npy_file

        interface = DANNCEInterface(file_path=file_path, frametimes_file_path=frametimes_path)
        timestamps = interface.get_timestamps()

        expected = seconds[np.arange(n_samples)]
        np.testing.assert_allclose(timestamps, expected)

    def test_frametimes_takes_precedence(self, dannce_mat_file, frametimes_npy_file):
        file_path, n_samples, _, _, _ = dannce_mat_file
        frametimes_path, seconds = frametimes_npy_file

        interface = DANNCEInterface(file_path=file_path, frametimes_file_path=frametimes_path, sampling_rate=30.0)
        timestamps = interface.get_timestamps()

        expected = seconds[np.arange(n_samples)]
        np.testing.assert_allclose(timestamps, expected)
        # Confirm sampling_rate was not used (frametimes took precedence).
        sampling_rate_timestamps = np.arange(n_samples) / 30.0
        assert not np.allclose(timestamps, sampling_rate_timestamps)

    def test_get_original_timestamps_from_frametimes(self, dannce_mat_file, frametimes_npy_file):
        file_path, n_samples, _, _, _ = dannce_mat_file
        frametimes_path, seconds = frametimes_npy_file

        interface = DANNCEInterface(file_path=file_path, frametimes_file_path=frametimes_path)
        timestamps = interface.get_original_timestamps()

        np.testing.assert_allclose(timestamps, seconds[np.arange(n_samples)])


class TestDANNCEInterfaceMetadata:
    def test_metadata_structure(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)
        metadata = interface.get_metadata()

        assert "PoseEstimation" in metadata
        pe = metadata["PoseEstimation"]
        assert "Skeletons" in pe
        assert "Devices" in pe
        assert "PoseEstimationContainers" in pe

    def test_metadata_dannce_defaults(self, dannce_mat_file):
        file_path, _, n_landmarks, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)
        metadata = interface.get_metadata()

        container = metadata["PoseEstimation"]["PoseEstimationContainers"]["PoseEstimationDANNCE"]
        assert container["source_software"] == "DANNCE"
        assert container["name"] == "PoseEstimationDANNCE"

        # Check series metadata has millimeters units
        series = container["PoseEstimationSeries"]
        assert len(series) == n_landmarks
        for landmark_meta in series.values():
            assert landmark_meta["unit"] == "millimeters"

    def test_metadata_custom_key(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(
            file_path=file_path, sampling_rate=30.0, pose_estimation_metadata_key="CustomDANNCE"
        )
        metadata = interface.get_metadata()

        assert "CustomDANNCE" in metadata["PoseEstimation"]["PoseEstimationContainers"]


class TestDANNCEInterfaceCalibration:
    """Coverage for get_camera_calibrations() and the calibration_path constructor argument."""

    def _assert_matches_synthetic_values(self, camera_calibrations: dict, camera_names: list[str]) -> None:
        for i, camera_name in enumerate(camera_names):
            expected = _synthetic_calibration_values(i)
            actual = camera_calibrations[camera_name]
            assert_array_equal(actual["intrinsic_matrix"], expected["intrinsic_matrix"])
            assert_array_equal(actual["rotation_matrix"], expected["rotation_matrix"])
            assert_array_equal(actual["translation_vector"], expected["translation_vector"])
            assert_array_equal(actual["distortion_coefficients"], expected["distortion_coefficients"])

    def test_get_camera_calibrations_from_hires_params_directory(self, hires_params_calibration_dir):
        calibration_dir, camera_names = hires_params_calibration_dir
        names, camera_calibrations = DANNCEInterface.get_camera_calibrations(calibration_dir)

        assert names == camera_names
        self._assert_matches_synthetic_values(camera_calibrations, camera_names)

    def test_get_camera_calibrations_from_json(self, calibration_json_file):
        file_path, camera_names = calibration_json_file
        names, camera_calibrations = DANNCEInterface.get_camera_calibrations(file_path)

        assert names == camera_names
        self._assert_matches_synthetic_values(camera_calibrations, camera_names)

    def test_get_camera_calibrations_from_label3d_mat(self, label3d_calibration_mat_file):
        file_path, camera_names = label3d_calibration_mat_file
        names, camera_calibrations = DANNCEInterface.get_camera_calibrations(file_path)

        assert names == camera_names
        self._assert_matches_synthetic_values(camera_calibrations, camera_names)

    def test_get_camera_calibrations_nonexistent_path_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            DANNCEInterface.get_camera_calibrations(tmp_path / "does_not_exist.json")

    def test_get_camera_calibrations_unrecognized_suffix_raises(self, tmp_path):
        bad_file = tmp_path / "calibration.txt"
        bad_file.touch()
        with pytest.raises(ValueError, match="Unrecognized calibration format"):
            DANNCEInterface.get_camera_calibrations(bad_file)

    def test_calibration_path_auto_populates_camera_names(self, dannce_mat_file, hires_params_calibration_dir):
        file_path = dannce_mat_file[0]
        calibration_dir, camera_names = hires_params_calibration_dir
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0, calibration_path=calibration_dir)

        assert interface._camera_names == camera_names

    def test_explicit_camera_names_override_calibration_path(self, dannce_mat_file, hires_params_calibration_dir):
        file_path = dannce_mat_file[0]
        calibration_dir, _ = hires_params_calibration_dir
        interface = DANNCEInterface(
            file_path=file_path,
            sampling_rate=30.0,
            calibration_path=calibration_dir,
            camera_names=["CustomCam"],
        )

        assert interface._camera_names == ["CustomCam"]

    def test_calibration_path_auto_creates_calibrated_cameras(self, dannce_mat_file, hires_params_calibration_dir):
        file_path = dannce_mat_file[0]
        calibration_dir, camera_names = hires_params_calibration_dir
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0, calibration_path=calibration_dir)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)  # no camera_calibrations argument passed

        for i, camera_name in enumerate(camera_names):
            device = nwbfile.devices[camera_name]
            assert isinstance(device, CalibratedCamera)
            expected = _synthetic_calibration_values(i)
            assert_array_equal(device.intrinsic_matrix, expected["intrinsic_matrix"])

    def test_add_to_nwbfile_camera_calibrations_overrides_calibration_path(
        self, dannce_mat_file, hires_params_calibration_dir
    ):
        file_path = dannce_mat_file[0]
        calibration_dir, camera_names = hires_params_calibration_dir
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0, calibration_path=calibration_dir)

        override_intrinsic_matrix = np.eye(3) * 99
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(
            nwbfile=nwbfile,
            camera_calibrations={"Camera1": dict(intrinsic_matrix=override_intrinsic_matrix)},
        )

        # Camera1 is overridden by the explicit argument...
        assert_array_equal(nwbfile.devices["Camera1"].intrinsic_matrix, override_intrinsic_matrix)
        # ...while Camera2 still falls back to the calibration loaded from calibration_path.
        expected_camera2 = _synthetic_calibration_values(1)
        assert_array_equal(nwbfile.devices["Camera2"].intrinsic_matrix, expected_camera2["intrinsic_matrix"])


class TestDANNCEInterfaceConversion:
    def test_add_to_nwbfile(self, dannce_mat_file, tmp_path):
        file_path, n_samples, n_landmarks, pred, p_max = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)

        nwbfile = NWBFile(
            session_description="test",
            identifier="test_dannce",
            session_start_time=datetime.now().astimezone(),
        )

        interface.add_to_nwbfile(nwbfile=nwbfile)

        # Verify behavior module
        assert "behavior" in nwbfile.processing
        behavior = nwbfile.processing["behavior"]
        assert "PoseEstimationDANNCE" in behavior.data_interfaces
        assert "Skeletons" in behavior.data_interfaces

        # Verify pose estimation container
        pe = behavior.data_interfaces["PoseEstimationDANNCE"]
        assert isinstance(pe, MultiCameraPoseEstimation)
        assert len(pe.pose_estimation_series) == n_landmarks
        assert pe.source_software == "DANNCE"

        # Verify the camera device is linked via a per-camera PoseEstimation child
        assert len(pe.pose_estimations) == 1
        camera_pose_estimation = next(iter(pe.pose_estimations.values()))
        assert camera_pose_estimation.device.name == "Camera1"
        assert len(camera_pose_estimation.pose_estimation_series) == 0

        # Build name-to-index mapping (NWB may return series in alphabetical order)
        landmark_names = [f"landmark_{i}" for i in range(n_landmarks)]
        name_to_idx = {}
        for i, landmark in enumerate(landmark_names):
            landmark_capitalized = landmark.replace("_", " ").title().replace(" ", "")
            name_to_idx[f"PoseEstimationSeries{landmark_capitalized}"] = i

        # Verify data shapes and content
        for series_name, series in pe.pose_estimation_series.items():
            i = name_to_idx[series_name]
            assert series.data.shape == (n_samples, 3)
            assert_array_equal(series.data, pred[:, :, i])
            assert series.confidence.shape == (n_samples,)
            assert_array_equal(series.confidence, p_max[:, i])
            assert series.unit == "millimeters"

    def test_add_to_nwbfile_with_custom_timestamps(self, dannce_mat_file, tmp_path):
        file_path, n_samples, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path)

        # Irregular spacing so calculate_regular_series_rate returns None and
        # timestamps are stored explicitly rather than as rate+starting_time.
        rng = np.random.default_rng(0)
        custom_timestamps = np.sort(rng.uniform(0.0, 10.0, n_samples))
        interface.set_aligned_timestamps(custom_timestamps)

        nwbfile = NWBFile(
            session_description="test",
            identifier="test_dannce_ts",
            session_start_time=datetime.now().astimezone(),
        )

        interface.add_to_nwbfile(nwbfile=nwbfile)

        pe = nwbfile.processing["behavior"].data_interfaces["PoseEstimationDANNCE"]
        for series in pe.pose_estimation_series.values():
            np.testing.assert_allclose(series.timestamps[:], custom_timestamps)

    def test_roundtrip_nwb(self, dannce_mat_file, tmp_path):
        file_path, n_samples, n_landmarks, pred, p_max = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)

        nwbfile_path = tmp_path / "test_dannce.nwb"

        metadata = interface.get_metadata()
        metadata["NWBFile"] = dict(
            session_description="test session",
            identifier="test_dannce_roundtrip",
            session_start_time=datetime.now().astimezone(),
        )

        interface.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata)

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            assert "behavior" in nwbfile.processing
            pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
            assert len(pe.pose_estimation_series) == n_landmarks

            for i, series in enumerate(pe.pose_estimation_series.values()):
                assert series.data.shape == (n_samples, 3)
                assert series.confidence.shape == (n_samples,)

    def test_skeleton_subject_linking(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0, subject_name="mouse1")

        nwbfile = mock_NWBFile()
        nwbfile.subject = mock_Subject(subject_id="mouse1")

        interface.add_to_nwbfile(nwbfile=nwbfile)

        skeleton = nwbfile.processing["behavior"]["Skeletons"]["SkeletonPoseEstimationDANNCE_Mouse1"]
        assert skeleton.subject is nwbfile.subject

    def test_skeleton_subject_not_linked(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0, subject_name="mouse1")

        nwbfile = mock_NWBFile()
        nwbfile.subject = mock_Subject(subject_id="different_mouse")

        interface.add_to_nwbfile(nwbfile=nwbfile)

        skeleton = nwbfile.processing["behavior"]["Skeletons"]["SkeletonPoseEstimationDANNCE_Mouse1"]
        assert skeleton.subject is None

    def test_source_video_links(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)

        nwbfile = NWBFile(
            session_description="test",
            identifier="test_dannce_video_links",
            session_start_time=datetime.now().astimezone(),
        )

        source_video = ImageSeries(
            name="SourceVideo",
            description="Source video for DANNCE pose estimation.",
            unit="NA",
            format="external",
            external_file=["camera1.mp4"],
            rate=30.0,
            num_samples=100,
        )
        nwbfile.add_acquisition(source_video)

        interface.add_to_nwbfile(nwbfile=nwbfile, source_videos={"Camera1": source_video})

        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
        camera_pose_estimation = next(iter(pe.pose_estimations.values()))
        assert camera_pose_estimation.source_video is source_video

    def test_source_video_defaults_to_none(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
        camera_pose_estimation = next(iter(pe.pose_estimations.values()))
        assert camera_pose_estimation.source_video is None

    def test_multiple_cameras_link_distinct_source_videos(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        camera_names = ["Camera1", "Camera2", "Camera3"]
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0, camera_names=camera_names)

        nwbfile = NWBFile(
            session_description="test",
            identifier="test_dannce_multi_camera",
            session_start_time=datetime.now().astimezone(),
        )

        source_videos = {}
        for camera_name in camera_names:
            video = ImageSeries(
                name=f"SourceVideo{camera_name}",
                description=f"Source video for {camera_name}.",
                unit="NA",
                format="external",
                external_file=[f"{camera_name}.mp4"],
                rate=30.0,
                num_samples=100,
            )
            nwbfile.add_acquisition(video)
            source_videos[camera_name] = video

        # Omit the source video for the last camera to verify unmatched cameras stay linkless.
        source_videos_missing_last = dict(source_videos)
        del source_videos_missing_last[camera_names[-1]]

        interface.add_to_nwbfile(nwbfile=nwbfile, source_videos=source_videos_missing_last)

        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
        assert len(pe.pose_estimations) == len(camera_names)

        assert set(nwbfile.devices.keys()) == set(camera_names)

        camera_pose_estimations_by_device = {pe_.device.name: pe_ for pe_ in pe.pose_estimations.values()}
        for camera_name in camera_names[:-1]:
            assert camera_pose_estimations_by_device[camera_name].source_video is source_videos[camera_name]

        assert camera_pose_estimations_by_device[camera_names[-1]].source_video is None

    def test_camera_calibrations_create_calibrated_camera(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        camera_names = ["Camera1", "Camera2"]
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0, camera_names=camera_names)

        nwbfile = mock_NWBFile()

        rng = np.random.default_rng(0)
        camera_calibrations = {
            "Camera1": dict(
                intrinsic_matrix=rng.standard_normal((3, 3)),
                rotation_matrix=rng.standard_normal((3, 3)),
                translation_vector=rng.standard_normal(3),
                distortion_coefficients=rng.standard_normal(5),
            ),
            # Camera2 intentionally has no calibration entry -- should get a plain Device.
        }

        interface.add_to_nwbfile(nwbfile=nwbfile, camera_calibrations=camera_calibrations)

        camera1 = nwbfile.devices["Camera1"]
        camera2 = nwbfile.devices["Camera2"]

        assert isinstance(camera1, CalibratedCamera)
        assert_array_equal(camera1.intrinsic_matrix, camera_calibrations["Camera1"]["intrinsic_matrix"])
        assert_array_equal(camera1.rotation_matrix, camera_calibrations["Camera1"]["rotation_matrix"])
        assert_array_equal(camera1.translation_vector, camera_calibrations["Camera1"]["translation_vector"])
        assert_array_equal(camera1.distortion_coefficients, camera_calibrations["Camera1"]["distortion_coefficients"])

        assert not isinstance(camera2, CalibratedCamera)
        assert type(camera2).__name__ == "Device"

    def test_add_to_nwbfile_writes_selected_animal(self, multi_animal_dannce_mat_file):
        file_path, n_samples, _, n_landmarks, pred, p_max = multi_animal_dannce_mat_file
        interface = DANNCEInterface(
            file_path=file_path,
            animal_index=1,
            sampling_rate=30.0,
            subject_name="rat2",
            pose_estimation_metadata_key="PoseEstimationRat2",
        )

        nwbfile = NWBFile(
            session_description="test",
            identifier="test_dannce_multi_animal",
            session_start_time=datetime.now().astimezone(),
        )
        interface.add_to_nwbfile(nwbfile=nwbfile)

        pe = nwbfile.processing["behavior"][interface.pose_estimation_metadata_key]
        assert len(pe.pose_estimation_series) == n_landmarks

        landmark_names = [f"landmark_{i}" for i in range(n_landmarks)]
        name_to_idx = {}
        for i, landmark in enumerate(landmark_names):
            landmark_cap = landmark.replace("_", " ").title().replace(" ", "")
            name_to_idx[f"PoseEstimationSeries{landmark_cap}"] = i

        for series_name, series in pe.pose_estimation_series.items():
            i = name_to_idx[series_name]
            assert series.data.shape == (n_samples, 3)
            assert_array_equal(series.data, pred[:, 1, :, i])
            assert_array_equal(series.confidence, p_max[:, 1, i])

    def test_multiple_animals_share_camera_device(self, multi_animal_dannce_mat_file):
        """Multiple DANNCEInterface instances (one per animal_index) writing to the same NWBFile
        should reuse a single shared camera Device instead of each creating their own."""
        file_path = multi_animal_dannce_mat_file[0]

        nwbfile = NWBFile(
            session_description="test",
            identifier="test_dannce_shared_device",
            session_start_time=datetime.now().astimezone(),
        )

        interface_animal0 = DANNCEInterface(
            file_path=file_path,
            animal_index=0,
            sampling_rate=30.0,
            subject_name="rat1",
            pose_estimation_metadata_key="PoseEstimationRat1",
        )
        interface_animal1 = DANNCEInterface(
            file_path=file_path,
            animal_index=1,
            sampling_rate=30.0,
            subject_name="rat2",
            pose_estimation_metadata_key="PoseEstimationRat2",
        )

        interface_animal0.add_to_nwbfile(nwbfile=nwbfile)
        interface_animal1.add_to_nwbfile(nwbfile=nwbfile)

        # Only one shared camera device should have been created.
        assert list(nwbfile.devices.keys()) == ["Camera1"]

        behavior = nwbfile.processing["behavior"]
        pe_animal0 = behavior.data_interfaces["PoseEstimationRat1"]
        pe_animal1 = behavior.data_interfaces["PoseEstimationRat2"]

        camera0 = next(iter(pe_animal0.pose_estimations.values())).device
        camera1 = next(iter(pe_animal1.pose_estimations.values())).device
        assert camera0 is camera1
        assert camera0 is nwbfile.devices["Camera1"]

    def test_source_software_relabeled_via_metadata_override(self, dannce_mat_file):
        """DANNCEInterface defaults source_software/scorer to "DANNCE"; for sDANNCE-produced data,
        relabel via the standard metadata-merge mechanism rather than a dedicated subclass."""
        file_path = dannce_mat_file[0]
        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)

        metadata = interface.get_metadata()
        container = metadata["PoseEstimation"]["PoseEstimationContainers"]["PoseEstimationDANNCE"]
        container["description"] = "3D keypoint coordinates estimated using sDANNCE (social DANNCE)."
        container["source_software"] = "sDANNCE"
        container["scorer"] = "sDANNCE"

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
        assert pe.source_software == "sDANNCE"
        assert pe.scorer == "sDANNCE"
        assert "sDANNCE" in pe.description

    def test_stub_test_limits_output_samples(self, tmp_path):
        # Build a larger fixture (500 samples) so stub_test (=100) actually slices.
        n_samples = 500
        n_landmarks = 5
        rng = np.random.default_rng(0)
        pred = rng.standard_normal((n_samples, 3, n_landmarks))
        p_max = rng.random((n_samples, n_landmarks))
        sample_id = np.arange(n_samples, dtype="float64").reshape(1, -1)
        file_path = tmp_path / "save_data_AVG_big.mat"
        from scipy.io import savemat as _savemat

        _savemat(str(file_path), dict(pred=pred, p_max=p_max, sampleID=sample_id))

        interface = DANNCEInterface(file_path=file_path, sampling_rate=30.0)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, stub_test=True)

        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
        for series in pe.pose_estimation_series.values():
            assert series.data.shape[0] == 100
            assert series.confidence.shape[0] == 100

        # Internal arrays must remain untouched.
        assert interface._pred.shape[0] == n_samples
        assert interface._p_max.shape[0] == n_samples
