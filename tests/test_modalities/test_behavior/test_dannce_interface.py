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
from neuroconv.datainterfaces.behavior.dannce.danncedatainterface import _NoTimingInformationWarning


@pytest.fixture
def matlab_v73_file(tmp_path):
    """Write a minimal file with a MATLAB v7.3 (HDF5-based) header -- just enough for scipy's
    'matfile_version' header check to classify it as v7.3 and raise, without needing a real HDF5
    library or file contents (v7.3 files are never actually valid DANNCE/sDANNCE output)."""
    file_path = tmp_path / "save_data_AVG.mat"
    header = b"\x01" * 124 + bytes([2, 0, 0, 0])  # bytes 124:128 decode to major version 2 ("v7.3")
    file_path.write_bytes(header)
    return file_path


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
def split_dannce_mat_files(tmp_path):
    """Create two synthetic DANNCE prediction .mat files with contiguous sampleID ranges, mimicking
    an sDANNCE run split across two job files (e.g. 'save_data_AVG0.mat' + 'save_data_AVG25.mat')."""
    n_samples_per_file = 25
    n_landmarks = 4

    rng = np.random.default_rng(99)
    pred_0 = rng.standard_normal((n_samples_per_file, 3, n_landmarks))
    p_max_0 = rng.random((n_samples_per_file, n_landmarks))
    sample_id_0 = np.arange(0, n_samples_per_file, dtype="float64").reshape(1, -1)

    pred_1 = rng.standard_normal((n_samples_per_file, 3, n_landmarks))
    p_max_1 = rng.random((n_samples_per_file, n_landmarks))
    sample_id_1 = np.arange(n_samples_per_file, 2 * n_samples_per_file, dtype="float64").reshape(1, -1)

    file_path_0 = tmp_path / "save_data_AVG0.mat"
    file_path_1 = tmp_path / "save_data_AVG25.mat"
    savemat(str(file_path_0), dict(pred=pred_0, p_max=p_max_0, sampleID=sample_id_0))
    savemat(str(file_path_1), dict(pred=pred_1, p_max=p_max_1, sampleID=sample_id_1))

    return dict(
        file_paths=[file_path_0, file_path_1],
        n_landmarks=n_landmarks,
        expected_pred=np.concatenate([pred_0, pred_1], axis=0),
        expected_p_max=np.concatenate([p_max_0, p_max_1], axis=0),
        expected_sample_id=np.concatenate([sample_id_0.squeeze(), sample_id_1.squeeze()]),
    )


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


@pytest.fixture
def singleton_animal_dannce_mat_file(tmp_path):
    """Create a synthetic sDANNCE-style prediction .mat file with a singleton animal axis
    (n_animals == 1) -- e.g. a run configured for multi-animal output that only ever predicted one."""
    n_samples = 30
    n_landmarks = 4

    rng = np.random.default_rng(13)
    pred = rng.standard_normal((n_samples, 1, 3, n_landmarks))
    p_max = rng.random((n_samples, 1, n_landmarks))
    sample_id = np.arange(n_samples, dtype="float64").reshape(1, -1)

    file_path = tmp_path / "save_data_AVG0.mat"
    savemat(str(file_path), dict(pred=pred, p_max=p_max, sampleID=sample_id))
    return file_path, n_samples, n_landmarks, pred, p_max


def _synthetic_calibration_values(camera_index: int) -> dict:
    """Deterministic per-camera calibration values, shared by the calibration fixtures below."""
    return dict(
        intrinsic_matrix=np.eye(3) * (camera_index + 1),
        rotation_matrix=np.eye(3),
        translation_vector=np.array([1.0, 2.0, 3.0]) * (camera_index + 1),
        distortion_coefficients=np.array([0.1, 0.2, 0.01, 0.02]),
    )


