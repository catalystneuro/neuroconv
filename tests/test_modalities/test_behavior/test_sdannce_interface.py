from datetime import datetime

import numpy as np
import pytest
from numpy.testing import assert_array_equal
from pynwb import NWBFile
from pynwb.testing.mock.file import mock_NWBFile
from scipy.io import savemat

from neuroconv.datainterfaces import DANNCEInterface, SDANNCEInterface


@pytest.fixture
def sdannce_mat_file(tmp_path):
    """Create a synthetic sDANNCE prediction .mat file (2 animals)."""
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
def single_animal_dannce_mat_file(tmp_path):
    """Create a synthetic single-animal DANNCE prediction .mat file (3D pred)."""
    n_samples = 30
    n_landmarks = 5
    rng = np.random.default_rng(8)
    pred = rng.standard_normal((n_samples, 3, n_landmarks))
    p_max = rng.random((n_samples, n_landmarks))
    sample_id = np.arange(n_samples, dtype="float64").reshape(1, -1)

    file_path = tmp_path / "save_data_AVG.mat"
    savemat(str(file_path), dict(pred=pred, p_max=p_max, sampleID=sample_id))
    return file_path


class TestSDANNCEInterfaceInit:
    def test_animal_index_0_slices_correctly(self, sdannce_mat_file):
        file_path, n_samples, _, n_landmarks, pred, p_max = sdannce_mat_file
        interface = SDANNCEInterface(file_path=file_path, animal_index=0, sampling_rate=30.0)

        assert interface._pred.shape == (n_samples, 3, n_landmarks)
        assert interface._p_max.shape == (n_samples, n_landmarks)
        assert_array_equal(interface._pred, pred[:, 0, :, :])
        assert_array_equal(interface._p_max, p_max[:, 0, :])

    def test_animal_index_1_slices_correctly(self, sdannce_mat_file):
        file_path, n_samples, _, n_landmarks, pred, p_max = sdannce_mat_file
        interface = SDANNCEInterface(file_path=file_path, animal_index=1, sampling_rate=30.0)

        assert interface._pred.shape == (n_samples, 3, n_landmarks)
        assert_array_equal(interface._pred, pred[:, 1, :, :])
        assert_array_equal(interface._p_max, p_max[:, 1, :])

    def test_out_of_range_animal_index_raises(self, sdannce_mat_file):
        file_path, _, n_animals, _, _, _ = sdannce_mat_file
        with pytest.raises(IndexError, match="out of range"):
            SDANNCEInterface(file_path=file_path, animal_index=n_animals, sampling_rate=30.0)

    def test_3d_pred_raises(self, single_animal_dannce_mat_file):
        with pytest.raises(ValueError, match="sDANNCE multi-animal output"):
            SDANNCEInterface(file_path=single_animal_dannce_mat_file, animal_index=0, sampling_rate=30.0)


class TestSDANNCEInterfaceMetadata:
    def test_source_software_is_sdannce(self, sdannce_mat_file):
        file_path = sdannce_mat_file[0]
        interface = SDANNCEInterface(file_path=file_path, animal_index=0, sampling_rate=30.0)
        metadata = interface.get_metadata()

        container = metadata["PoseEstimation"]["PoseEstimationContainers"]["PoseEstimationSDANNCE"]
        assert container["source_software"] == "sDANNCE"
        assert container["scorer"] == "sDANNCE"
        assert "sDANNCE" in container["description"]

    def test_default_metadata_key(self, sdannce_mat_file):
        file_path = sdannce_mat_file[0]
        interface = SDANNCEInterface(file_path=file_path, animal_index=0, sampling_rate=30.0)
        assert interface.pose_estimation_metadata_key == "PoseEstimationSDANNCE"

    def test_explicit_metadata_key_overrides_default(self, sdannce_mat_file):
        file_path = sdannce_mat_file[0]
        interface = SDANNCEInterface(
            file_path=file_path,
            animal_index=0,
            sampling_rate=30.0,
            subject_name="rat1",
            pose_estimation_metadata_key="CustomSDANNCEKey",
        )
        assert interface.pose_estimation_metadata_key == "CustomSDANNCEKey"

    def test_unit_is_millimeters(self, sdannce_mat_file):
        file_path = sdannce_mat_file[0]
        interface = SDANNCEInterface(file_path=file_path, animal_index=0, sampling_rate=30.0)
        metadata = interface.get_metadata()
        key = interface.pose_estimation_metadata_key
        series = metadata["PoseEstimation"]["PoseEstimationContainers"][key]["PoseEstimationSeries"]
        for landmark_meta in series.values():
            assert landmark_meta["unit"] == "millimeters"


class TestSDANNCEInterfaceConversion:
    def test_add_to_nwbfile_writes_selected_animal(self, sdannce_mat_file):
        file_path, n_samples, _, n_landmarks, pred, p_max = sdannce_mat_file
        interface = SDANNCEInterface(file_path=file_path, animal_index=1, sampling_rate=30.0, subject_name="rat2")

        nwbfile = NWBFile(
            session_description="test",
            identifier="test_sdannce",
            session_start_time=datetime.now().astimezone(),
        )
        interface.add_to_nwbfile(nwbfile=nwbfile)

        pe = nwbfile.processing["behavior"][interface.pose_estimation_metadata_key]
        assert pe.source_software == "sDANNCE"
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
            assert series.unit == "millimeters"

    def test_stub_test_limits_output_samples(self, tmp_path):
        n_samples = 400
        n_animals = 2
        n_landmarks = 4
        rng = np.random.default_rng(11)
        pred = rng.standard_normal((n_samples, n_animals, 3, n_landmarks))
        p_max = rng.random((n_samples, n_animals, n_landmarks))
        sample_id = np.arange(n_samples, dtype="float64").reshape(1, -1)
        file_path = tmp_path / "save_data_AVG0_big.mat"
        savemat(str(file_path), dict(pred=pred, p_max=p_max, sampleID=sample_id))

        interface = SDANNCEInterface(file_path=file_path, animal_index=0, sampling_rate=30.0)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, stub_test=True)

        pe = nwbfile.processing["behavior"][interface.pose_estimation_metadata_key]
        for series in pe.pose_estimation_series.values():
            assert series.data.shape[0] == 100
            assert series.confidence.shape[0] == 100
        assert interface._pred.shape[0] == n_samples

    def test_frametimes_file_path_indexed_by_sample_id(self, tmp_path, sdannce_mat_file):
        file_path, n_samples, _, _, _, _ = sdannce_mat_file
        seconds = np.linspace(0.0, 2.0, n_samples + 20, dtype="float64")
        frame_indices = np.arange(1, seconds.size + 1, dtype="float64")
        frametimes_path = tmp_path / "frametimes.npy"
        np.save(str(frametimes_path), np.stack([frame_indices, seconds], axis=0))

        interface = SDANNCEInterface(file_path=file_path, animal_index=0, frametimes_file_path=frametimes_path)
        timestamps = interface.get_timestamps()
        np.testing.assert_allclose(timestamps, seconds[:n_samples])


def test_dannce_and_sdannce_are_distinct_classes():
    assert SDANNCEInterface is not DANNCEInterface
    assert issubclass(SDANNCEInterface, DANNCEInterface)
