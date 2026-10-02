from datetime import datetime, timezone

import numpy as np
import pytest
from scipy.io import savemat

from neuroconv.converters import DANNCEConverter

from ._dannce_helpers import write_label3d_file

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

    with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file, quoting=csv.QUOTE_ALL)
        writer.writerow(["cameraMake", camera_make])
        writer.writerow(["cameraModel", camera_model])
        writer.writerow(["cameraSerialNo", serial_number])
        writer.writerow(["frameRate", frame_rate])


@pytest.fixture
def dannce_converter_dir(tmp_path):
    """Build a synthetic DANNCE + campy-style videos folder: one prediction .mat file, a Label3D-style sync
    file, and two camera subdirectories (Camera1, Camera2), each with one video and a matching frametimes.npy.

    The sampleIDs are classic-DANNCE-style labels (1, 11, 21, ...) that the sync table maps to frames
    0, 1, 2, ..., so reading a sampleID as a frame index gives wrong times."""
    n_samples = 20
    n_landmarks = 3
    camera_names = ["Camera1", "Camera2"]

    rng = np.random.default_rng(0)
    pred = rng.standard_normal((n_samples, 3, n_landmarks))
    p_max = rng.random((n_samples, n_landmarks))
    sample_ids = 1 + 10 * np.arange(n_samples, dtype="float64")
    file_path = tmp_path / "save_data_AVG.mat"
    savemat(str(file_path), dict(pred=pred, p_max=p_max, sampleID=sample_ids.reshape(1, -1)))
    sync_path = tmp_path / "label3d_dannce.mat"
    write_label3d_file(
        sync_path,
        camera_names=camera_names,
        sample_ids=sample_ids,
        frames_per_camera=[np.arange(n_samples)] * len(camera_names),
    )

    videos_folder_path = tmp_path / "videos"
    for camera_name in camera_names:
        camera_dir = videos_folder_path / camera_name
        camera_dir.mkdir(parents=True)
        _write_video(camera_dir / "0.avi", n_frames=n_samples)
        _write_frametimes(camera_dir / "frametimes.npy", n_frames=n_samples)

    return dict(
        file_path=file_path,
        sync_path=sync_path,
        videos_folder_path=videos_folder_path,
        camera_names=camera_names,
        n_samples=n_samples,
    )


@pytest.fixture
def dannce_converter_dir_multi_segment_no_frametimes(tmp_path):
    """Build a synthetic DANNCE videos folder with two cameras, each split across two video
    segments, and no 'frametimes.npy' at all -- mirrors a classic (non-campy) DANNCE rig whose
    videos happen to be chunked (e.g. 'dannce/chunked_videos' in the real DANNCE dataset)."""
    n_frames_per_segment = 5
    n_landmarks = 3
    camera_names = ["Camera1", "Camera2"]

    rng = np.random.default_rng(0)
    n_samples = n_frames_per_segment * 2
    pred = rng.standard_normal((n_samples, 3, n_landmarks))
    p_max = rng.random((n_samples, n_landmarks))
    sample_id = np.arange(n_samples, dtype="float64").reshape(1, -1)
    file_path = tmp_path / "save_data_AVG.mat"
    savemat(str(file_path), dict(pred=pred, p_max=p_max, sampleID=sample_id))

    videos_folder_path = tmp_path / "videos"
    for camera_name in camera_names:
        camera_dir = videos_folder_path / camera_name
        camera_dir.mkdir(parents=True)
        _write_video(camera_dir / "0.avi", n_frames=n_frames_per_segment)
        _write_video(camera_dir / f"{n_frames_per_segment}.avi", n_frames=n_frames_per_segment)

    return dict(
        file_path=file_path,
        videos_folder_path=videos_folder_path,
        camera_names=camera_names,
        n_frames_per_segment=n_frames_per_segment,
    )