@pytest.fixture(params=["hires_", "kyle_"])
def params_calibration_dir(request, tmp_path):
    """Create a directory of '<prefix>camN_params.mat' files (one per camera), plus a decoy '.old'
    file."""
    prefix = request.param
    calibration_dir = tmp_path / "calibration"
    calibration_dir.mkdir()

    camera_names = ["Camera1", "Camera2"]
    for i, camera_name in enumerate(camera_names):
        values = _synthetic_calibration_values(i)
        savemat(
            str(calibration_dir / f"{prefix}cam{i + 1}_params.mat"),
            dict(
                K=values["intrinsic_matrix"],
                r=values["rotation_matrix"],
                t=values["translation_vector"].reshape(1, 3),
                RDistort=values["distortion_coefficients"][:2].reshape(1, 2),
                TDistort=values["distortion_coefficients"][2:].reshape(1, 2),
            ),
        )
    # Backup file that must NOT be picked up by the 'camN_params.mat' glob.
    (calibration_dir / f"{prefix}cam1_params.mat.old").write_text("not a real calibration file")

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
    with open(file_path, "w", encoding="utf-8") as f:
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
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        assert interface._pred.shape == (n_samples, 3, n_landmarks)
        assert interface._p_max.shape == (n_samples, n_landmarks)
        assert interface._sample_id.shape == (n_samples,)

    def test_default_landmark_names(self, dannce_mat_file):
        file_path, _, n_landmarks, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        expected_names = [f"landmark_{i}" for i in range(n_landmarks)]
        assert interface._landmark_names == expected_names

    def test_custom_landmark_names(self, dannce_mat_file):
        file_path, _, n_landmarks, _, _ = dannce_mat_file
        names = [f"joint_{i}" for i in range(n_landmarks)]
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, landmark_names=names)

        assert interface._landmark_names == names

    def test_wrong_landmark_count_raises(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        with pytest.raises(ValueError, match="does not match the number of landmarks"):
            DANNCEInterface(file_paths=file_path, sampling_rate=30.0, landmark_names=["a", "b"])

    def test_invalid_file_suffix_raises(self, tmp_path):
        bad_file = tmp_path / "data.csv"
        bad_file.touch()
        with pytest.raises(IOError, match="Only .mat files are supported"):
            DANNCEInterface(file_paths=bad_file, sampling_rate=30.0)


class TestDANNCEInterfaceMultiFile:
    """Coverage for 'file_paths' accepting a list, concatenating multiple prediction files into one
    continuous session (e.g. sDANNCE jobs split across batches)."""

    def test_concatenates_in_given_order(self, split_dannce_mat_files):
        fixture = split_dannce_mat_files
        interface = DANNCEInterface(file_paths=fixture["file_paths"], sampling_rate=30.0)

        assert interface._pred.shape == fixture["expected_pred"].shape
        assert_array_equal(interface._pred, fixture["expected_pred"])
        assert_array_equal(interface._p_max, fixture["expected_p_max"])
        assert_array_equal(interface._sample_id, fixture["expected_sample_id"])

    def test_single_path_in_list_matches_bare_path(self, dannce_mat_file):
        file_path, n_samples, n_landmarks, pred, p_max = dannce_mat_file
        interface_from_list = DANNCEInterface(file_paths=[file_path], sampling_rate=30.0)
        interface_from_path = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        assert_array_equal(interface_from_list._pred, interface_from_path._pred)
        assert_array_equal(interface_from_list._p_max, interface_from_path._p_max)

    def test_mismatched_landmark_count_raises(self, tmp_path):
        n_samples = 10
        rng = np.random.default_rng(1)

        file_path_0 = tmp_path / "save_data_AVG0.mat"
        savemat(
            str(file_path_0),
            dict(
                pred=rng.standard_normal((n_samples, 3, 4)),
                p_max=rng.random((n_samples, 4)),
                sampleID=np.arange(0, n_samples, dtype="float64").reshape(1, -1),
            ),
        )
        file_path_1 = tmp_path / "save_data_AVG10.mat"
        savemat(
            str(file_path_1),
            dict(
                pred=rng.standard_normal((n_samples, 3, 5)),  # different landmark count
                p_max=rng.random((n_samples, 5)),
                sampleID=np.arange(n_samples, 2 * n_samples, dtype="float64").reshape(1, -1),
            ),
        )

        with pytest.raises(ValueError, match="does not match the first file"):
            DANNCEInterface(file_paths=[file_path_0, file_path_1], sampling_rate=30.0)

    def test_multi_file_writes_to_nwbfile(self, split_dannce_mat_files):
        fixture = split_dannce_mat_files
        interface = DANNCEInterface(file_paths=fixture["file_paths"], sampling_rate=30.0)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
        assert len(pe.pose_estimation_series) == fixture["n_landmarks"]
        for series in pe.pose_estimation_series.values():
            assert series.data.shape[0] == fixture["expected_pred"].shape[0]


class TestDANNCEInterfaceAnimalIndex:
    """Coverage for multi-animal (sDANNCE-style) 4D 'pred' input, selected via animal_index."""

    def test_animal_index_0_slices_correctly(self, multi_animal_dannce_mat_file):
        file_path, n_samples, _, n_landmarks, pred, p_max = multi_animal_dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, animal_index=0, sampling_rate=30.0)

        assert interface._pred.shape == (n_samples, 3, n_landmarks)
        assert interface._p_max.shape == (n_samples, n_landmarks)
        assert_array_equal(interface._pred, pred[:, 0, :, :])
        assert_array_equal(interface._p_max, p_max[:, 0, :])

    def test_animal_index_1_slices_correctly(self, multi_animal_dannce_mat_file):
        file_path, n_samples, _, n_landmarks, pred, p_max = multi_animal_dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, animal_index=1, sampling_rate=30.0)

        assert interface._pred.shape == (n_samples, 3, n_landmarks)
        assert_array_equal(interface._pred, pred[:, 1, :, :])
        assert_array_equal(interface._p_max, p_max[:, 1, :])

    def test_out_of_range_animal_index_raises(self, multi_animal_dannce_mat_file):
        file_path, _, n_animals, _, _, _ = multi_animal_dannce_mat_file
        with pytest.raises(IndexError, match="out of range"):
            DANNCEInterface(file_paths=file_path, animal_index=n_animals, sampling_rate=30.0)

    def test_4d_pred_without_animal_index_raises(self, multi_animal_dannce_mat_file):
        file_path = multi_animal_dannce_mat_file[0]
        with pytest.raises(ValueError, match="explicit animal axis"):
            DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

    def test_singleton_animal_axis_defaults_animal_index_to_0(self, singleton_animal_dannce_mat_file):
        """A 4D 'pred' with a singleton animal axis (n_animals == 1) has only one possible
        selection, so 'animal_index' should default to 0 instead of requiring it explicitly."""
        file_path, n_samples, n_landmarks, pred, p_max = singleton_animal_dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        assert interface._animal_index == 0
        assert interface._pred.shape == (n_samples, 3, n_landmarks)
        assert_array_equal(interface._pred, pred[:, 0, :, :])
        assert_array_equal(interface._p_max, p_max[:, 0, :])

    def test_singleton_animal_axis_explicit_animal_index_0_matches_default(self, singleton_animal_dannce_mat_file):
        file_path = singleton_animal_dannce_mat_file[0]
        interface_default = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)
        interface_explicit = DANNCEInterface(file_paths=file_path, animal_index=0, sampling_rate=30.0)

        assert_array_equal(interface_default._pred, interface_explicit._pred)

    def test_3d_pred_with_animal_index_raises(self, dannce_mat_file):
        file_path = dannce_mat_file[0]
        with pytest.raises(ValueError, match="already single-animal"):
            DANNCEInterface(file_paths=file_path, animal_index=0, sampling_rate=30.0)


