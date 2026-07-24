import re
from copy import deepcopy
from pathlib import Path

import numpy as np
from pydantic import DirectoryPath, FilePath, validate_call
from pynwb import NWBFile

from .danncedatainterface import DANNCEInterface
from ..video.externalvideointerface import ExternalVideoInterface
from ..video.video_utils import VideoCaptureContext
from ....basedatainterface import BaseDataInterface
from ....utils import DeepDict, dict_deep_update

_VIDEO_SUFFIXES = (".mp4", ".avi", ".wmv", ".mov", ".flv", ".mkv")
_CAMERA_DIRECTORY_PATTERN = re.compile(r"camera(\d+)$", re.IGNORECASE)


class DANNCEConverter(BaseDataInterface):
    """
    Converter combining a :py:class:`~neuroconv.datainterfaces.DANNCEInterface` with one
    :py:class:`~neuroconv.datainterfaces.ExternalVideoInterface` per camera, discovered from a
    DANNCE/campy-style ``videos`` folder.

    DANNCE rigs typically record with `campy <https://github.com/ksseverson57/campy>`_ (or the
    compatible pCamPI), which writes one subdirectory per camera under a shared ``videos`` folder,
    each containing that camera's video file(s) and a ``frametimes.npy`` file recording that
    camera's own per-frame acquisition times. This converter takes the path to that ``videos``
    folder, discovers each camera's video(s) and frametimes from it, and uses them to both write
    each camera's video and temporally align it -- and the DANNCE pose estimation itself -- without
    the caller needing to enumerate cameras or timestamps by hand.

    ``DANNCEInterface`` on its own can link each camera's source video via the ``source_videos``
    argument of its ``add_to_nwbfile``, but doing so safely requires the video ``ImageSeries`` to
    already be written to the ``NWBFile`` first, and then looked up by name to pass the live
    objects through -- easy to get wrong (write order, name matching) when wiring up interfaces
    by hand in an ``NWBConverter``. This converter does that wiring internally, so a user combining
    DANNCE with source videos does not need to reimplement it.
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

        Subdirectories named after the DANNCE/campy convention (``Camera1``, ``Camera2``, ...) are
        sorted numerically; any others are sorted alphabetically and placed after the numbered ones.
        """
        subdirectories = [path for path in videos_folder_path.iterdir() if path.is_dir()]
        if not subdirectories:
            raise FileNotFoundError(
                f"No camera subdirectories found in '{videos_folder_path}'. Expected one subdirectory "
                "per camera (e.g. 'Camera1', 'Camera2', ...), each containing that camera's video "
                "file(s) and a 'frametimes.npy' file."
            )

        numbered = []
        unnumbered = []
        for directory in subdirectories:
            match = _CAMERA_DIRECTORY_PATTERN.match(directory.name)
            if match:
                numbered.append((int(match.group(1)), directory))
            else:
                unnumbered.append(directory)
        numbered.sort(key=lambda pair: pair[0])
        ordered_directories = [directory for _, directory in numbered] + sorted(
            unnumbered, key=lambda directory: directory.name
        )

        return {directory.name: directory for directory in ordered_directories}

    @staticmethod
    def _discover_video_file_paths(camera_directory: Path) -> list[Path]:
        """Find a camera's video file(s) in its directory, in sorted (consecutive segment) order."""
        video_paths = [
            file_path for file_path in camera_directory.iterdir() if file_path.suffix.lower() in _VIDEO_SUFFIXES
        ]
        if not video_paths:
            raise FileNotFoundError(
                f"No video files found in '{camera_directory}' (expected one of {_VIDEO_SUFFIXES})."
            )

        def sort_key(file_path: Path):
            return (0, int(file_path.stem)) if file_path.stem.isdigit() else (1, file_path.stem)

        video_paths.sort(key=sort_key)
        return video_paths

    @staticmethod
    def _load_frametimes(frametimes_file_path: Path) -> np.ndarray:
        """Load a campy/pCamPI-style ``frametimes.npy`` file (shape ``(2, n_frames)``; row 0 = 1-indexed
        frame number, row 1 = elapsed seconds) and return just the per-frame timestamps, in seconds,
        shape ``(n_frames,)``."""
        frametimes = np.load(str(frametimes_file_path))
        return np.asarray(frametimes[1], dtype="float64")

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

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        videos_folder_path: DirectoryPath,
        *,
        calibration_path: Path | None = None,
        landmark_names: list[str] | None = None,
        subject_name: str = "ind1",
        metadata_key: str | None = None,
        animal_index: int | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the DANNCE prediction .mat file (e.g., save_data_AVG.mat or save_data_MAX.mat).
        videos_folder_path : DirectoryPath
            Path to the DANNCE/campy ``videos`` folder, containing one subdirectory per camera (e.g.
            ``Camera1``, ``Camera2``, ...). Each camera subdirectory must contain that camera's video
            file(s) (in sorted, consecutive segment order, if split into multiple parts) and a
            ``frametimes.npy`` file (shape ``(2, n_video_frames)``; row 0 = 1-indexed frame number, row
            1 = elapsed seconds since recording start) -- the campy/pCamPI capture standard used by
            DANNCE rigs. Camera names are taken directly from the subdirectory names and used as
            ``DANNCEInterface``'s ``camera_names``, so they must match the naming used by
            ``calibration_path``, if provided (see :meth:`DANNCEInterface.get_camera_calibrations`).

            Each camera's own frametimes are used to set that camera's video's timestamps (via
            ``ExternalVideoInterface.set_aligned_timestamps``). The first camera's frametimes, indexed
            by the DANNCE prediction file's ``sampleID`` field, are used to set the DANNCE pose
            estimation's timestamps (via ``DANNCEInterface.set_aligned_timestamps``); the first camera
            is used because DANNCE/sDANNCE triangulates from all cameras but stores only one shared
            ``sampleID`` per predicted sample, referencing frame indices in a single reference camera's
            timeline (by campy/pCamPI convention, cameras are frame-synchronized, so any one camera's
            frametimes would work equally well as that reference).
        calibration_path : str or Path, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`. Only used to load per-camera
            calibrations (intrinsics/extrinsics); the set of cameras itself is always taken from
            ``videos_folder_path``.
        landmark_names : list of str, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        subject_name : str, default: "ind1"
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        metadata_key : str, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        animal_index : int, optional
            See :class:`~neuroconv.datainterfaces.DANNCEInterface`.
        verbose : bool, default: False
            Controls verbosity of the conversion process.
        """
        self.verbose = verbose
        videos_folder_path = Path(videos_folder_path)

        camera_directories = self._discover_camera_directories(videos_folder_path)
        self._camera_names = list(camera_directories)

        camera_video_paths: dict[str, list[Path]] = {}
        camera_frametimes: dict[str, np.ndarray] = {}
        for camera_name, camera_directory in camera_directories.items():
            camera_video_paths[camera_name] = self._discover_video_file_paths(camera_directory)

            frametimes_file_path = camera_directory / "frametimes.npy"
            if not frametimes_file_path.exists():
                raise FileNotFoundError(
                    f"No 'frametimes.npy' file found for camera '{camera_name}' at "
                    f"'{frametimes_file_path}'. Each camera subdirectory of 'videos_folder_path' must "
                    "contain a frametimes file, used to synchronize its video and the DANNCE pose "
                    "estimation."
                )
            camera_frametimes[camera_name] = self._load_frametimes(frametimes_file_path)

        self._dannce_interface = DANNCEInterface(
            file_path=file_path,
            landmark_names=landmark_names,
            subject_name=subject_name,
            metadata_key=metadata_key,
            camera_names=self._camera_names,
            calibration_path=calibration_path,
            animal_index=animal_index,
            verbose=verbose,
        )

        primary_camera_name = self._camera_names[0]
        primary_camera_frametimes = camera_frametimes[primary_camera_name]
        video_frame_indices = self._dannce_interface.video_frame_indices
        self._dannce_interface.set_aligned_timestamps(primary_camera_frametimes[video_frame_indices.astype(int)])

        self._video_interfaces: dict[str, ExternalVideoInterface] = {}
        for camera_name in self._camera_names:
            video_paths = camera_video_paths[camera_name]
            video_interface = ExternalVideoInterface(
                file_paths=[str(path) for path in video_paths],
                metadata_key=f"video_{camera_name}",
                video_name=f"Video{camera_name}",
                verbose=verbose,
            )
            segment_timestamps = self._split_timestamps_by_segment(
                timestamps=camera_frametimes[camera_name], video_paths=video_paths, camera_name=camera_name
            )
            video_interface.set_aligned_timestamps(segment_timestamps)
            self._video_interfaces[camera_name] = video_interface

        self.data_interface_objects: dict[str, BaseDataInterface] = {
            "DANNCE": self._dannce_interface,
            **{f"Video{camera_name}": interface for camera_name, interface in self._video_interfaces.items()},
        }

    def get_metadata(self) -> DeepDict:
        metadata = self._dannce_interface.get_metadata()
        for camera_name in self._camera_names:
            video_interface = self._video_interfaces[camera_name]
            video_metadata = video_interface.get_metadata()
            # Point the video at the same camera Device DANNCE already registered (under `camera_name`
            # in `metadata["Devices"]`), dropping the video interface's own default device entry (see
            # ExternalVideoInterface.__init__: `f"{metadata_key}_camera"`), so the two interfaces share
            # one Device (e.g. a calibrated one) instead of each creating their own -- see the matching
            # `create_camera_devices` call in `add_to_nwbfile`.
            video_metadata["Devices"].pop(f"{video_interface.metadata_key}_camera", None)
            video_metadata["Behavior"]["ExternalVideos"][video_interface.metadata_key].update(
                description=f"Source video recorded by camera '{camera_name}'.",
                device_metadata_key=camera_name,
            )
            metadata = dict_deep_update(metadata, video_metadata)
        return metadata

    def get_conversion_options_schema(self) -> dict:
        # `camera_calibrations` carries live `numpy.ndarray` values, not JSON-serializable values, so it
        # cannot be represented in a JSON schema and must be excluded (unlike `nwbfile`/`metadata`, which
        # the base implementation already excludes).
        from ....utils import get_json_schema_from_method_signature

        return get_json_schema_from_method_signature(
            self.add_to_nwbfile, exclude=["nwbfile", "metadata", "camera_calibrations"]
        )

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *,
        stub_test: bool = False,
        camera_calibrations: dict[str, dict] | None = None,
        starting_frames: dict[str, list[int]] | None = None,
    ) -> None:
        """
        Add each camera's source video and the DANNCE pose estimation data to an NWB file, linking the two.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the data to.
        metadata : dict
            Metadata dictionary. If provided, overrides default metadata from ``get_metadata()``.
        stub_test : bool, default: False
            If True, write only the first 100 frames of the DANNCE pose estimation data for quick smoke testing.
            Video data is always written in full.
        camera_calibrations : dict of str to dict, optional
            Per-camera calibration overrides; see ``DANNCEInterface.add_to_nwbfile``. Merged on top of any
            calibrations already loaded from ``calibration_path`` at construction.
        starting_frames : dict of str to list of int, optional
            Per-camera list of start frames for videos written using external mode, keyed by camera name.
            Required for a given camera only if more than one video path was given for it.
        """
        metadata_copy = deepcopy(metadata)

        # Pre-create each camera's Device (calibrated, if calibration data is available) before
        # writing the videos, so that when each ExternalVideoInterface resolves its device_metadata_key
        # (pointed at the same camera_name entry by get_metadata, above), it reuses this Device instead
        # of creating its own -- Device creation is idempotent on name.
        self._dannce_interface.create_camera_devices(
            nwbfile=nwbfile, metadata=metadata_copy, camera_calibrations=camera_calibrations
        )

        source_videos = {}
        for camera_name in self._camera_names:
            video_interface = self._video_interfaces[camera_name]
            video_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata_copy,
                starting_frames=(starting_frames or {}).get(camera_name),
            )
            image_series_name = metadata_copy["Behavior"]["ExternalVideos"][video_interface.metadata_key]["name"]
            source_videos[camera_name] = nwbfile.acquisition[image_series_name]

        self._dannce_interface.add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata_copy,
            stub_test=stub_test,
            source_videos=source_videos,
            camera_calibrations=camera_calibrations,
        )
