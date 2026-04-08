from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module
from ....utils import DeepDict, calculate_regular_series_rate, get_base_schema


class DANNCEInterface(BaseTemporalAlignmentInterface):
    """Data interface for DANNCE 3D pose estimation datasets."""

    display_name = "DANNCE"
    keywords = ("DANNCE", "3D pose estimation", "behavior", "pose estimation")
    associated_suffixes = (".mat",)
    info = "Interface for DANNCE 3D pose estimation output data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"][
            "description"
        ] = "Path to the DANNCE prediction .mat file (e.g., save_data_AVG.mat)."
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        video_file_path: FilePath | None = None,
        sampling_rate: float | None = None,
        landmark_names: list[str] | None = None,
        subject_name: str = "ind1",
        pose_estimation_metadata_key: str = "PoseEstimationDANNCE",
        verbose: bool = False,
    ):
        """
        Interface for writing DANNCE 3D pose estimation output files to NWB.

        DANNCE (3-Dimensional Aligned Neural Network for Computational Ethology) is a
        multi-camera 3D pose estimation system that tracks anatomical landmarks on animals.
        This interface reads DANNCE prediction .mat files and converts them to NWB format
        using the ndx-pose extension.

        Parameters
        ----------
        file_path : FilePath
            Path to the DANNCE prediction .mat file (e.g., save_data_AVG.mat or save_data_MAX.mat).
        video_file_path : FilePath, optional
            Path to one of the source video files used for DANNCE prediction. Used to extract
            per-frame timestamps, which are then indexed by the sampleID field to obtain the
            timestamps for each prediction. Takes precedence over ``sampling_rate``.
        sampling_rate : float, optional
            The sampling rate in Hz of the pose estimation data. Used to compute timestamps from
            the sampleID field. Ignored if ``video_file_path`` is provided. If neither is provided,
            timestamps must be set externally via ``set_aligned_timestamps()`` before conversion.
        landmark_names : list of str, optional
            Names for each tracked landmark/body part. Must match the number of landmarks in the
            data. If not provided, defaults to ``["landmark_0", "landmark_1", ...]``.
        subject_name : str, default: "ind1"
            The subject name used for linking the skeleton to the NWB subject.
        pose_estimation_metadata_key : str, default: "PoseEstimationDANNCE"
            Controls where in the metadata the pose estimation data is stored and the name of the
            PoseEstimation container in the NWB file.
        verbose : bool, default: False
            Controls verbosity of the conversion process.
        """
        from importlib.metadata import version

        import ndx_pose  # noqa: F401
        from packaging import version as version_parse

        ndx_pose_version = version("ndx-pose")
        if version_parse.parse(ndx_pose_version) < version_parse.parse("0.2.0"):
            raise ImportError(
                "DANNCE interface requires ndx-pose version 0.2.0 or later. "
                f"Found version {ndx_pose_version}. Please upgrade: "
                "pip install 'ndx-pose>=0.2.0'"
            )

        file_path = Path(file_path)
        if ".mat" not in file_path.suffixes:
            raise IOError(f"The file '{file_path}' is not a valid DANNCE output file. Only .mat files are supported.")

        self.subject_name = subject_name
        self.verbose = verbose
        self.pose_estimation_metadata_key = pose_estimation_metadata_key
        self._sampling_rate = sampling_rate
        self._video_file_path = Path(video_file_path) if video_file_path is not None else None
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

        # Compute timestamps: video_file_path takes precedence over sampling_rate
        if video_file_path is not None:
            self._timestamps = self._get_timestamps_from_video()
        elif sampling_rate is not None:
            self._timestamps = self._sample_id / sampling_rate

        super().__init__(file_path=file_path, video_file_path=video_file_path, verbose=verbose)

    def _load_dannce_data(self, file_path: Path) -> None:
        """Load and parse the DANNCE .mat prediction file."""
        from scipy.io import loadmat

        mat_data = loadmat(str(file_path))

        self._pred = mat_data["pred"]  # shape: (n_samples, 3, n_landmarks)
        self._p_max = mat_data["p_max"]  # shape: (n_samples, n_landmarks)
        sample_id = mat_data["sampleID"]  # shape: (1, n_samples) or (n_samples,)
        self._sample_id = np.squeeze(sample_id).astype("float64")

    def _get_timestamps_from_video(self) -> np.ndarray:
        """Extract timestamps from the video file, indexed by sampleID."""
        from ...video.video_utils import VideoCaptureContext

        with VideoCaptureContext(file_path=str(self._video_file_path)) as video:
            all_timestamps = video.get_video_timestamps()

        frame_indices = self._sample_id.astype(int)
        return np.asarray(all_timestamps[frame_indices], dtype="float64")

    def get_original_timestamps(self) -> np.ndarray:
        if self._video_file_path is not None:
            return self._get_timestamps_from_video()
        if self._sampling_rate is not None:
            return self._sample_id / self._sampling_rate
        raise ValueError(
            "Cannot compute original timestamps without a video file or sampling rate. "
            "Provide 'video_file_path' or 'sampling_rate' when initializing the interface, "
            "or use 'set_aligned_timestamps()' to set timestamps directly."
        )

    def get_timestamps(self) -> np.ndarray:
        if self._timestamps is not None:
            return self._timestamps
        return self.get_original_timestamps()

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
            },
            "required": ["name"],
        }

        containers_schema = get_base_schema(tag="PoseEstimationContainers")
        containers_schema["additionalProperties"] = {
            "type": "object",
            "description": "Metadata for a PoseEstimation group",
            "properties": {
                "name": {"type": "string", "description": "Name of the PoseEstimation group"},
                "description": {"type": ["string", "null"], "description": "Description of the pose estimation"},
                "source_software": {"type": ["string", "null"], "description": "Name of the software tool used"},
                "source_software_version": {"type": ["string", "null"], "description": "Version of the software"},
                "scorer": {"type": ["string", "null"], "description": "Name of the scorer or algorithm"},
                "skeleton": {"type": ["string", "null"], "description": "Reference to a Skeleton"},
                "devices": {
                    "type": ["array", "null"],
                    "description": "References to Device objects",
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
                            "unit": {"type": ["string", "null"], "description": "Unit of measurement", "default": "mm"},
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
        device_name = f"Camera{container_name}"

        pose_estimation_series_metadata = {}
        for landmark in self._landmark_names:
            landmark_capitalized = landmark.replace("_", " ").title().replace(" ", "")
            pose_estimation_series_metadata[landmark] = {
                "name": f"PoseEstimationSeries{landmark_capitalized}",
                "description": f"3D position of {landmark}.",
                "unit": "mm",
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
            "Devices": {
                device_name: {
                    "name": device_name,
                    "description": "Multi-camera system used for 3D pose estimation with DANNCE.",
                }
            },
            "PoseEstimationContainers": {
                container_name: {
                    "name": container_name,
                    "description": "3D keypoint coordinates estimated using DANNCE.",
                    "source_software": "DANNCE",
                    "scorer": "DANNCE",
                    "skeleton": skeleton_name,
                    "devices": [device_name],
                    "PoseEstimationSeries": pose_estimation_series_metadata,
                }
            },
        }

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
    ) -> None:
        """
        Add DANNCE pose estimation data to an NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the pose estimation data to.
        metadata : dict, optional
            Metadata dictionary. If provided, overrides default metadata from ``get_metadata()``.
        """
        from ndx_pose import PoseEstimation, PoseEstimationSeries, Skeleton, Skeletons

        # Build metadata
        default_metadata = DeepDict(self.get_metadata())
        if metadata:
            default_metadata.deep_update(metadata)

        pose_estimation_metadata = default_metadata["PoseEstimation"]
        container_metadata = pose_estimation_metadata["PoseEstimationContainers"][self.pose_estimation_metadata_key]

        # Get timestamps
        timestamps = self.get_timestamps()
        timestamps = np.asarray(timestamps, dtype="float64")

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

        skeleton = Skeleton(
            name=skeleton_metadata["name"],
            nodes=skeleton_metadata["nodes"],
            edges=np.array(skeleton_metadata["edges"]) if skeleton_metadata["edges"] else None,
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
            data = self._pred[:, :, i]  # shape: (n_samples, 3)
            confidence = self._p_max[:, i]  # shape: (n_samples,)

            # Default series kwargs
            landmark_capitalized = landmark.replace("_", " ").title().replace(" ", "")
            series_kwargs = dict(
                name=f"PoseEstimationSeries{landmark_capitalized}",
                description=f"3D position of {landmark}.",
                data=data,
                unit="mm",
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

        # Create or get device
        device_metadata_key = container_metadata["devices"][0]
        device_metadata = pose_estimation_metadata["Devices"][device_metadata_key]
        device_name = device_metadata["name"]

        if device_name not in nwbfile.devices:
            camera = nwbfile.create_device(
                name=device_name,
                description=device_metadata.get("description", "Camera used for pose estimation."),
            )
        else:
            camera = nwbfile.devices[device_name]

        # Create PoseEstimation container
        pose_estimation = PoseEstimation(
            name=container_metadata["name"],
            pose_estimation_series=pose_estimation_series,
            description=container_metadata.get("description", "3D keypoint coordinates estimated using DANNCE."),
            devices=[camera],
            scorer=container_metadata.get("scorer"),
            source_software=container_metadata.get("source_software", "DANNCE"),
            source_software_version=container_metadata.get("source_software_version"),
            skeleton=skeleton,
        )

        behavior_module.add(pose_estimation)