class TestDANNCEInterfaceTimestamps:
    def test_timestamps_from_sampling_rate(self, dannce_mat_file):
        file_path, n_samples, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        timestamps = interface.alignment[interface.metadata_key].get_times()
        expected = np.arange(n_samples, dtype="float64") / 30.0
        np.testing.assert_allclose(timestamps, expected)

    def test_get_original_timestamps(self, dannce_mat_file):
        file_path, n_samples, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        timestamps = interface.get_original_timestamps()
        expected = np.arange(n_samples, dtype="float64") / 30.0
        np.testing.assert_allclose(timestamps, expected)

    def test_no_timestamps_raises(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path)

        with pytest.raises(ValueError, match="No timing information is available"):
            interface.alignment[interface.metadata_key].get_times()

    def test_no_timestamps_raises_on_write(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path)

        with pytest.raises(ValueError, match="No timing information is available"):
            interface.add_to_nwbfile(nwbfile=mock_NWBFile())

    def test_alignment_has_one_key(self, dannce_mat_file):
        file_path = dannce_mat_file[0]
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        assert interface.alignment.keys() == (interface.metadata_key,)

    def test_set_times(self, dannce_mat_file):
        file_path, n_samples, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path)

        custom_timestamps = np.linspace(10.0, 20.0, n_samples)
        interface.alignment[interface.metadata_key].set_times(custom_timestamps)

        np.testing.assert_array_equal(interface.alignment[interface.metadata_key].get_times(), custom_timestamps)

    def test_set_times_overrides_sampling_rate(self, dannce_mat_file):
        file_path, n_samples, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        custom_timestamps = np.linspace(10.0, 20.0, n_samples)
        interface.alignment[interface.metadata_key].set_times(custom_timestamps)

        np.testing.assert_array_equal(interface.alignment[interface.metadata_key].get_times(), custom_timestamps)

    def test_shift_times(self, dannce_mat_file):
        file_path, n_samples, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        interface.alignment.shift_times(5.0)

        expected = np.arange(n_samples, dtype="float64") / 30.0 + 5.0
        np.testing.assert_allclose(interface.alignment[interface.metadata_key].get_times(), expected)