class TestDANNCEConverterDiscovery:
    def test_camera_names_and_timestamps(self, dannce_converter_dir):
        converter = DANNCEConverter(
            file_paths=dannce_converter_dir["file_path"],
            videos_folder_path=dannce_converter_dir["videos_folder_path"],
            sync_path=dannce_converter_dir["sync_path"],
        )
        assert converter._camera_names == dannce_converter_dir["camera_names"]

        expected_timestamps = np.arange(dannce_converter_dir["n_samples"]) / 40.0
        np.testing.assert_allclose(
            converter._dannce_interface.alignment[converter._dannce_interface.metadata_key].get_times(),
            expected_timestamps,
        )
        for camera_name in dannce_converter_dir["camera_names"]:
            video_interface = converter._video_interfaces[camera_name]
            np.testing.assert_allclose(
                video_interface.alignment[video_interface.alignment.keys()[0]].get_times(), expected_timestamps
            )

    def test_numeric_camera_ordering(self, tmp_path, dannce_converter_dir):
        # Camera10 should sort after Camera2 (numeric order), not before it (lexicographic order).
        videos_folder_path = dannce_converter_dir["videos_folder_path"]
        (videos_folder_path / "Camera2").rename(videos_folder_path / "Camera10")

        converter = DANNCEConverter(
            file_paths=dannce_converter_dir["file_path"],
            videos_folder_path=videos_folder_path,
        )
        assert converter._camera_names == ["Camera1", "Camera10"]

    def test_missing_frametimes_falls_back_to_video_default_timestamps(self, dannce_converter_dir):
        """'frametimes.npy' is optional per camera -- not every DANNCE rig records with campy/pCamPI.
        A camera missing one should not raise: it should simply keep ExternalVideoInterface's own
        default timestamps (derived directly from the video file), independent of the sibling
        camera that does have a real 'frametimes.npy'."""
        camera1_frametimes = dannce_converter_dir["videos_folder_path"] / "Camera1" / "frametimes.npy"
        camera1_frametimes.unlink()

        converter = DANNCEConverter(
            file_paths=dannce_converter_dir["file_path"],
            videos_folder_path=dannce_converter_dir["videos_folder_path"],
            sync_path=dannce_converter_dir["sync_path"],
            sampling_rate=40.0,
        )

        # Camera1 has no frametimes.npy, so it falls back to ExternalVideoInterface's own
        # video-derived timestamps -- close to, but not necessarily bit-identical to, frame_index/fps.
        camera1_interface = converter._video_interfaces["Camera1"]
        expected_timestamps = np.arange(dannce_converter_dir["n_samples"]) / 40.0
        np.testing.assert_allclose(
            camera1_interface.alignment[camera1_interface.alignment.keys()[0]].get_times(),
            expected_timestamps,
            atol=0.05,
        )

        # Camera2 still has its own real frametimes.npy, unaffected by Camera1 missing one.
        camera2_interface = converter._video_interfaces["Camera2"]
        np.testing.assert_allclose(
            camera2_interface.alignment[camera2_interface.alignment.keys()[0]].get_times(), expected_timestamps
        )

    def test_primary_camera_missing_frametimes_uses_sampling_rate_for_pose(self, dannce_converter_dir):
        """When the first camera has no 'frametimes.npy', the DANNCE pose estimation's timestamps
        should come from 'sampling_rate' (forwarded to DANNCEInterface) instead."""
        camera1_frametimes = dannce_converter_dir["videos_folder_path"] / "Camera1" / "frametimes.npy"
        camera1_frametimes.unlink()

        converter = DANNCEConverter(
            file_paths=dannce_converter_dir["file_path"],
            videos_folder_path=dannce_converter_dir["videos_folder_path"],
            sync_path=dannce_converter_dir["sync_path"],
            sampling_rate=25.0,
        )

        expected_timestamps = np.arange(dannce_converter_dir["n_samples"]) / 25.0
        np.testing.assert_allclose(
            converter._dannce_interface.alignment[converter._dannce_interface.metadata_key].get_times(),
            expected_timestamps,
        )

    def test_primary_camera_missing_frametimes_and_no_sampling_rate_raises_on_write(self, dannce_converter_dir):
        """Without 'frametimes.npy' for the first camera and no 'sampling_rate' fallback, building the
        converter still succeeds (mirrors the bare DANNCEInterface), but asking for the DANNCE pose
        estimation's timestamps raises DANNCEInterface's own pre-existing, clear error."""
        camera1_frametimes = dannce_converter_dir["videos_folder_path"] / "Camera1" / "frametimes.npy"
        camera1_frametimes.unlink()

        converter = DANNCEConverter(
            file_paths=dannce_converter_dir["file_path"],
            videos_folder_path=dannce_converter_dir["videos_folder_path"],
            sync_path=dannce_converter_dir["sync_path"],
        )

        with pytest.raises(ValueError, match="No timing information is available"):
            converter._dannce_interface.alignment[converter._dannce_interface.metadata_key].get_times()

    def test_multi_segment_no_frametimes_placed_one_after_another(
        self, dannce_converter_dir_multi_segment_no_frametimes
    ):
        """A camera split across several video files with no 'frametimes.npy' has its files placed one after
        another from their headers (40 fps here), so no 'sampling_rate' is needed for the videos."""
        fixture = dannce_converter_dir_multi_segment_no_frametimes
        converter = DANNCEConverter(
            file_paths=fixture["file_path"],
            videos_folder_path=fixture["videos_folder_path"],
            sampling_rate=10.0,  # for the pose only
        )

        n_per_segment = fixture["n_frames_per_segment"]
        expected_first_segment = np.arange(n_per_segment) / 40.0
        expected_second_segment = np.arange(n_per_segment, 2 * n_per_segment) / 40.0

        for camera_name in fixture["camera_names"]:
            video_interface = converter._video_interfaces[camera_name]
            first_segment_key, second_segment_key = video_interface.alignment.keys()
            np.testing.assert_allclose(video_interface.alignment[first_segment_key].get_times(), expected_first_segment)
            np.testing.assert_allclose(
                video_interface.alignment[second_segment_key].get_times(), expected_second_segment
            )
            # Only the starts were stored, so the video is still written as a starting time and a rate.
            assert video_interface._get_compact_timing() == pytest.approx((0.0, 40.0))

    def test_no_camera_subdirectories_raises(self, tmp_path, dannce_converter_dir):
        empty_videos_folder = tmp_path / "empty_videos"
        empty_videos_folder.mkdir()

        with pytest.raises(FileNotFoundError, match="No camera subdirectories found"):
            DANNCEConverter(
                file_paths=dannce_converter_dir["file_path"],
                videos_folder_path=empty_videos_folder,
            )

    def test_video_frame_count_frametimes_mismatch_raises(self, dannce_converter_dir):
        # Camera2's video has fewer frames than its own frametimes file claims.
        camera2_dir = dannce_converter_dir["videos_folder_path"] / "Camera2"
        _write_video(camera2_dir / "0.avi", n_frames=dannce_converter_dir["n_samples"] - 5)

        with pytest.raises(ValueError, match="video frames"):
            DANNCEConverter(
                file_paths=dannce_converter_dir["file_path"],
                videos_folder_path=dannce_converter_dir["videos_folder_path"],
                sync_path=dannce_converter_dir["sync_path"],
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
            file_paths=dannce_converter_dir_with_camera_metadata["file_path"],
            videos_folder_path=dannce_converter_dir_with_camera_metadata["videos_folder_path"],
            sync_path=dannce_converter_dir_with_camera_metadata["sync_path"],
        )
        metadata = converter.get_metadata()

        assert len(metadata["DeviceModels"]) == 1
        ((device_model_metadata_key, device_model_metadata),) = metadata["DeviceModels"].items()
        assert device_model_metadata["name"] == "a2A1920-160ucBAS"
        assert device_model_metadata["manufacturer"] == "basler"  # as campy writes it

        for camera_name, serial_number in dannce_converter_dir_with_camera_metadata["serial_numbers"].items():
            device_metadata = metadata["Devices"][camera_name]
            assert device_metadata["serial_number"] == serial_number
            assert device_metadata["device_model_metadata_key"] == device_model_metadata_key

            video_description = metadata["Behavior"]["ExternalVideos"][f"video_{camera_name}"]["description"]
            assert "40 fps" in video_description

    def test_no_metadata_csv_omits_capture_metadata(self, dannce_converter_dir):
        # dannce_converter_dir (without the _with_camera_metadata fixture) has no metadata.csv files.
        converter = DANNCEConverter(
            file_paths=dannce_converter_dir["file_path"],
            videos_folder_path=dannce_converter_dir["videos_folder_path"],
            sync_path=dannce_converter_dir["sync_path"],
        )
        metadata = converter.get_metadata()

        assert "DeviceModels" not in metadata or len(metadata["DeviceModels"]) == 0
        for camera_name in dannce_converter_dir["camera_names"]:
            device_metadata = metadata["Devices"][camera_name]
            assert "serial_number" not in device_metadata
            assert "device_model_metadata_key" not in device_metadata

            # Nothing recorded, nothing added: the video keeps the description its own interface gives it.
            video_interface = converter._video_interfaces[camera_name]
            own_metadata = video_interface.get_metadata()["Behavior"]["ExternalVideos"][video_interface.metadata_key]
            video_entry = metadata["Behavior"]["ExternalVideos"][video_interface.metadata_key]
            assert video_entry["description"] == own_metadata["description"]

    def test_run_conversion_roundtrip(self, tmp_path, dannce_converter_dir_with_camera_metadata):
        converter = DANNCEConverter(
            file_paths=dannce_converter_dir_with_camera_metadata["file_path"],
            videos_folder_path=dannce_converter_dir_with_camera_metadata["videos_folder_path"],
            sync_path=dannce_converter_dir_with_camera_metadata["sync_path"],
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
            assert device_model.manufacturer == "basler"  # as campy writes it

            for camera_name, serial_number in dannce_converter_dir_with_camera_metadata["serial_numbers"].items():
                camera = nwbfile.devices[camera_name]
                assert camera.serial_number == serial_number
                assert camera.model is device_model

                video = nwbfile.acquisition[f"Video{camera_name}"]
                assert "40 fps" in video.description


class TestDANNCEConverterConversion:
    def test_run_conversion(self, tmp_path, dannce_converter_dir):
        converter = DANNCEConverter(
            file_paths=dannce_converter_dir["file_path"],
            videos_folder_path=dannce_converter_dir["videos_folder_path"],
            sync_path=dannce_converter_dir["sync_path"],
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


class TestDANNCEConverterSync:
    """The pose times go sampleID -> sync table -> video frame -> frametimes, and never guess the frame."""

    def test_sync_from_calibration_path(self, tmp_path, dannce_converter_dir):
        """A Label3D '.mat' passed only as calibration_path also supplies the sync table."""
        camera_names = dannce_converter_dir["camera_names"]
        n_samples = dannce_converter_dir["n_samples"]
        label3d_path = tmp_path / "session_Label3D_dannce.mat"
        write_label3d_file(
            label3d_path,
            camera_names=camera_names,
            sample_ids=1 + 10 * np.arange(n_samples),
            frames_per_camera=[np.arange(n_samples)] * len(camera_names),
            with_calibration=True,
        )

        converter = DANNCEConverter(
            file_paths=dannce_converter_dir["file_path"],
            videos_folder_path=dannce_converter_dir["videos_folder_path"],
            calibration_path=label3d_path,
        )

        dannce_interface = converter._dannce_interface
        np.testing.assert_array_equal(dannce_interface.video_frame_indices, np.arange(n_samples))
        np.testing.assert_allclose(
            dannce_interface.alignment[dannce_interface.metadata_key].get_times(), np.arange(n_samples) / 40.0
        )
        assert converter.get_metadata()["Devices"]["Camera1"]["type"] == "CalibratedCamera"

    def test_frametimes_without_sync_are_not_used_for_pose(self, dannce_converter_dir):
        with pytest.warns(UserWarning, match="no sync table to map"):
            converter = DANNCEConverter(
                file_paths=dannce_converter_dir["file_path"],
                videos_folder_path=dannce_converter_dir["videos_folder_path"],
                sampling_rate=40.0,
            )

        # Without sync the samples are taken as consecutive frames from the start.
        dannce_interface = converter._dannce_interface
        assert dannce_interface.video_frame_indices is None
        np.testing.assert_allclose(
            dannce_interface.alignment[dannce_interface.metadata_key].get_times(),
            np.arange(dannce_converter_dir["n_samples"]) / 40.0,
        )

    def test_frametimes_without_sync_or_sampling_rate_warns_and_raises_on_write(self, dannce_converter_dir):
        with pytest.warns(UserWarning) as records:
            converter = DANNCEConverter(
                file_paths=dannce_converter_dir["file_path"],
                videos_folder_path=dannce_converter_dir["videos_folder_path"],
            )
        messages = [str(record.message) for record in records]
        assert any("no sync table to map" in message for message in messages)
        assert any("No timing information is available for the DANNCE pose" in message for message in messages)
        # The interface's own construction-time warning is held back in favor of the converter's.
        assert not any("no 'sampling_rate' was given" in message for message in messages)

        dannce_interface = converter._dannce_interface
        with pytest.raises(ValueError, match="No timing information is available"):
            dannce_interface.alignment[dannce_interface.metadata_key].get_times()

    def test_no_timing_warning_when_frametimes_set_the_pose_times(self, dannce_converter_dir, recwarn):
        DANNCEConverter(
            file_paths=dannce_converter_dir["file_path"],
            videos_folder_path=dannce_converter_dir["videos_folder_path"],
            sync_path=dannce_converter_dir["sync_path"],
        )
        assert not [record for record in recwarn if "No timing information" in str(record.message)]

    def test_sync_frame_past_the_frametimes_raises(self, tmp_path, dannce_converter_dir):
        n_samples = dannce_converter_dir["n_samples"]
        sync_path = tmp_path / "too_far_dannce.mat"
        camera_names = dannce_converter_dir["camera_names"]
        write_label3d_file(
            sync_path,
            camera_names=camera_names,
            sample_ids=1 + 10 * np.arange(n_samples),
            frames_per_camera=[np.arange(n_samples) + 5] * len(camera_names),
        )

        with pytest.raises(ValueError, match="has frametimes for only"):
            DANNCEConverter(
                file_paths=dannce_converter_dir["file_path"],
                videos_folder_path=dannce_converter_dir["videos_folder_path"],
                sync_path=sync_path,
            )


class TestDANNCEConverterWarningLocation:
    """Warnings point at the caller's line, past pydantic's ``validate_call`` wrapper."""

    def test_warnings_point_at_caller(self, dannce_converter_dir):
        with pytest.warns(UserWarning) as records:
            DANNCEConverter(
                file_paths=dannce_converter_dir["file_path"],
                videos_folder_path=dannce_converter_dir["videos_folder_path"],
            )
        messages = {str(record.message)[:40]: record.filename for record in records}
        assert len(messages) == 2  # frametimes without sync, and no timing at all
        assert set(messages.values()) == {__file__}
