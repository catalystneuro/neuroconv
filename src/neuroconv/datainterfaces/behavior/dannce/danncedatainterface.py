import re
from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.image import ImageSeries

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module
from ....utils import DeepDict, calculate_regular_series_rate, get_base_schema


class DANNCEInterface(BaseTemporalAlignmentInterface):
    """Data interface for DANNCE 3D pose estimation datasets."""

    display_name = "DANNCE"
    keywords = ("DANNCE", "sDANNCE", "social DANNCE", "3D pose estimation", "behavior", "pose estimation")
    associated_suffixes = (".mat",)
    info = "Interface for DANNCE and social DANNCE (sDANNCE) 3D pose estimation output data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"][
            "description"
        ] = "Path to the DANNCE prediction .mat file (e.g., save_data_AVG.mat)."
        if "frametimes_file_path" in source_schema["properties"]:
            source_schema["properties"]["frametimes_file_path"][
                "description"
            ] = "Optional path to a frametimes.npy file (shape (2, n_frames); row 1 = seconds) for per-frame timestamps."
        return source_schema

    @staticmethod
    def get_camera_calibrations(calibration_path: str | Path) -> tuple[list[str], dict[str, dict]]:
        """
        Load per-camera intrinsic/extrinsic calibration parameters, auto-detecting the file format.

        Three DANNCE/sDANNCE calibration layouts are supported:

        - A directory of per-camera ``hires_camN_params.mat`` files (keys ``K``, ``r``, ``t``,
          ``RDistort``, ``TDistort``); camera names are derived from the filenames (``Camera1``, ...).
        - A single ``calibration.json`` file with top-level ``camera_names`` and ``camera_params``
          (keys ``camera_matrix``, ``rotation_matrix``, ``translation_vector``, ``r_distort``,
          ``t_distort``), index-aligned.
        - A single Label3D-style ``*_dannce.mat`` file with top-level ``camnames`` and ``params``
          (same keys as the per-camera ``.mat`` format), index-aligned.

        Parameters
        ----------
        calibration_path : str or Path
            Path to a calibration directory or file in one of the formats described above.

        Returns
        -------
        camera_names : list of str
            Camera names, in the order given by the calibration source.
        camera_calibrations : dict of str to dict
            Per-camera calibration kwargs (``intrinsic_matrix``, ``rotation_matrix``,
            ``translation_vector``, ``distortion_coefficients``), keyed by camera name -- ready to pass
            as the ``camera_calibrations`` argument of :meth:`add_to_nwbfile` or the ``calibration_path``
            argument of ``__init__``.
        """
        calibration_path = Path(calibration_path)
        if not calibration_path.exists():
            raise FileNotFoundError(f"Calibration path '{calibration_path}' does not exist.")

        if calibration_path.is_dir():
            return DANNCEInterface._load_calibrations_from_hires_params_directory(calibration_path)
        elif calibration_path.suffix == ".json":
            return DANNCEInterface._load_calibrations_from_json(calibration_path)
        elif calibration_path.suffix == ".mat":
            return DANNCEInterface._load_calibrations_from_label3d_mat(calibration_path)
        else:
            raise ValueError(
                f"Unrecognized calibration format for '{calibration_path}'. Expected a directory of "
                "'hires_camN_params.mat' files, a '.json' file, or a Label3D-style '.mat' file."
            )

    @staticmethod
    def _load_calibrations_from_hires_params_directory(directory: Path) -> tuple[list[str], dict[str, dict]]:
        """Parse a directory of 'hires_camN_params.mat' files, one per camera."""
        from scipy.io import loadmat

        pattern = re.compile(r"hires_cam(\d+)_params\.mat$")
        matches = []
        for file_path in directory.iterdir():
            match = pattern.match(file_path.name)
            if match:
                matches.append((int(match.group(1)), file_path))
        if not matches:
            raise ValueError(f"No 'hires_camN_params.mat' files found in '{directory}'.")
        matches.sort(key=lambda pair: pair[0])

        camera_names = [f"Camera{camera_number}" for camera_number, _ in matches]
        camera_calibrations = {}
        for camera_name, (_, file_path) in zip(camera_names, matches):
            calibration = loadmat(str(file_path))
            camera_calibrations[camera_name] = dict(
                intrinsic_matrix=np.asarray(calibration["K"]),
                rotation_matrix=np.asarray(calibration["r"]),
                translation_vector=np.asarray(calibration["t"]).squeeze(),
                distortion_coefficients=np.concatenate(
                    [np.asarray(calibration["RDistort"]).squeeze(), np.asarray(calibration["TDistort"]).squeeze()]
                ),
            )
        return camera_names, camera_calibrations

    @staticmethod
    def _load_calibrations_from_json(file_path: Path) -> tuple[list[str], dict[str, dict]]:
        """Parse a single 'calibration.json' file with 'camera_names' and 'camera_params'."""
        import json

        with open(file_path) as f:
            data = json.load(f)

        camera_names = list(data["camera_names"])
        camera_calibrations = {}
        for camera_name, params in zip(camera_names, data["camera_params"]):
            camera_calibrations[camera_name] = dict(
                intrinsic_matrix=np.asarray(params["camera_matrix"]),
                rotation_matrix=np.asarray(params["rotation_matrix"]),
                translation_vector=np.asarray(params["translation_vector"]).squeeze(),
                distortion_coefficients=np.concatenate(
                    [np.asarray(params["r_distort"]).squeeze(), np.asarray(params["t_distort"]).squeeze()]
                ),
            )
        return camera_names, camera_calibrations

    @staticmethod
    def _load_calibrations_from_label3d_mat(file_path: Path) -> tuple[list[str], dict[str, dict]]:
        """Parse a single Label3D-style '*_dannce.mat' file with 'camnames' and 'params'."""
        from scipy.io import loadmat

        data = loadmat(str(file_path), simplify_cells=True)
        camera_names = list(np.atleast_1d(data["camnames"]))
        params_list = data["params"]
        if isinstance(params_list, dict):
            params_list = [params_list]

        camera_calibrations = {}
        for camera_name, params in zip(camera_names, params_list):
            camera_calibrations[camera_name] = dict(
                intrinsic_matrix=np.asarray(params["K"]),
                rotation_matrix=np.asarray(params["r"]),
                translation_vector=np.asarray(params["t"]).squeeze(),
                distortion_coefficients=np.concatenate(
                    [np.asarray(params["RDistort"]).squeeze(), np.asarray(params["TDistort"]).squeeze()]
                ),
            )
        return camera_names, camera_calibrations

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        frametimes_file_path: FilePath | None = None,
        video_file_path: FilePath | None = None,
        sampling_rate: float | None = None,
        landmark_names: list[str] | None = None,
        subject_name: str = "ind1",
        pose_estimation_metadata_key: str = "PoseEstimationDANNCE",
        camera_names: list[str] | None = None,
        calibration_path: Path | None = None,
        animal_index: int | None = None,
        verbose: bool = False,
    ):
        """
        Interface for writing DANNCE and social DANNCE (sDANNCE) 3D pose estimation output files to NWB.

        DANNCE (3-Dimensional Aligned Neural Network for Computational Ethology) is a
        multi-camera 3D pose estimation system that tracks anatomical landmarks on animals.
        This interface reads DANNCE prediction .mat files and converts them to NWB format
        using the ndx-pose extension. It transparently supports both single-animal DANNCE output
        (``pred`` shaped ``(n_frames, 3, n_landmarks)``) and multi-animal sDANNCE output (``pred``
        shaped ``(n_frames, n_animals, 3, n_landmarks)``, selected via ``animal_index``).

        Parameters
        ----------
        file_path : FilePath
            Path to the DANNCE prediction .mat file (e.g., save_data_AVG.mat or save_data_MAX.mat).
        frametimes_file_path : FilePath, optional
            Path to a ``frametimes.npy`` file (the campy / pCampi standard used by DANNCE rigs)
            with shape ``(2, n_video_frames)`` where row 1 holds per-frame timestamps in seconds
            from session start. Timestamps are indexed by the sampleID field to obtain the
            timestamp for each prediction. Takes precedence over ``video_file_path`` and
            ``sampling_rate``.
        video_file_path : FilePath, optional
            Path to one of the source video files used for DANNCE prediction. Used to extract
            per-frame timestamps, which are then indexed by the sampleID field to obtain the
            timestamps for each prediction. Takes precedence over ``sampling_rate``.
        sampling_rate : float, optional
            The sampling rate in Hz of the pose estimation data. Used to compute timestamps from
            the sampleID field. Ignored if ``frametimes_file_path`` or ``video_file_path`` is
            provided. If none are provided, timestamps must be set externally via
            ``set_aligned_timestamps()`` before conversion.
        landmark_names : list of str, optional
            Names for each tracked landmark/body part. Must match the number of landmarks in the
            data. If not provided, defaults to ``["landmark_0", "landmark_1", ...]``.
        subject_name : str, default: "ind1"
            The subject name used for linking the skeleton to the NWB subject.
        pose_estimation_metadata_key : str, default: "PoseEstimationDANNCE"
            Controls where in the metadata the pose estimation data is stored and the name of the
            MultiCameraPoseEstimation container in the NWB file.
        camera_names : list of str, optional
            Names of the cameras in the multi-camera rig used to produce the 3D predictions (e.g.,
            ``["Camera1", "Camera2", ..., "Camera6"]``). One camera Device and one empty per-camera
            ``PoseEstimation`` child of the ``MultiCameraPoseEstimation`` container is created per
            name; pass the corresponding videos as ``source_videos`` to ``add_to_nwbfile`` to link
            each camera's source video. If not provided, defaults to a single camera, ``["Camera1"]``,
            unless ``calibration_path`` is given, in which case it defaults to the camera names
            detected there.
        calibration_path : str or Path, optional
            Path to a camera calibration directory or file; see :meth:`get_camera_calibrations` for the
            supported formats. When provided, the detected camera names and calibrations are used
            automatically -- both to populate ``camera_names`` (unless explicitly overridden above) and
            to create ``ndx_pose.CalibratedCamera`` devices in :meth:`add_to_nwbfile` without needing to
            pass ``camera_calibrations`` there. An explicit ``camera_calibrations`` argument to
            ``add_to_nwbfile`` still overrides individual cameras loaded from here.
        animal_index : int, optional
            Index of the animal to write, selecting along the animal axis of a 4D ``pred`` array
            (shape ``(n_frames, n_animals, 3, n_landmarks)``), as produced by multi-animal sDANNCE
            output. Required when ``pred`` is 4D; construct one interface instance per animal, using
            a distinct ``pose_estimation_metadata_key`` per instance, to write each animal to the
            same NWBFile. Must be omitted (left as ``None``) when ``pred`` is already 3D
            (single-animal DANNCE output) -- passing it in that case raises an error.
        verbose : bool, default: False
            Controls verbosity of the conversion process.
        """
        from importlib.metadata import version

        import ndx_pose  # noqa: F401
        from packaging import version as version_parse

        ndx_pose_version = version("ndx-pose")
        if version_parse.parse(ndx_pose_version) < version_parse.parse("0.3.0"):
            raise ImportError(
                "DANNCE interface requires ndx-pose version 0.3.0 or later. "
                f"Found version {ndx_pose_version}. Please upgrade: "
                "pip install 'ndx-pose>=0.3.0'"
            )

        file_path = Path(file_path)
        if ".mat" not in file_path.suffixes:
            raise IOError(f"The file '{file_path}' is not a valid DANNCE output file. Only .mat files are supported.")

        self.subject_name = subject_name
        self.verbose = verbose
        self.pose_estimation_metadata_key = pose_estimation_metadata_key

        detected_camera_names = None
        self._camera_calibrations = None
        if calibration_path is not None:
            detected_camera_names, self._camera_calibrations = self.get_camera_calibrations(calibration_path)

        if camera_names:
            self._camera_names = list(camera_names)
        elif detected_camera_names:
            self._camera_names = detected_camera_names
        else:
            self._camera_names = ["Camera1"]

        self._animal_index = animal_index
        self._sampling_rate = sampling_rate
        self._video_file_path = Path(video_file_path) if video_file_path is not None else None
        self._frametimes_file_path = Path(frametimes_file_path) if frametimes_file_path is not None else None
        self._timestamps = None

        # Load data from .mat file
        self._load_dannce_data(file_path)

        # Validate and set landmark names
        n_landmarks = self._pred.shape[2]
        if landmark_names is not None:
            if len(landmark_names) != n_landmarks:
                raise ValueError(
                    f"Length of landmark_names ({len(landmark_names)}) does not match "
                    f"the number of landmarks in the data ({n_landmarks})."
                )
            self._landmark_names = list(landmark_names)
        else:
            self._landmark_names = [f"landmark_{i}" for i in range(n_landmarks)]

        # Compute timestamps:
        # frametimes_file_path > video_file_path > sampling_rate
        if frametimes_file_path is not None:
            self._timestamps = self._get_timestamps_from_frametimes()
        elif video_file_path is not None:
            self._timestamps = self._get_timestamps_from_video()
        elif sampling_rate is not None:
            self._timestamps = self._sample_id / sampling_rate

        super().__init__(file_path=file_path, video_file_path=video_file_path, verbose=verbose)

    def _load_dannce_data(self, file_path: Path) -> None:
        """Load and parse the DANNCE/sDANNCE .mat prediction file.

        Handles both single-animal DANNCE output (``pred`` shape ``(n_samples, 3, n_landmarks)``)
        and multi-animal sDANNCE output (``pred`` shape ``(n_samples, n_animals, 3, n_landmarks)``,
        sliced down to one animal via ``self._animal_index``).
        """
        from scipy.io import loadmat

        mat_data = loadmat(str(file_path))

        pred = mat_data["pred"]
        p_max = mat_data["p_max"]
        sample_id = mat_data["sampleID"]  # shape: (1, n_samples) or (n_samples,)
        self._sample_id = np.squeeze(sample_id).astype("float64")

        if pred.ndim == 4:
            if p_max.ndim != 3:
                raise ValueError(
                    f"Expected 3D 'p_max' to pair with 4D 'pred' (multi-animal sDANNCE output), "
                    f"but 'p_max' has shape {p_max.shape}."
                )
            if self._animal_index is None:
                raise ValueError(
                    f"The prediction file has an explicit animal axis (pred shape {pred.shape}). "
                    "Pass 'animal_index' to select which animal to write."
                )
            n_animals = pred.shape[1]
            if not 0 <= self._animal_index < n_animals:
                raise IndexError(
                    f"animal_index {self._animal_index} is out of range for a file with {n_animals} animals."
                )
            pred = pred[:, self._animal_index, :, :]
            p_max = p_max[:, self._animal_index, :]
        elif pred.ndim == 3:
            if self._animal_index is not None:
                raise ValueError(
                    f"'animal_index' was provided ({self._animal_index}) but the prediction data is "
                    f"already single-animal (pred shape {pred.shape}). Omit 'animal_index' for this file."
                )
        else:
            raise ValueError(
                f"Expected 'pred' to be 3D (single-animal DANNCE output) or 4D (multi-animal sDANNCE "
                f"output), but got shape {pred.shape}."
            )

        self._pred = pred  # shape: (n_samples, 3, n_landmarks)
        self._p_max = p_max  # shape: (n_samples, n_landmarks)

    def _get_timestamps_from_video(self, stub_test: bool = False) -> np.ndarray:
        """Extract timestamps from the video file, indexed by sampleID."""
        from ...video.video_utils import VideoCaptureContext

        sample_id = self._sample_id[:100] if stub_test else self._sample_id
        max_frames = int(sample_id.max()) + 1 if stub_test and sample_id.size > 0 else None
        with VideoCaptureContext(file_path=str(self._video_file_path)) as video:
            all_timestamps = video.get_video_timestamps(max_frames=max_frames)

        frame_indices = sample_id.astype(int)
        return np.asarray(all_timestamps[frame_indices], dtype="float64")

    def _get_timestamps_from_frametimes(self, stub_test: bool = False) -> np.ndarray:
        """Extract timestamps from a frametimes.npy file, indexed by sampleID."""
        frametimes = np.load(str(self._frametimes_file_path))  # shape (2, n_video_frames)
        all_timestamps = frametimes[1]  # row 1 = elapsed seconds
        sample_id = self._sample_id[:100] if stub_test else self._sample_id
        frame_indices = sample_id.astype(int)
        return np.asarray(all_timestamps[frame_indices], dtype="float64")

    def get_original_timestamps(self, stub_test: bool = False) -> np.ndarray:
        if self._frametimes_file_path is not None:
            return self._get_timestamps_from_frametimes(stub_test=stub_test)
        if self._video_file_path is not None:
            return self._get_timestamps_from_video(stub_test=stub_test)
        if self._sampling_rate is not None:
            sample_id = self._sample_id[:100] if stub_test else self._sample_id
            return sample_id / self._sampling_rate
        raise ValueError(
            "Cannot compute original timestamps without a frametimes file, video file, or sampling rate. "
            "Provide 'frametimes_file_path', 'video_file_path', or 'sampling_rate' when initializing the "
            "interface, or use 'set_aligned_timestamps()' to set timestamps directly."
        )

    def get_timestamps(self, stub_test: bool = False) -> np.ndarray:
        if self._timestamps is not None:
            return self._timestamps[:100] if stub_test else self._timestamps
        return self.get_original_timestamps(stub_test=stub_test)

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = np.asarray(aligned_timestamps, dtype="float64")

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()

        metadata_schema["properties"]["PoseEstimation"] = get_base_schema(tag="PoseEstimation")

        skeleton_schema = get_base_schema(tag="Skeletons")
        skeleton_schema["additionalProperties"] = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the skeleton"},
                "nodes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of node names (landmarks)",
                },
                "edges": {
                    "type": ["array", "null"],
                    "items": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "description": "List of edges connecting nodes, each edge is a pair of node indices",
                },
                "subject": {
                    "type": ["string", "null"],
                    "description": "Subject ID associated with this skeleton",
                },
            },
            "required": ["name", "nodes"],
        }

        devices_schema = get_base_schema(tag="Devices")
        devices_schema["additionalProperties"] = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the device"},
                "description": {"type": "string", "description": "Description of the device"},
                "camera_name": {
                    "type": "string",
                    "description": (
                        "Name of the camera this device represents, matching a key of the "
                        "'source_videos' dict passed to add_to_nwbfile."
                    ),
                },
            },
            "required": ["name"],
        }

        containers_schema = get_base_schema(tag="PoseEstimationContainers")
        containers_schema["additionalProperties"] = {
            "type": "object",
            "description": "Metadata for a MultiCameraPoseEstimation group",
            "properties": {
                "name": {"type": "string", "description": "Name of the MultiCameraPoseEstimation group"},
                "description": {"type": ["string", "null"], "description": "Description of the pose estimation"},
                "source_software": {"type": ["string", "null"], "description": "Name of the software tool used"},
                "source_software_version": {"type": ["string", "null"], "description": "Version of the software"},
                "scorer": {"type": ["string", "null"], "description": "Name of the scorer or algorithm"},
                "skeleton": {"type": ["string", "null"], "description": "Reference to a Skeleton"},
                "devices": {
                    "type": ["array", "null"],
                    "description": (
                        "References to Device objects, one per camera. Each device becomes the camera "
                        "link of its own empty per-camera PoseEstimation child of the "
                        "MultiCameraPoseEstimation container."
                    ),
                    "items": {"type": "string"},
                },
                "PoseEstimationSeries": {
                    "type": ["object", "null"],
                    "description": "Dictionary of PoseEstimationSeries, one per landmark",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "name": {"type": ["string", "null"], "description": "Name for this series"},
                            "description": {"type": ["string", "null"], "description": "Description for this series"},
                            "unit": {
                                "type": ["string", "null"],
                                "description": "Unit of measurement",
                                "default": "millimeters",
                            },
                            "reference_frame": {
                                "type": ["string", "null"],
                                "description": "Description of the reference frame",
                            },
                            "confidence_definition": {
                                "type": ["string", "null"],
                                "description": "How the confidence was computed",
                            },
                        },
                        "required": ["name"],
                    },
                },
            },
            "required": ["name"],
        }

        metadata_schema["properties"]["PoseEstimation"]["properties"] = {
            "Skeletons": skeleton_schema,
            "Devices": devices_schema,
            "PoseEstimationContainers": containers_schema,
        }

        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        container_name = self.pose_estimation_metadata_key
        skeleton_name = f"Skeleton{container_name}_{self.subject_name.capitalize()}"

        devices_metadata = {}
        for camera_name in self._camera_names:
            devices_metadata[camera_name] = {
                "name": camera_name,
                "description": f"Camera '{camera_name}' of the multi-camera system used for 3D pose estimation.",
                "camera_name": camera_name,
            }

        pose_estimation_series_metadata = {}
        for landmark in self._landmark_names:
            landmark_capitalized = landmark.replace("_", " ").title().replace(" ", "")
            pose_estimation_series_metadata[landmark] = {
                "name": f"PoseEstimationSeries{landmark_capitalized}",
                "description": f"3D position of {landmark}.",
                "unit": "millimeters",
                "reference_frame": "3D coordinate system defined by the DANNCE calibration.",
                "confidence_definition": "Maximum probability from the 3D probability volume.",
            }

        metadata["PoseEstimation"] = {
            "Skeletons": {
                skeleton_name: {
                    "name": skeleton_name,
                    "nodes": list(self._landmark_names),
                    "edges": [],
                    "subject": self.subject_name,
                }
            },
            "Devices": devices_metadata,
            "PoseEstimationContainers": {
                container_name: {
                    "name": container_name,
                    "description": "3D keypoint coordinates estimated using DANNCE.",
                    "source_software": "DANNCE",
                    "scorer": "DANNCE",
                    "skeleton": skeleton_name,
                    "devices": list(devices_metadata.keys()),
                    "PoseEstimationSeries": pose_estimation_series_metadata,
                }
            },
        }

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        stub_test: bool = False,
        source_videos: dict[str, ImageSeries] | None = None,
        camera_calibrations: dict[str, dict] | None = None,
    ) -> None:
        """
        Add DANNCE pose estimation data to an NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the pose estimation data to.
        metadata : dict, optional
            Metadata dictionary. If provided, overrides default metadata from ``get_metadata()``.
        stub_test : bool, default: False
            If True, write only the first 100 frames to the NWB file for quick smoke testing.
            The interface's internal data arrays are not mutated.
        source_videos : dict of str to ImageSeries, optional
            Formal NWB links to ``ImageSeries`` containing the source video for each camera,
            keyed by camera name (matching the ``camera_names`` passed at construction, e.g.
            ``{"Camera1": image_series_1, "Camera2": image_series_2}``). Each ``ImageSeries`` must
            already be added to the ``NWBFile`` (e.g. in ``nwbfile.acquisition``) before calling
            this method. Cameras without a corresponding entry are linked with no source video.
            Each is linked from its corresponding per-camera ``PoseEstimation`` child of the
            ``MultiCameraPoseEstimation`` container.
        camera_calibrations : dict of str to dict, optional
            Intrinsic/extrinsic calibration parameters for each camera, keyed by camera name
            (matching ``camera_names``), e.g.::

                {
                    "Camera1": dict(
                        intrinsic_matrix=...,  # required, shape (3, 3)
                        rotation_matrix=...,  # optional, shape (3, 3)
                        translation_vector=...,  # optional, shape (3,)
                        distortion_coefficients=...,  # optional
                    ),
                }

            When a camera has a matching entry, its Device is created as an ``ndx_pose.CalibratedCamera``
            (a ``Device`` extended with these calibration fields) instead of a plain ``Device``. Cameras
            without a corresponding entry get a plain ``Device``. Ignored for a camera whose Device was
            already added to the ``NWBFile`` by a previous call (e.g. a shared camera already created by
            another animal's interface instance). Merged on top of any calibrations already loaded from
            ``calibration_path`` at construction, taking precedence per-camera over those.
        """
        from ndx_pose import (
            CalibratedCamera,
            MultiCameraPoseEstimation,
            PoseEstimation,
            PoseEstimationSeries,
            Skeleton,
            Skeletons,
        )

        # Build metadata
        default_metadata = DeepDict(self.get_metadata())
        if metadata:
            default_metadata.deep_update(metadata)

        pose_estimation_metadata = default_metadata["PoseEstimation"]
        container_metadata = pose_estimation_metadata["PoseEstimationContainers"][self.pose_estimation_metadata_key]

        # Get timestamps (sliced when stub_test=True)
        timestamps = self.get_timestamps(stub_test=stub_test)
        timestamps = np.asarray(timestamps, dtype="float64")
        n_samples = timestamps.shape[0]

        rate = calculate_regular_series_rate(timestamps)
        if rate is not None:
            timing_kwargs = dict(rate=rate, starting_time=timestamps[0])
        else:
            timing_kwargs = dict(timestamps=timestamps)

        # Create skeleton
        skeleton_metadata_key = container_metadata["skeleton"]
        skeleton_metadata = pose_estimation_metadata["Skeletons"][skeleton_metadata_key]

        skeleton_subject = skeleton_metadata.get("subject")
        if nwbfile.subject is not None and skeleton_subject == nwbfile.subject.subject_id:
            subject = nwbfile.subject
        else:
            subject = None

        edges = skeleton_metadata.get("edges")
        skeleton = Skeleton(
            name=skeleton_metadata["name"],
            nodes=skeleton_metadata["nodes"],
            edges=np.array(edges) if edges else None,
            subject=subject,
        )

        # Add skeleton to behavior module
        behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="processed behavioral data")
        if "Skeletons" not in behavior_module.data_interfaces:
            skeletons = Skeletons(skeletons=[skeleton])
            behavior_module.add(skeletons)
        else:
            skeletons = behavior_module["Skeletons"]
            skeletons.add_skeletons(skeleton)

        # Create PoseEstimationSeries for each landmark
        pose_estimation_series = []
        series_metadata = container_metadata.get("PoseEstimationSeries", {})

        for i, landmark in enumerate(self._landmark_names):
            data = self._pred[:n_samples, :, i]  # shape: (n_samples, 3)
            confidence = self._p_max[:n_samples, i]  # shape: (n_samples,)

            # Default series kwargs
            landmark_capitalized = landmark.replace("_", " ").title().replace(" ", "")
            series_kwargs = dict(
                name=f"PoseEstimationSeries{landmark_capitalized}",
                description=f"3D position of {landmark}.",
                data=data,
                unit="millimeters",
                reference_frame="3D coordinate system defined by the DANNCE calibration.",
                confidence=confidence,
                confidence_definition="Maximum probability from the 3D probability volume.",
                **timing_kwargs,
            )

            # Override with user-provided series metadata
            if landmark in series_metadata:
                series_kwargs.update(series_metadata[landmark])
                # Restore data fields that shouldn't be overridden by metadata
                series_kwargs["data"] = data
                series_kwargs["confidence"] = confidence
                series_kwargs.update(timing_kwargs)

            series = PoseEstimationSeries(**series_kwargs)
            pose_estimation_series.append(series)

        # Create or get one Device per camera, named directly after the camera (not derived from the
        # per-instance pose_estimation_metadata_key), so multiple interface instances writing to the same
        # NWBFile with matching camera_names (e.g., one interface instance per animal_index) share and
        # reuse the same camera Devices.
        source_videos = source_videos or {}
        # Calibrations loaded from calibration_path at construction are the default; an explicit
        # camera_calibrations argument here overrides individual cameras on top of those.
        camera_calibrations = {**(self._camera_calibrations or {}), **(camera_calibrations or {})}
        camera_pose_estimations = []
        for device_metadata_key in container_metadata["devices"]:
            device_metadata = pose_estimation_metadata["Devices"][device_metadata_key]
            device_name = device_metadata["name"]
            camera_name = device_metadata.get("camera_name", device_name)

            if device_name not in nwbfile.devices:
                calibration = camera_calibrations.get(camera_name)
                if calibration is not None:
                    camera = CalibratedCamera(
                        name=device_name,
                        description=device_metadata.get("description", "Camera used for pose estimation."),
                        intrinsic_matrix=calibration["intrinsic_matrix"],
                        rotation_matrix=calibration.get("rotation_matrix"),
                        translation_vector=calibration.get("translation_vector"),
                        distortion_coefficients=calibration.get("distortion_coefficients"),
                    )
                    nwbfile.add_device(camera)
                else:
                    camera = nwbfile.create_device(
                        name=device_name,
                        description=device_metadata.get("description", "Camera used for pose estimation."),
                    )
            else:
                camera = nwbfile.devices[device_name]

            # Per-camera PoseEstimation child: DANNCE/sDANNCE only produce triangulated 3D world-space
            # landmarks (no raw per-camera 2D data), so this child carries no pose_estimation_series of
            # its own -- it exists solely to formally link the camera Device (and, when available, that
            # camera's source video) under the MultiCameraPoseEstimation container.
            camera_pose_estimation = PoseEstimation(
                name=f"{device_name}PoseEstimation",
                device=camera,
                source_video=source_videos.get(camera_name),
            )
            camera_pose_estimations.append(camera_pose_estimation)

        # Create MultiCameraPoseEstimation container holding the 3D world-space landmark series
        pose_estimation = MultiCameraPoseEstimation(
            name=container_metadata["name"],
            pose_estimation_series=pose_estimation_series,
            pose_estimations=camera_pose_estimations,
            description=container_metadata.get("description", "3D keypoint coordinates estimated using DANNCE."),
            scorer=container_metadata.get("scorer"),
            source_software=container_metadata.get("source_software", "DANNCE"),
            source_software_version=container_metadata.get("source_software_version"),
            skeleton=skeleton,
        )

        behavior_module.add(pose_estimation)