class TestDANNCEInterfaceMetadata:
    def test_metadata_structure(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)
        metadata = interface.get_metadata()

        assert "Devices" in metadata
        pose = metadata["Pose"]
        assert "Skeletons" in pose
        assert "PoseEstimations" in pose
        assert "MultiCameraPoseEstimations" in pose

    def test_metadata_dannce_defaults(self, dannce_mat_file):
        file_path, _, n_landmarks, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)
        metadata = interface.get_metadata()

        assert interface.metadata_key == "dannce"
        container = metadata["Pose"]["MultiCameraPoseEstimations"]["dannce"]
        assert container["source_software"] == "DANNCE"
        assert container["name"] == "PoseEstimationDANNCE"

        # Only what the format defines: units and confidence, no invented free text
        series = container["PoseEstimationSeries"]
        assert len(series) == n_landmarks
        for landmark_meta in series.values():
            assert landmark_meta["unit"] == "millimeters"
            assert "description" not in landmark_meta
            assert "reference_frame" not in landmark_meta
        assert "description" not in container

    def test_multi_animal_default_keys_and_names(self, multi_animal_dannce_mat_file):
        file_path = multi_animal_dannce_mat_file[0]
        interface = DANNCEInterface(file_paths=file_path, animal_index=1, sampling_rate=30.0)
        metadata = interface.get_metadata()

        assert interface.metadata_key == "dannce_animal_1"
        container = metadata["Pose"]["MultiCameraPoseEstimations"]["dannce_animal_1"]
        assert container["name"] == "PoseEstimationDANNCEAnimal1"
        assert metadata["Pose"]["Skeletons"]["dannce_animal_1"]["name"] == "SkeletonPoseEstimationDANNCEAnimal1"

    def test_singleton_animal_axis_uses_single_animal_names(self, singleton_animal_dannce_mat_file):
        interface = DANNCEInterface(file_paths=singleton_animal_dannce_mat_file[0], sampling_rate=30.0)

        assert interface.metadata_key == "dannce"
        assert interface.get_metadata()["Pose"]["MultiCameraPoseEstimations"]["dannce"]["name"] == (
            "PoseEstimationDANNCE"
        )

    def test_subject_name_names_key_container_and_skeleton(self, dannce_mat_file):
        interface = DANNCEInterface(file_paths=dannce_mat_file[0], sampling_rate=30.0, subject_name="Rat 1")
        metadata = interface.get_metadata()

        assert interface.metadata_key == "dannce_rat_1"
        assert metadata["Pose"]["MultiCameraPoseEstimations"]["dannce_rat_1"]["name"] == "PoseEstimationDANNCERat1"
        skeleton = metadata["Pose"]["Skeletons"]["dannce_rat_1"]
        assert skeleton["name"] == "SkeletonPoseEstimationDANNCERat1"
        assert skeleton["subject"] == "Rat 1"

    def test_subject_name_wins_over_animal_index(self, multi_animal_dannce_mat_file):
        interface = DANNCEInterface(
            file_paths=multi_animal_dannce_mat_file[0], animal_index=1, sampling_rate=30.0, subject_name="rat2"
        )

        assert interface.metadata_key == "dannce_rat2"
        assert interface.get_metadata()["Pose"]["MultiCameraPoseEstimations"]["dannce_rat2"]["name"] == (
            "PoseEstimationDANNCERat2"
        )

    def test_explicit_metadata_key_keeps_subject_based_names(self, dannce_mat_file):
        interface = DANNCEInterface(
            file_paths=dannce_mat_file[0], sampling_rate=30.0, subject_name="rat1", metadata_key="my_key"
        )

        assert interface.metadata_key == "my_key"
        assert interface.get_metadata()["Pose"]["MultiCameraPoseEstimations"]["my_key"]["name"] == (
            "PoseEstimationDANNCERat1"
        )

    def test_metadata_template(self, dannce_mat_file):
        file_path, _, n_landmarks, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, camera_names=["Camera1", "Camera2"])
        template = interface.get_metadata_template()

        container = template["Pose"]["MultiCameraPoseEstimations"]["dannce"]
        assert container["name"] == "PoseEstimationDANNCE"
        assert container["description"] is None
        assert len(container["pose_estimation_metadata_keys"]) == 2
        for series in container["PoseEstimationSeries"].values():
            assert series["unit"] == "millimeters"
            assert series["reference_frame"] is None
        for camera_metadata_key in container["pose_estimation_metadata_keys"]:
            camera_entry = template["Pose"]["PoseEstimations"][camera_metadata_key]
            assert camera_entry["source_video_metadata_key"] is None
            assert camera_entry["device_metadata_key"] in template["Devices"]

    def test_metadata_template_writes(self, dannce_mat_file):
        """The template, with its series blanks filled, writes a file."""
        file_path = dannce_mat_file[0]
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)
        template = interface.get_metadata_template()
        for landmark, series in template["Pose"]["MultiCameraPoseEstimations"]["dannce"][
            "PoseEstimationSeries"
        ].items():
            series.update(description=f"3D position of {landmark}.", reference_frame="Origin at the arena center.")
        # No camera model recorded: delete it, and the cross-reference pointing at it.
        del template["DeviceModels"]["camera_model"]
        for device_entry in template["Devices"].values():
            del device_entry["device_model_metadata_key"]

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=template)

        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
        for series in pe.pose_estimation_series.values():
            assert series.reference_frame == "Origin at the arena center."

    def test_metadata_custom_key(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, metadata_key="CustomDANNCE")
        metadata = interface.get_metadata()

        assert "CustomDANNCE" in metadata["Pose"]["MultiCameraPoseEstimations"]


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

    def test_get_camera_calibrations_from_params_directory(self, params_calibration_dir):
        """The '<prefix>camN_params.mat' directory format must not be hardcoded to a single prefix --
        'params_calibration_dir' is parametrized over prefixes observed in real DANNCE data (e.g.
        'hires_', 'kyle_') and must load identically regardless."""
        calibration_dir, camera_names = params_calibration_dir
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

    def test_calibration_path_auto_populates_camera_names(self, dannce_mat_file, params_calibration_dir):
        file_path = dannce_mat_file[0]
        calibration_dir, camera_names = params_calibration_dir
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, calibration_path=calibration_dir)

        assert interface._camera_names == camera_names

    def test_explicit_camera_names_override_calibration_path(self, dannce_mat_file, params_calibration_dir):
        file_path = dannce_mat_file[0]
        calibration_dir, _ = params_calibration_dir
        interface = DANNCEInterface(
            file_paths=file_path,
            sampling_rate=30.0,
            calibration_path=calibration_dir,
            camera_names=["CustomCam"],
        )

        assert interface._camera_names == ["CustomCam"]

    def test_calibration_path_marks_devices_metadata_as_calibrated_camera(
        self, dannce_mat_file, params_calibration_dir
    ):
        """calibration_path writes the non-generic device type the unified way: a ``type`` field plus
        the calibration fields on each ``metadata["Devices"]`` entry, resolved at write time."""
        file_path = dannce_mat_file[0]
        calibration_dir, camera_names = params_calibration_dir
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, calibration_path=calibration_dir)

        devices_metadata = interface.get_metadata()["Devices"]
        for i, camera_name in enumerate(camera_names):
            entry = devices_metadata[camera_name]
            assert entry["type"] == "CalibratedCamera"
            expected = _synthetic_calibration_values(i)
            assert_array_equal(entry["intrinsic_matrix"], expected["intrinsic_matrix"])
            assert_array_equal(entry["rotation_matrix"], expected["rotation_matrix"])
            assert_array_equal(entry["translation_vector"], expected["translation_vector"])
            assert_array_equal(entry["distortion_coefficients"], expected["distortion_coefficients"])

    def test_no_calibration_leaves_devices_metadata_generic(self, dannce_mat_file):
        file_path = dannce_mat_file[0]
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, camera_names=["Camera1"])

        entry = interface.get_metadata()["Devices"]["Camera1"]
        assert "type" not in entry
        assert "intrinsic_matrix" not in entry

    def test_calibration_path_auto_creates_calibrated_cameras(self, dannce_mat_file, params_calibration_dir):
        file_path = dannce_mat_file[0]
        calibration_dir, camera_names = params_calibration_dir
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, calibration_path=calibration_dir)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)  # calibration comes from calibration_path via metadata["Devices"]

        for i, camera_name in enumerate(camera_names):
            device = nwbfile.devices[camera_name]
            assert isinstance(device, CalibratedCamera)
            expected = _synthetic_calibration_values(i)
            assert_array_equal(device.intrinsic_matrix, expected["intrinsic_matrix"])

    def test_metadata_devices_edit_overrides_calibration_path(self, dannce_mat_file, params_calibration_dir):
        file_path = dannce_mat_file[0]
        calibration_dir, camera_names = params_calibration_dir
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, calibration_path=calibration_dir)

        # calibration_path pre-fills each camera's Devices entry as a CalibratedCamera; editing that
        # entry before the write is how a value is overridden.
        metadata = interface.get_metadata()
        assert metadata["Devices"]["Camera1"]["type"] == "CalibratedCamera"
        override_intrinsic_matrix = np.eye(3) * 99
        metadata["Devices"]["Camera1"]["intrinsic_matrix"] = override_intrinsic_matrix

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # Camera1 is overridden by the metadata edit...
        assert isinstance(nwbfile.devices["Camera1"], CalibratedCamera)
        assert_array_equal(nwbfile.devices["Camera1"].intrinsic_matrix, override_intrinsic_matrix)
        # ...while Camera2 still falls back to the calibration loaded from calibration_path.
        expected_camera2 = _synthetic_calibration_values(1)
        assert_array_equal(nwbfile.devices["Camera2"].intrinsic_matrix, expected_camera2["intrinsic_matrix"])


