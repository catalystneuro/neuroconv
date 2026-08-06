from datetime import datetime, timezone

import numpy as np
import pytest
from scipy.io import savemat

from neuroconv.converters import DANNCEConverter

try:
    from importlib.metadata import version as importlib_version

    from packaging import version

    ndx_pose_version = version.parse(importlib_version("ndx-pose"))
    NDX_POSE_TOO_OLD = ndx_pose_version < version.parse("0.3.0")
except Exception:
    NDX_POSE_TOO_OLD = True

pytestmark = pytest.mark.skipif(NDX_POSE_TOO_OLD, reason="DANNCEInterface requires ndx-pose version >= 0.3.0")


def _write_video(file_path, n_frames: int, fps: float = 40.0):
    cv2 = pytest.importorskip("cv2")
    fourcc = cv2.VideoWriter_fourcc(*("M", "J", "P", "G"))
    writer = cv2.VideoWriter(filename=str(file_path), fourcc=fourcc, fps=fps, frameSize=(32, 24))
    for _ in range(n_frames):
        writer.write(np.random.randint(0, 255, (24, 32, 3)).astype("uint8"))
    writer.release()


def _write_frametimes(file_path, n_frames: int, fps: float = 40.0):
    frame_numbers = np.arange(1, n_frames + 1, dtype="float64")
    seconds = np.arange(n_frames, dtype="float64") / fps
    np.save(str(file_path), np.stack([frame_numbers, seconds], axis=0))


def _write_metadata_csv(file_path, *, camera_make: str, camera_model: str, serial_number: str, frame_rate: str):
    """Write a campy-style headerless two-column 'metadata.csv' (a small subset of the real fields)."""
    import csv

    with open(file_path, "w", newline="") as csv_file:
        writer = csv.writer(csv_file, quoting=csv.QUOTE_ALL)
        writer.writerow(["cameraMake", camera_make])
        writer.writerow(["cameraModel", camera_model])
        writer.writerow(["cameraSerialNo", serial_number])
        writer.writerow(["frameRate", frame_rate])


@pytest.fixture
def dannce_converter_dir(tmp_path):
    """Build a synthetic DANNCE + campy-style videos folder: one prediction .mat file and two
    camera subdirectories (Camera1, Camera2), each with one video and a matching frametimes.npy."""
    n_samples = 20
    n_landmarks = 3
    camera_names = ["Camera1", "Camera2"]

    rng = np.random.default_rng(0)
    pred = rng.standard_normal((n_samples, 3, n_landmarks))
    p_max = rng.random((n_samples, n_landmarks))
    sample_id = np.arange(n_samples, dtype="float64").reshape(1, -1)
    file_path = tmp_path / "save_data_AVG.mat"
    savemat(str(file_path), dict(pred=pred, p_max=p_max, sampleID=sample_id))

    videos_folder_path = tmp_path / "videos"
    for camera_name in camera_names:
        camera_dir = videos_folder_path / camera_name
        camera_dir.mkdir(parents=True)
        _write_video(camera_dir / "0.avi", n_frames=n_samples)
        _write_frametimes(camera_dir / "frametimes.npy", n_frames=n_samples)

    return dict(
        file_path=file_path,
        videos_folder_path=videos_folder_path,
        camera_names=camera_names,
        n_samples=n_samples,
    )


class TestDANNCEConverterDiscovery:
    def test_camera_names_and_timestamps(self, dannce_converter_dir):
        converter = DANNCEConverter(
            file_path=dannce_converter_dir["file_path"],
            videos_folder_path=dannce_converter_dir["videos_folder_path"],
        )
        assert converter._camera_names == dannce_converter_dir["camera_names"]

        expected_timestamps = np.arange(dannce_converter_dir["n_samples"]) / 40.0
        np.testing.assert_allclose(converter._dannce_interface.get_timestamps(), expected_timestamps)
        for camera_name in dannce_converter_dir["camera_names"]:
            video_interface = converter._video_interfaces[camera_name]
            np.testing.assert_allclose(video_interface.get_timestamps()[0], expected_timestamps)

    def test_numeric_camera_ordering(self, tmp_path, dannce_converter_dir):
        # Camera10 should sort after Camera2 (numeric order), not before it (lexicographic order).
        videos_folder_path = dannce_converter_dir["videos_folder_path"]
        (videos_folder_path / "Camera2").rename(videos_folder_path / "Camera10")

        converter = DANNCEConverter(
            file_path=dannce_converter_dir["file_path"],
            videos_folder_path=videos_folder_path,
        )
        assert converter._camera_names == ["Camera1", "Camera10"]

    def test_missing_frametimes_raises(self, dannce_converter_dir):
        camera1_frametimes = dannce_converter_dir["videos_folder_path"] / "Camera1" / "frametimes.npy"
        camera1_frametimes.unlink()

        with pytest.raises(FileNotFoundError, match="No 'frametimes.npy' file found"):
            DANNCEConverter(
                file_path=dannce_converter_dir["file_path"],
                videos_folder_path=dannce_converter_dir["videos_folder_path"],
            )

    def test_no_camera_subdirectories_raises(self, tmp_path, dannce_converter_dir):
        empty_videos_folder = tmp_path / "empty_videos"
        empty_videos_folder.mkdir()

        with pytest.raises(FileNotFoundError, match="No camera subdirectories found"):
            DANNCEConverter(
                file_path=dannce_converter_dir["file_path"],
                videos_folder_path=empty_videos_folder,
            )

    def test_video_frame_count_frametimes_mismatch_raises(self, dannce_converter_dir):
        # Camera2's video has fewer frames than its own frametimes file claims.
        camera2_dir = dannce_converter_dir["videos_folder_path"] / "Camera2"
        _write_video(camera2_dir / "0.avi", n_frames=dannce_converter_dir["n_samples"] - 5)

        with pytest.raises(ValueError, match="video frames"):
            DANNCEConverter(
                file_path=dannce_converter_dir["file_path"],
                videos_folder_path=dannce_converter_dir["videos_folder_path"],
            )


