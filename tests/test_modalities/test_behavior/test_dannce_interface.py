from datetime import datetime

import numpy as np
import pytest
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO, NWBFile
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

        # Check series metadata has mm units
        series = container["PoseEstimationSeries"]
        assert len(series) == n_landmarks
        for landmark_meta in series.values():
            assert landmark_meta["unit"] == "mm"

    def test_metadata_custom_key(self, dannce_mat_file):
        file_path, _, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(
            file_path=file_path, sampling_rate=30.0, pose_estimation_metadata_key="CustomDANNCE"
        )
        metadata = interface.get_metadata()

        assert "CustomDANNCE" in metadata["PoseEstimation"]["PoseEstimationContainers"]


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
        assert len(pe.pose_estimation_series) == n_landmarks
        assert pe.source_software == "DANNCE"

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
            assert series.unit == "mm"

    def test_add_to_nwbfile_with_custom_timestamps(self, dannce_mat_file, tmp_path):
        file_path, n_samples, _, _, _ = dannce_mat_file
        interface = DANNCEInterface(file_path=file_path)

        custom_timestamps = np.linspace(0.0, 10.0, n_samples)
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