class TestDANNCEInterfaceMatlabV73:
    """Prediction files are written by DANNCE/sDANNCE through scipy and are never MATLAB v7.3, so a v7.3
    file passed as one raises a clear error. Label3D, sync and calibration files are read with pymatreader,
    which handles v7.3; that is covered on real data (``com_dannce.mat``) in the on-data tests."""

    def test_prediction_file_raises_clear_error(self, matlab_v73_file):
        with pytest.raises(ValueError, match="MATLAB v7.3"):
            DANNCEInterface(file_paths=matlab_v73_file, sampling_rate=30.0)


def _write_sync_entry_cells(camera_names, sample_ids, frames_per_camera):
    sync = np.empty((len(camera_names), 1), dtype=object)
    for index, frames in enumerate(frames_per_camera):
        sync[index, 0] = dict(
            data_sampleID=np.asarray(sample_ids, dtype="float64"), data_frame=np.asarray(frames, dtype="float64")
        )
    return sync


@pytest.fixture
def classic_dannce_mat_file(tmp_path):
    """Predictions with classic-DANNCE sampleIDs (1, 11, 21, ...), which are not frame indices."""
    n_samples, n_landmarks = 10, 4
    rng = np.random.default_rng(0)
    sample_ids = 1 + 10 * np.arange(n_samples, dtype="float64")
    file_path = tmp_path / "save_data_AVG.mat"
    savemat(
        str(file_path),
        dict(
            pred=rng.standard_normal((n_samples, 3, n_landmarks)),
            p_max=rng.random((n_samples, n_landmarks)),
            sampleID=sample_ids.reshape(1, -1),
        ),
    )
    return file_path, sample_ids