@pytest.fixture
def dannce_converter_dir_with_camera_metadata(dannce_converter_dir):
    """Same as ``dannce_converter_dir``, plus a campy-style 'metadata.csv' per camera. Both cameras
    share the same make/model (the common case for a multi-camera rig) but have distinct serial
    numbers, so a shared DeviceModel can be verified alongside per-camera serial numbers."""
    serial_numbers = {"Camera1": "40054255", "Camera2": "40068500"}
    for camera_name in dannce_converter_dir["camera_names"]:
        camera_dir = dannce_converter_dir["videos_folder_path"] / camera_name
        _write_metadata_csv(
            camera_dir / "metadata.csv",
            camera_make="basler",
            camera_model="a2A1920-160ucBAS",
            serial_number=serial_numbers[camera_name],
            frame_rate="40",
        )
    dannce_converter_dir["serial_numbers"] = serial_numbers
    return dannce_converter_dir


class TestDANNCEConverterCameraCaptureMetadata:
    def test_get_metadata(self, dannce_converter_dir_with_camera_metadata):
        converter = DANNCEConverter(
            file_path=dannce_converter_dir_with_camera_metadata["file_path"],
            videos_folder_path=dannce_converter_dir_with_camera_metadata["videos_folder_path"],
        )
        metadata = converter.get_metadata()

        assert len(metadata["DeviceModels"]) == 1
        (device_model_metadata_key, device_model_metadata), = metadata["DeviceModels"].items()
        assert device_model_metadata["name"] == "a2A1920-160ucBAS"
        assert device_model_metadata["manufacturer"] == "Basler"

        for camera_name, serial_number in dannce_converter_dir_with_camera_metadata["serial_numbers"].items():
            device_metadata = metadata["Devices"][camera_name]
            assert device_metadata["serial_number"] == serial_number
            assert device_metadata["device_model_metadata_key"] == device_model_metadata_key

            video_description = metadata["Behavior"]["ExternalVideos"][f"video_{camera_name}"]["description"]
            assert "40 fps" in video_description

    def test_no_metadata_csv_omits_capture_metadata(self, dannce_converter_dir):
        # dannce_converter_dir (without the _with_camera_metadata fixture) has no metadata.csv files.
        converter = DANNCEConverter(
            file_path=dannce_converter_dir["file_path"],
            videos_folder_path=dannce_converter_dir["videos_folder_path"],
        )
        metadata = converter.get_metadata()

        assert "DeviceModels" not in metadata or len(metadata["DeviceModels"]) == 0
        for camera_name in dannce_converter_dir["camera_names"]:
            device_metadata = metadata["Devices"][camera_name]
            assert "serial_number" not in device_metadata
            assert "device_model_metadata_key" not in device_metadata

    def test_run_conversion_roundtrip(self, tmp_path, dannce_converter_dir_with_camera_metadata):
        converter = DANNCEConverter(
            file_path=dannce_converter_dir_with_camera_metadata["file_path"],
            videos_folder_path=dannce_converter_dir_with_camera_metadata["videos_folder_path"],
            metadata_key="PoseEstimationDANNCE",
        )
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now(timezone.utc)
        metadata["Subject"] = dict(subject_id="mouse1", species="Mus musculus", sex="U")

        nwbfile_path = tmp_path / "test_dannce_converter_camera_metadata.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata)

        from pynwb import NWBHDF5IO

        with NWBHDF5IO(path=str(nwbfile_path), mode="r", load_namespaces=True) as io:
            nwbfile = io.read()

            assert len(nwbfile.device_models) == 1
            (device_model,) = nwbfile.device_models.values()
            assert device_model.name == "a2A1920-160ucBAS"
            assert device_model.manufacturer == "Basler"

            for camera_name, serial_number in dannce_converter_dir_with_camera_metadata["serial_numbers"].items():
                camera = nwbfile.devices[camera_name]
                assert camera.serial_number == serial_number
                assert camera.model is device_model

                video = nwbfile.acquisition[f"Video{camera_name}"]
                assert "40 fps" in video.description


class TestDANNCEConverterConversion:
    def test_run_conversion(self, tmp_path, dannce_converter_dir):
        converter = DANNCEConverter(
            file_path=dannce_converter_dir["file_path"],
            videos_folder_path=dannce_converter_dir["videos_folder_path"],
            metadata_key="PoseEstimationDANNCE",
        )
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now(timezone.utc)
        metadata["Subject"] = dict(subject_id="mouse1", species="Mus musculus", sex="U")

        nwbfile_path = tmp_path / "test_dannce_converter.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata)

        from ndx_pose import MultiCameraPoseEstimation
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(path=str(nwbfile_path), mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            for camera_name in dannce_converter_dir["camera_names"]:
                assert f"Video{camera_name}" in nwbfile.acquisition

            pe = nwbfile.processing["behavior"].data_interfaces["PoseEstimationDANNCE"]
            assert isinstance(pe, MultiCameraPoseEstimation)
            for series in pe.pose_estimation_series.values():
                # The synthetic frametimes are exactly regular, so they are stored as rate/starting_time
                # rather than an explicit timestamps array (see calculate_regular_series_rate).
                assert series.rate == pytest.approx(40.0)
                assert series.starting_time == pytest.approx(0.0)
