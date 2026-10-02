import csv
import re
import warnings
from copy import deepcopy
from pathlib import Path

import numpy as np
from pydantic import DirectoryPath, FilePath, validate_call
from pynwb import NWBFile

from .danncedatainterface import DANNCEInterface, _natural_sort_key, _NoTimingInformationWarning
from ..video.externalvideointerface import ExternalVideoInterface
from ..video.video_utils import VideoCaptureContext
from ....basedatainterface import BaseDataInterface
from ....utils import DeepDict, dict_deep_update

_VIDEO_SUFFIXES = (".mp4", ".avi", ".wmv", ".mov", ".flv", ".mkv")


class DANNCEConverter(BaseDataInterface):
    """
    Converter combining a :py:class:`~neuroconv.datainterfaces.DANNCEInterface` with one
    :py:class:`~neuroconv.datainterfaces.ExternalVideoInterface` per camera, discovered from a
    DANNCE/campy-style ``videos`` folder.

    DANNCE rigs typically record with `campy <https://github.com/ksseverson57/campy>`_ (or the
    compatible pCamPI), which writes one subdirectory per camera under a shared ``videos`` folder,
    each containing that camera's video file(s) and, per camera, an optional ``frametimes.npy`` file
    recording that camera's own per-frame acquisition times (not every DANNCE rig records with
    campy/pCamPI, so some or all cameras may lack one). This converter takes the path to that
    ``videos`` folder, discovers each camera's video(s) and any frametimes from it, and writes each
    camera's video timed by its frametimes, without the caller needing to enumerate cameras or
    timestamps by hand. A camera without frametimes is timed from its video headers, its files placed
    one after another when there are several (see
    :class:`~neuroconv.datainterfaces.ExternalVideoInterface`).

    The DANNCE pose estimation is timed by the first camera's frametimes, read at the video frame the
    sync table (``sync_path``) gives for each prediction's ``sampleID``. Without frametimes or without
    a sync table it uses ``sampling_rate`` instead (see :class:`~neuroconv.datainterfaces.DANNCEInterface`).

    The videos and the pose share one ``Device`` per camera, a ``CalibratedCamera`` when calibration is
    available, and each camera's per-camera ``PoseEstimation`` links its video as ``source_video``.
    Wiring this up by hand means pointing each video's ``device_metadata_key`` at the camera's
    ``Devices`` entry, setting ``source_video_metadata_key`` on each camera's entry in
    ``metadata["Pose"]["PoseEstimations"]``, and writing the videos before the pose; this converter
    does it internally.
    """

    display_name = "DANNCE with source videos"
    keywords = ("DANNCE", "sDANNCE", "social DANNCE", "3D pose estimation", "behavior", "pose estimation", "video")
    associated_suffixes = (".mat", ".mp4")
    info = (
        "Converter for DANNCE and social DANNCE (sDANNCE) 3D pose estimation output data, combined with each "
        "camera's source video."
    )

    @staticmethod
    def _discover_camera_directories(videos_folder_path: Path) -> dict[str, Path]:
        """Find one subdirectory per camera under ``videos_folder_path``.

        Subdirectories are sorted by name, numbers by value (``Camera2`` before ``Camera10``), ignoring case.
        The first one is the reference camera whose frametimes time the pose estimation.
        """
        subdirectories = [path for path in videos_folder_path.iterdir() if path.is_dir()]
        if not subdirectories:
            raise FileNotFoundError(
                f"No camera subdirectories found in '{videos_folder_path}'. Expected one subdirectory "
                "per camera (e.g. 'Camera1', 'Camera2', ...), each containing that camera's video "
                "file(s) and, optionally, a 'frametimes.npy' file."
            )

        subdirectories.sort(key=lambda directory: _natural_sort_key(directory.name))
        return {directory.name: directory for directory in subdirectories}

    @staticmethod
    def _discover_video_file_paths(camera_directory: Path) -> list[Path]:
        """Find a camera's video file(s) in its directory, in segment order: sorted by name, numbers by value
        (``0.mp4``, ``25.mp4``, ``100.mp4``)."""
        video_paths = [
            file_path for file_path in camera_directory.iterdir() if file_path.suffix.lower() in _VIDEO_SUFFIXES
        ]
        if not video_paths:
            raise FileNotFoundError(
                f"No video files found in '{camera_directory}' (expected one of {_VIDEO_SUFFIXES})."
            )

        video_paths.sort(key=lambda file_path: _natural_sort_key(file_path.stem))
        return video_paths

    @staticmethod
    def _load_frametimes(frametimes_file_path: Path) -> np.ndarray:
        """Load a campy/pCamPI-style ``frametimes.npy`` file (shape ``(2, n_frames)``; row 0 = 1-indexed
        frame number, row 1 = elapsed seconds) and return just the per-frame timestamps, in seconds,
        shape ``(n_frames,)``."""
        frametimes = np.load(str(frametimes_file_path))
        return np.asarray(frametimes[1], dtype="float64")

    @staticmethod
    def _load_camera_capture_metadata(metadata_csv_file_path: Path) -> dict[str, str]:
        """Parse a campy/pCamPI-style per-camera ``metadata.csv`` file into a dict.

        The file is a headerless two-column CSV (``"key","value"`` per row, e.g.
        ``"cameraModel","a2A1920-160ucBAS"``) recording the capture software's acquisition settings
        for that camera. All values come back as strings (the file has no type information).
        """
        with open(metadata_csv_file_path, newline="", encoding="utf-8") as csv_file:
            return {row[0]: row[1] for row in csv.reader(csv_file) if len(row) == 2}

    @staticmethod
    def _split_timestamps_by_segment(
        timestamps: np.ndarray, video_paths: list[Path], camera_name: str
    ) -> list[np.ndarray]:
        """Split a camera's full-session ``timestamps`` across its video segment(s) (``video_paths``, in
        order) by each segment's actual frame count, so each segment gets exactly the timestamps of the
        frames it contains. Raises if the segments' combined frame count does not match ``timestamps``."""
        segment_timestamps = []
        start = 0
        for video_path in video_paths:
            with VideoCaptureContext(file_path=str(video_path)) as video:
                n_frames = video.get_video_frame_count()
            stop = start + n_frames
            segment_timestamps.append(timestamps[start:stop])
            start = stop

        if start != timestamps.shape[0]:
            raise ValueError(
                f"Camera '{camera_name}' has {start} video frames across {len(video_paths)} file(s) "
                f"({[str(path) for path in video_paths]}), but its frametimes file records "
                f"{timestamps.shape[0]} frames. Verify that the video file(s) and frametimes file come "
                "from the same recording."
            )
        return segment_timestamps

    @staticmethod
    def _set_segment_times(video_interface: ExternalVideoInterface, segment_timestamps: list[np.ndarray]) -> None:
        """Give each of a camera's video files its own times, through that file's alignment key."""
        for segment_key, timestamps in zip(video_interface.alignment.keys(), segment_timestamps, strict=True):
            video_interface.alignment[segment_key].set_times(timestamps)

    @validate_call
    def __init__(
        self,
        file_paths: FilePath | list[FilePath],
        videos_folder_path: DirectoryPath,
        *,
        calibration_path: Path | None = None,
        sync_path: Path | None = None,
        landmark_names: list[str] | None = None,
        subject_name: str | None = None,
        metadata_key: str | None = None,
        animal_index: int | None = None,
        sampling_rate: float | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_paths : FilePath or list of FilePath
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`. Path to the DANNCE prediction
            .mat file (e.g., save_data_AVG.mat or save_data_MAX.mat), or a list of paths to
            concatenate into one continuous session (e.g. sDANNCE jobs split by batch).
        videos_folder_path : DirectoryPath
            Path to the DANNCE/campy ``videos`` folder, containing one subdirectory per camera (e.g.
            ``Camera1``, ``Camera2``, ...). Each camera subdirectory must contain that camera's video
            file(s) (in sorted, consecutive segment order, if split into multiple parts). Camera names
            are taken directly from the subdirectory names and used as ``DANNCEInterface``'s
            ``camera_names``, so they must match the naming used by ``calibration_path``, if provided
            (see :meth:`DANNCEInterface.get_camera_calibrations`).

            A camera subdirectory *may* also contain a campy/pCamPI-style ``frametimes.npy`` file
            (shape ``(2, n_video_frames)``; row 0 = 1-indexed frame number, row 1 = elapsed seconds
            since recording start) -- not every DANNCE rig records with campy/pCamPI, so this is
            optional per camera. When present, it is used to set the times of each of that camera's
            video files (via ``alignment[segment_key].set_times``); when absent, that video keeps
            ``ExternalVideoInterface``'s own default timestamps (derived directly from the video
            file). The first camera's frametimes, if present, also give the DANNCE pose estimation's
            times (via ``DANNCEInterface.alignment[metadata_key].set_times``): each prediction's
            ``sampleID`` is mapped to its video frame through the sync table (``sync_path``), and the
            frametimes are read at those frames. Without a sync table the frametimes are not used for
            the pose, since a ``sampleID`` is not itself a frame index; a warning says so, and
            ``sampling_rate`` (below) is used instead, if given.
        calibration_path : str or Path, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`. Only used to load per-camera
            calibrations (intrinsics/extrinsics), and the sync table when it is a Label3D ``.mat`` file
            and no ``sync_path`` is given; the set of cameras itself is always taken from
            ``videos_folder_path``.
        sync_path : str or Path, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        landmark_names : list of str, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        subject_name : str, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        metadata_key : str, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        animal_index : int, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        sampling_rate : float, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`. Forwarded to it directly, and used
            for the DANNCE pose estimation's timestamps only when the first camera's frametimes cannot be
            used. The videos are timed from their own headers, not from this rate: a camera without
            ``frametimes.npy`` that is split across several files has the files placed one after another.
        verbose : bool, default: False
            Controls verbosity of the conversion process.
        """
        self.verbose = verbose
        videos_folder_path = Path(videos_folder_path)

        camera_directories = self._discover_camera_directories(videos_folder_path)
        self._camera_names = list(camera_directories)

        camera_video_paths: dict[str, list[Path]] = {}
        camera_frametimes: dict[str, np.ndarray] = {}
        self._camera_capture_metadata: dict[str, dict[str, str]] = {}
        for camera_name, camera_directory in camera_directories.items():
            camera_video_paths[camera_name] = self._discover_video_file_paths(camera_directory)

            frametimes_file_path = camera_directory / "frametimes.npy"
            if frametimes_file_path.exists():
                camera_frametimes[camera_name] = self._load_frametimes(frametimes_file_path)

            # Optional: a campy/pCamPI-style 'metadata.csv' recording the capture software's
            # acquisition settings for this camera (model, serial number, nominal frame rate, ...).
            # Not all DANNCE rigs write this file, so its absence is not an error.
            metadata_csv_file_path = camera_directory / "metadata.csv"
            if metadata_csv_file_path.exists():
                self._camera_capture_metadata[camera_name] = self._load_camera_capture_metadata(metadata_csv_file_path)

        # The interface warns at construction when it has no times of its own, but here the frametimes
        # may still supply them, so that warning is held back and given below only if they do not.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=_NoTimingInformationWarning)
            self._dannce_interface = DANNCEInterface(
                file_paths=file_paths,
                sampling_rate=sampling_rate,
                landmark_names=landmark_names,
                subject_name=subject_name,
                metadata_key=metadata_key,
                camera_names=self._camera_names,
                calibration_path=calibration_path,
                sync_path=sync_path,
                animal_index=animal_index,
                verbose=verbose,
            )

        primary_camera_name = self._camera_names[0]
        self._set_pose_times(
            camera_name=primary_camera_name,
            frametimes=camera_frametimes.get(primary_camera_name),
            sampling_rate=sampling_rate,
        )

        self._video_interfaces: dict[str, ExternalVideoInterface] = {}
        for camera_name in self._camera_names:
            video_paths = camera_video_paths[camera_name]
            video_interface = ExternalVideoInterface(
                file_paths=[str(path) for path in video_paths],
                metadata_key=f"video_{camera_name}",
                video_name=f"Video{camera_name}",
                verbose=verbose,
            )
            self._set_video_times(
                video_interface=video_interface,
                video_paths=video_paths,
                camera_name=camera_name,
                frametimes=camera_frametimes.get(camera_name),
            )
            self._video_interfaces[camera_name] = video_interface

        self.data_interface_objects: dict[str, BaseDataInterface] = {
            "DANNCE": self._dannce_interface,
            **{f"Video{camera_name}": interface for camera_name, interface in self._video_interfaces.items()},
        }

    def _set_pose_times(self, *, camera_name: str, frametimes: np.ndarray | None, sampling_rate: float | None) -> None:
        """Time the pose estimation from the reference camera's frametimes, read at the frames the sync table
        gives for each prediction. Without frametimes or without a sync table the interface keeps its own
        times (``sampling_rate``), and a warning says when neither gives any."""
        video_frame_indices = self._dannce_interface.video_frame_indices
        if frametimes is not None and video_frame_indices is not None:
            if video_frame_indices.max() >= len(frametimes):
                raise ValueError(
                    f"The sync table maps some predictions to frame {video_frame_indices.max()}, but camera "
                    f"'{camera_name}' has frametimes for only {len(frametimes)} frames. Check that the sync table, "
                    "predictions and videos come from the same recording."
                )
            self._dannce_interface.alignment[self._dannce_interface.metadata_key].set_times(
                frametimes[video_frame_indices]
            )
            return

        if frametimes is not None:
            warnings.warn(
                f"Camera '{camera_name}' has a 'frametimes.npy', but there is no sync table to map the "
                "predictions' sampleIDs to its frames, so the frametimes are not used for the pose estimation. "
                "Pass 'sync_path' (a Label3D '*_dannce.mat' file or a 'sync/' folder) to use them.",
                UserWarning,
                stacklevel=5,  # _set_pose_times, __init__, two validate_call frames, caller
            )
        if sampling_rate is None:
            warnings.warn(
                "No timing information is available for the DANNCE pose estimation: no usable frametimes and "
                "no 'sampling_rate'. Pass 'sampling_rate', or call "
                "'converter.data_interface_objects[\"DANNCE\"].alignment[key].set_times(times)' before writing.",
                _NoTimingInformationWarning,
                stacklevel=5,  # _set_pose_times, __init__, two validate_call frames, caller
            )

    def _set_video_times(
        self,
        *,
        video_interface: ExternalVideoInterface,
        video_paths: list[Path],
        camera_name: str,
        frametimes: np.ndarray | None,
    ) -> None:
        """Time one camera's video files, each through its own alignment key, in the order of ``video_paths``.

        A camera with frametimes gets them, split across its files by frame count. A camera without them keeps
        ExternalVideoInterface's own default, each file spaced at its header frame rate. Those files do not
        say how they relate, so a camera split across several files has them placed one after another: the
        first at zero and each next one where the previous ends, by its header frame count and rate. Only
        their starts are stored, so the video is still written as a starting time and a rate.
        """
        if frametimes is not None:
            segment_timestamps = self._split_timestamps_by_segment(
                timestamps=frametimes, video_paths=video_paths, camera_name=camera_name
            )
            self._set_segment_times(video_interface=video_interface, segment_timestamps=segment_timestamps)
            return
        if len(video_paths) == 1:
            return

        frame_counts = video_interface.get_header_frame_counts()
        frame_rates = video_interface.get_header_frame_rates()
        starting_time = 0.0
        for segment_key, frame_count, frame_rate in zip(
            video_interface.alignment.keys(), frame_counts, frame_rates, strict=True
        ):
            video_interface.alignment[segment_key].move_start_to(starting_time)
            starting_time += frame_count / frame_rate

    def get_metadata(self) -> DeepDict:
        metadata = self._dannce_interface.get_metadata()

        # Each camera's per-camera PoseEstimation entry is found through the metadata itself: it is the child
        # of this interface's container whose device is that camera.
        container_metadata = metadata["Pose"]["MultiCameraPoseEstimations"][self._dannce_interface.metadata_key]
        camera_pose_estimation_metadata_keys = {
            metadata["Pose"]["PoseEstimations"][key]["device_metadata_key"]: key
            for key in container_metadata["pose_estimation_metadata_keys"]
        }

        for camera_name in self._camera_names:
            video_interface = self._video_interfaces[camera_name]
            video_metadata = video_interface.get_metadata()
            video_entry = video_metadata["Behavior"]["ExternalVideos"][video_interface.metadata_key]
            # Point the video at the same camera Device DANNCE registers (under `camera_name` in
            # `metadata["Devices"]`), dropping the device entry the video interface made for itself, so the two
            # interfaces share one Device (e.g. a calibrated one) instead of each creating their own. The video
            # is written first and creates it; DANNCE then finds it by name.
            video_metadata["Devices"].pop(video_entry["device_metadata_key"], None)

            video_entry["device_metadata_key"] = camera_name
            # Only what campy recorded goes into the description; without it the video keeps its own default.
            nominal_frame_rate = self._camera_capture_metadata.get(camera_name, {}).get("frameRate")
            if nominal_frame_rate:
                video_entry["description"] = f"Recorded at a nominal {nominal_frame_rate} fps."

            metadata = dict_deep_update(metadata, video_metadata)

            # Link this camera's per-camera PoseEstimation child to the video, by key.
            camera_pose_estimation_metadata_key = camera_pose_estimation_metadata_keys[camera_name]
            metadata["Pose"]["PoseEstimations"][camera_pose_estimation_metadata_key][
                "source_video_metadata_key"
            ] = video_interface.metadata_key

        # Enrich each camera's Device entry with capture-software metadata (from that camera's
        # 'metadata.csv', if present): serial number directly on the Device, and make/model via a
        # shared DeviceModel (reused across cameras of the same hardware model instead of duplicating
        # manufacturer/model text on every camera).
        for camera_name, capture_metadata in self._camera_capture_metadata.items():
            device_metadata = metadata["Devices"][camera_name]

            serial_number = capture_metadata.get("cameraSerialNo")
            if serial_number:
                device_metadata["serial_number"] = serial_number

            model_name = capture_metadata.get("cameraModel")
            manufacturer = capture_metadata.get("cameraMake")
            if model_name and manufacturer:
                # A snake_case registry key, like every other key; the name keeps the model as campy wrote it.
                device_model_metadata_key = f"camera_model_{re.sub(r'[^0-9a-zA-Z]+', '_', model_name).lower()}"
                metadata["DeviceModels"][device_model_metadata_key] = dict(name=model_name, manufacturer=manufacturer)
                device_metadata["device_model_metadata_key"] = device_model_metadata_key

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *,
        stub_test: bool = False,
        starting_frames: dict[str, list[int]] | None = None,
    ) -> None:
        """
        Add each camera's source video and the DANNCE pose estimation data to an NWB file, linking the two.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the data to.
        metadata : dict
            The full metadata, as returned by ``get_metadata()`` and edited by the caller. It is used as
            given, not merged over the defaults, and is copied so the caller's dict is left unchanged.
        stub_test : bool, default: False
            If True, write only the first 100 frames of the DANNCE pose estimation data for quick smoke testing.
            Video data is always written in full.
        starting_frames : dict of str to list of int, optional
            Per-camera list of start frames for videos written using external mode, keyed by camera name.
            When a camera is not listed, its start frames are computed from each of its files' frame count
            (see ``ExternalVideoInterface.add_to_nwbfile``).

        Notes
        -----
        Camera calibration is written by marking a camera's ``metadata["Devices"]`` entry with
        ``type="CalibratedCamera"`` plus its calibration fields; see ``DANNCEInterface.add_to_nwbfile``.
        Passing ``calibration_path`` at construction fills these in automatically; to override or
        supply them otherwise, edit ``metadata["Devices"]`` before calling this method.
        """
        metadata_copy = deepcopy(metadata)

        # Videos first: each one creates its camera's Device (a CalibratedCamera when that
        # metadata["Devices"] entry names the type), and the pose container links each video by
        # `source_video_metadata_key`, which needs the ImageSeries already in the file.
        for camera_name in self._camera_names:
            self._video_interfaces[camera_name].add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata_copy,
                starting_frames=(starting_frames or {}).get(camera_name),
            )

        self._dannce_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata_copy, stub_test=stub_test)