class TestDANNCEInterfaceSync:
    """A sampleID is a row label of the sync table; its video frame comes from the 'data_frame' column."""

    def test_label3d_sync_maps_sample_ids_to_frames(self, tmp_path, classic_dannce_mat_file):
        file_path, sample_ids = classic_dannce_mat_file
        sync_path = tmp_path / "label3d_dannce.mat"
        camera_names = ["Camera1", "Camera2"]
        frames = np.arange(len(sample_ids))
        savemat(
            str(sync_path),
            dict(
                camnames=np.array(camera_names, dtype=object).reshape(1, -1),
                sync=_write_sync_entry_cells(camera_names, sample_ids, [frames, frames]),
            ),
        )

        interface = DANNCEInterface(
            file_paths=file_path, sampling_rate=100.0, sync_path=sync_path, camera_names=camera_names
        )

        assert_array_equal(interface.video_frame_indices, frames)
        np.testing.assert_allclose(interface.alignment[interface.metadata_key].get_times(), frames / 100.0)

    def test_sync_directory_layout(self, tmp_path, classic_dannce_mat_file):
        file_path, sample_ids = classic_dannce_mat_file
        sync_dir = tmp_path / "sync"
        sync_dir.mkdir()
        frames = np.arange(len(sample_ids)) + 3  # predictions start a few frames into the video
        for camera_name in ("Camera1", "Camera2", "Camera10"):
            savemat(
                str(sync_dir / f"{camera_name}_sync.mat"),
                dict(data_sampleID=sample_ids, data_frame=frames.astype("float64")),
            )

        interface = DANNCEInterface(file_paths=file_path, sampling_rate=100.0, sync_path=sync_dir)

        assert_array_equal(interface.video_frame_indices, frames)
        np.testing.assert_allclose(interface.alignment[interface.metadata_key].get_times(), frames / 100.0)

    def test_struct_array_layout(self, tmp_path, classic_dannce_mat_file):
        """A MATLAB struct array (rather than Label3D's cell array) is read the same way."""
        file_path, sample_ids = classic_dannce_mat_file
        sync = np.empty((1, 2), dtype=[("data_sampleID", "O"), ("data_frame", "O")])
        frames = np.arange(len(sample_ids)).astype("float64")
        for index in range(2):
            sync[0, index] = (sample_ids, frames)
        sync_path = tmp_path / "struct_dannce.mat"
        savemat(str(sync_path), dict(sync=sync))

        interface = DANNCEInterface(file_paths=file_path, sampling_rate=100.0, sync_path=sync_path)

        assert_array_equal(interface.video_frame_indices, frames)

    def test_without_sync_samples_are_consecutive_frames(self, classic_dannce_mat_file):
        file_path, sample_ids = classic_dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=100.0)

        assert interface.video_frame_indices is None
        np.testing.assert_allclose(
            interface.alignment[interface.metadata_key].get_times(), np.arange(len(sample_ids)) / 100.0
        )

    def test_sample_id_missing_from_sync_raises(self, tmp_path, classic_dannce_mat_file):
        file_path, sample_ids = classic_dannce_mat_file
        sync_path = tmp_path / "label3d_dannce.mat"
        savemat(
            str(sync_path),
            dict(sync=_write_sync_entry_cells(["Camera1"], sample_ids[:-2], [np.arange(len(sample_ids) - 2)])),
        )

        with pytest.raises(ValueError, match="2 of the 10 predicted sampleIDs are not in the sync table"):
            DANNCEInterface(file_paths=file_path, sampling_rate=100.0, sync_path=sync_path)

    def test_cameras_that_disagree_warn(self, tmp_path, classic_dannce_mat_file):
        file_path, sample_ids = classic_dannce_mat_file
        frames = np.arange(len(sample_ids))
        sync_path = tmp_path / "label3d_dannce.mat"
        savemat(
            str(sync_path),
            dict(
                camnames=np.array(["Camera1", "Camera2"], dtype=object).reshape(1, -1),
                sync=_write_sync_entry_cells(["Camera1", "Camera2"], sample_ids, [frames, frames + 1]),
            ),
        )

        with pytest.warns(UserWarning, match="camera 'Camera2' maps some sampleIDs to different frames"):
            interface = DANNCEInterface(
                file_paths=file_path, sampling_rate=100.0, sync_path=sync_path, camera_names=["Camera1", "Camera2"]
            )
        assert_array_equal(interface.video_frame_indices, frames)

    def test_mat_file_without_sync_raises(self, tmp_path, classic_dannce_mat_file):
        file_path, _ = classic_dannce_mat_file
        not_sync_path = tmp_path / "params_only.mat"
        savemat(str(not_sync_path), dict(K=np.eye(3)))

        with pytest.raises(ValueError, match="has no 'sync' table"):
            DANNCEInterface(file_paths=file_path, sampling_rate=100.0, sync_path=not_sync_path)

    def test_no_sampling_rate_warns_at_init(self, classic_dannce_mat_file):
        with pytest.warns(_NoTimingInformationWarning, match="no 'sampling_rate' was given"):
            DANNCEInterface(file_paths=classic_dannce_mat_file[0])


class TestDANNCEInterfaceConversion:
    def test_add_to_nwbfile(self, dannce_mat_file, tmp_path):
        file_path, n_samples, n_landmarks, pred, p_max = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

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
        interface = DANNCEInterface(file_paths=file_path)

        # Irregular spacing so calculate_regular_series_rate returns None and
        # timestamps are stored explicitly rather than as rate+starting_time.
        rng = np.random.default_rng(0)
        custom_timestamps = np.sort(rng.uniform(0.0, 10.0, n_samples))
        interface.alignment[interface.metadata_key].set_times(custom_timestamps)

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
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

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
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, subject_name="mouse1")

        nwbfile = mock_NWBFile()
        nwbfile.subject = mock_Subject(subject_id="mouse1")

        interface.add_to_nwbfile(nwbfile=nwbfile)

        skeleton = nwbfile.processing["behavior"]["Skeletons"]["SkeletonPoseEstimationDANNCEMouse1"]
        assert skeleton.subject is nwbfile.subject

    def test_skeleton_subject_not_linked(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, subject_name="mouse1")

        nwbfile = mock_NWBFile()
        nwbfile.subject = mock_Subject(subject_id="different_mouse")

        interface.add_to_nwbfile(nwbfile=nwbfile)

        skeleton = nwbfile.processing["behavior"]["Skeletons"]["SkeletonPoseEstimationDANNCEMouse1"]
        assert skeleton.subject is None

    def test_no_subject_name_links_the_file_subject(self, dannce_mat_file):
        interface = DANNCEInterface(file_paths=dannce_mat_file[0], sampling_rate=30.0)

        nwbfile = mock_NWBFile()
        nwbfile.subject = mock_Subject(subject_id="any_mouse")
        interface.add_to_nwbfile(nwbfile=nwbfile)

        skeleton = nwbfile.processing["behavior"]["Skeletons"]["SkeletonPoseEstimationDANNCE"]
        assert skeleton.subject is nwbfile.subject

    def test_separate_files_with_subject_names_write_together(self, dannce_mat_file, tmp_path):
        """Animals predicted in separate files get distinct names from subject_name alone."""
        file_path, n_samples, n_landmarks, _, _ = dannce_mat_file
        rng = np.random.default_rng(1)
        other_file_path = tmp_path / "save_data_AVG_rat2.mat"
        savemat(
            str(other_file_path),
            dict(
                pred=rng.standard_normal((n_samples, 3, n_landmarks)),
                p_max=rng.random((n_samples, n_landmarks)),
                sampleID=np.arange(n_samples, dtype="float64").reshape(1, -1),
            ),
        )
        interface_rat1 = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, subject_name="rat1")
        interface_rat2 = DANNCEInterface(file_paths=other_file_path, sampling_rate=30.0, subject_name="rat2")

        nwbfile = mock_NWBFile()
        interface_rat1.add_to_nwbfile(nwbfile=nwbfile)
        interface_rat2.add_to_nwbfile(nwbfile=nwbfile)

        behavior = nwbfile.processing["behavior"]
        pe_rat1 = behavior["PoseEstimationDANNCERat1"]
        pe_rat2 = behavior["PoseEstimationDANNCERat2"]
        assert pe_rat1.skeleton.name == "SkeletonPoseEstimationDANNCERat1"
        assert pe_rat2.skeleton.name == "SkeletonPoseEstimationDANNCERat2"
        assert list(nwbfile.devices) == ["Camera1"]

    def test_reusing_a_skeleton_name_with_other_nodes_raises(self, dannce_mat_file):
        """A skeleton is shared by name only when it is the same skeleton."""
        file_path, _, n_landmarks, _, _ = dannce_mat_file
        interface_a = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)
        interface_b = DANNCEInterface(
            file_paths=file_path, sampling_rate=30.0, landmark_names=[f"node_{i}" for i in range(n_landmarks)]
        )

        nwbfile = mock_NWBFile()
        interface_a.add_to_nwbfile(nwbfile=nwbfile)
        metadata_b = interface_b.get_metadata()
        metadata_b["Pose"]["MultiCameraPoseEstimations"]["dannce"]["name"] = "PoseEstimationDANNCERunB"

        with pytest.raises(ValueError, match="already has a skeleton named"):
            interface_b.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata_b)

    def test_source_video_links(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

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

        metadata = interface.get_metadata()
        metadata["Behavior"]["ExternalVideos"]["video_camera1"] = dict(name="SourceVideo")
        metadata["Pose"]["PoseEstimations"]["dannce_Camera1_pose_estimation"][
            "source_video_metadata_key"
        ] = "video_camera1"
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
        camera_pose_estimation = next(iter(pe.pose_estimations.values()))
        assert camera_pose_estimation.source_video is source_video

    def test_source_video_written_after_pose_raises(self, dannce_mat_file):
        file_path = dannce_mat_file[0]
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        metadata = interface.get_metadata()
        metadata["Behavior"]["ExternalVideos"]["video_camera1"] = dict(name="SourceVideo")
        metadata["Pose"]["PoseEstimations"]["dannce_Camera1_pose_estimation"][
            "source_video_metadata_key"
        ] = "video_camera1"

        with pytest.raises(ValueError, match="has to be written before the pose"):
            interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)

    def test_source_video_defaults_to_none(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
        camera_pose_estimation = next(iter(pe.pose_estimations.values()))
        assert camera_pose_estimation.source_video is None

    def test_multiple_cameras_link_distinct_source_videos(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        camera_names = ["Camera1", "Camera2", "Camera3"]
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, camera_names=camera_names)

        nwbfile = NWBFile(
            session_description="test",
            identifier="test_dannce_multi_camera",
            session_start_time=datetime.now().astimezone(),
        )

        metadata = interface.get_metadata()
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
            metadata["Behavior"]["ExternalVideos"][f"video_{camera_name}"] = dict(name=video.name)

        # Link every camera but the last, to verify unlinked cameras stay without a source video.
        for camera_name in camera_names[:-1]:
            metadata["Pose"]["PoseEstimations"][f"dannce_{camera_name}_pose_estimation"][
                "source_video_metadata_key"
            ] = f"video_{camera_name}"

        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
        assert len(pe.pose_estimations) == len(camera_names)

        assert set(nwbfile.devices.keys()) == set(camera_names)

        camera_pose_estimations_by_device = {pe_.device.name: pe_ for pe_ in pe.pose_estimations.values()}
        for camera_name in camera_names[:-1]:
            assert camera_pose_estimations_by_device[camera_name].source_video is source_videos[camera_name]

        assert camera_pose_estimations_by_device[camera_names[-1]].source_video is None

    def test_metadata_devices_type_creates_calibrated_camera(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        camera_names = ["Camera1", "Camera2"]
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0, camera_names=camera_names)

        nwbfile = mock_NWBFile()

        rng = np.random.default_rng(0)
        calibration = dict(
            intrinsic_matrix=rng.standard_normal((3, 3)),
            rotation_matrix=rng.standard_normal((3, 3)),
            translation_vector=rng.standard_normal(3),
            distortion_coefficients=rng.standard_normal(5),
        )

        # Supplying calibration by editing metadata["Devices"] before the write: mark the entry with
        # type="CalibratedCamera" and add the calibration fields alongside it.
        metadata = interface.get_metadata()
        metadata["Devices"]["Camera1"].update(type="CalibratedCamera", **calibration)
        # Camera2 intentionally left as a generic entry -- should get a plain Device.

        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        camera1 = nwbfile.devices["Camera1"]
        camera2 = nwbfile.devices["Camera2"]

        assert isinstance(camera1, CalibratedCamera)
        assert_array_equal(camera1.intrinsic_matrix, calibration["intrinsic_matrix"])
        assert_array_equal(camera1.rotation_matrix, calibration["rotation_matrix"])
        assert_array_equal(camera1.translation_vector, calibration["translation_vector"])
        assert_array_equal(camera1.distortion_coefficients, calibration["distortion_coefficients"])

        assert not isinstance(camera2, CalibratedCamera)
        assert type(camera2).__name__ == "Device"

    def test_add_to_nwbfile_writes_selected_animal(self, multi_animal_dannce_mat_file):
        file_path, n_samples, _, n_landmarks, pred, p_max = multi_animal_dannce_mat_file
        interface = DANNCEInterface(
            file_paths=file_path,
            animal_index=1,
            sampling_rate=30.0,
            subject_name="rat2",
        )

        nwbfile = NWBFile(
            session_description="test",
            identifier="test_dannce_multi_animal",
            session_start_time=datetime.now().astimezone(),
        )
        interface.add_to_nwbfile(nwbfile=nwbfile)

        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCERat2"]
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
            file_paths=file_path,
            animal_index=0,
            sampling_rate=30.0,
            subject_name="rat1",
        )
        interface_animal1 = DANNCEInterface(
            file_paths=file_path,
            animal_index=1,
            sampling_rate=30.0,
            subject_name="rat2",
        )

        interface_animal0.add_to_nwbfile(nwbfile=nwbfile)
        interface_animal1.add_to_nwbfile(nwbfile=nwbfile)

        # Only one shared camera device should have been created.
        assert list(nwbfile.devices.keys()) == ["Camera1"]

        behavior = nwbfile.processing["behavior"]
        pe_animal0 = behavior.data_interfaces["PoseEstimationDANNCERat1"]
        pe_animal1 = behavior.data_interfaces["PoseEstimationDANNCERat2"]

        camera0 = next(iter(pe_animal0.pose_estimations.values())).device
        camera1 = next(iter(pe_animal1.pose_estimations.values())).device
        assert camera0 is camera1
        assert camera0 is nwbfile.devices["Camera1"]

    def test_source_software_relabeled_via_metadata_override(self, dannce_mat_file):
        """DANNCEInterface defaults source_software to "DANNCE"; for sDANNCE-produced data,
        relabel via the standard metadata-merge mechanism rather than a dedicated subclass."""
        file_path = dannce_mat_file[0]
        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        metadata = interface.get_metadata()
        container = metadata["Pose"]["MultiCameraPoseEstimations"]["dannce"]
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

        interface = DANNCEInterface(file_paths=file_path, sampling_rate=30.0)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, stub_test=True)

        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
        for series in pe.pose_estimation_series.values():
            assert series.data.shape[0] == 100
            assert series.confidence.shape[0] == 100

        # Internal arrays must remain untouched.
        assert interface._pred.shape[0] == n_samples
        assert interface._p_max.shape[0] == n_samples


class TestDANNCEInterfaceWarningLocation:
    """Warnings point at the caller's line, past pydantic's ``validate_call`` wrapper."""

    def test_no_sampling_rate_warning_points_at_caller(self, classic_dannce_mat_file):
        with pytest.warns(_NoTimingInformationWarning) as records:
            DANNCEInterface(file_paths=classic_dannce_mat_file[0])
        assert records[0].filename == __file__

    def test_cameras_disagree_warning_points_at_caller(self, tmp_path, classic_dannce_mat_file):
        file_path, sample_ids = classic_dannce_mat_file
        frames = np.arange(len(sample_ids))
        sync_path = tmp_path / "label3d_dannce.mat"
        savemat(
            str(sync_path),
            dict(
                camnames=np.array(["Camera1", "Camera2"], dtype=object).reshape(1, -1),
                sync=_write_sync_entry_cells(["Camera1", "Camera2"], sample_ids, [frames, frames + 1]),
            ),
        )

        with pytest.warns(UserWarning, match="maps some sampleIDs to different frames") as records:
            DANNCEInterface(
                file_paths=file_path, sampling_rate=100.0, sync_path=sync_path, camera_names=["Camera1", "Camera2"]
            )
        assert all(record.filename == __file__ for record in records)
