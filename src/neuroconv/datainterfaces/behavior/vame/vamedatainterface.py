"""DataInterface for VAME behavioral segmentation data."""

import json
import warnings
from pathlib import Path

import numpy as np
from packaging.version import Version
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module
from ....utils import DeepDict, calculate_regular_series_rate, load_dict_from_file


class VameInterface(BaseTemporalAlignmentInterface):
    """DataInterface for VAME behavioral segmentation data using the ndx-vame NWB extension.

    VAME (Variational Animal Motion Encoding) segments animal behavior into discrete motifs
    by training a variational autoencoder on pose estimation time series.

    This interface writes the per-frame motif labels, latent-space embeddings, and community
    labels to NWB using the ``ndx-vame`` extension.

    The NWB container name and all series descriptions are controlled via the metadata dict
    under ``metadata["Behavior"]["Vame"]``.

    Metadata Structure
    ------------------
    The container and its series live in separate, flat registries under ``metadata["Behavior"]["Vame"]``
    (one registry per type), following the unified metadata pattern used elsewhere in NeuroConv: each
    series links *up* to its ``VAMEProject`` via ``vame_project_metadata_key`` rather than being nested
    inside it. Series keys are project-prefixed so several projects can share one NWB file.

    .. code-block:: python

        metadata = {
            "Behavior": {
                "Vame": {
                    "VameProjects": {
                        "VAMEProject": {                       # keyed by metadata_key (default "VAMEProject")
                            "name": "VAMEProject",
                            "pose_estimation_metadata_key": "DLC",  # optional, -> Behavior/Pose/PoseEstimations
                            "video_metadata_key": "video_0",   # optional, -> Behavior/InternalVideos|ExternalVideos
                        }
                    },
                    "MotifSeries": {
                        "VAMEProject_motif_kmeans": {
                            "name": "MotifSeriesKmeans",
                            "description": "VAME behavioral motif labels.",
                            "algorithm": "kmeans",
                            "vame_project_metadata_key": "VAMEProject",
                            "latent_space_metadata_key": "VAMEProject_latent_space",  # optional
                        },
                    },
                    "CommunitySeries": {
                        "VAMEProject_community_kmeans": {
                            "name": "CommunitySeriesKmeans",
                            "description": "VAME community labels ...",
                            "vame_project_metadata_key": "VAMEProject",
                            "motif_series_metadata_key": "VAMEProject_motif_kmeans",  # -> MotifSeries
                        },
                    },
                    "LatentSpaceSeries": {                     # optional — one per project, shared across runs
                        "VAMEProject_latent_space": {
                            "name": "LatentSpaceSeries",
                            "description": "VAME latent-space embeddings (30 dimensions per frame).",
                            "vame_project_metadata_key": "VAMEProject",
                        },
                    },
                }
            }
        }

    The metadata can be customized by:

    #. Calling :meth:`get_metadata` to retrieve the defaults.
    #. Modifying the returned dictionary as needed.
    #. Passing the modified metadata to :meth:`add_to_nwbfile` or :meth:`run_conversion`.

    Notes
    -----
    - ``motif_series_metadata_key`` in a ``CommunitySeries`` entry is automatically set to the matching
      run's ``MotifSeries`` key when the same run exists in ``motif_labels_file_paths``.
    - ``pose_estimation_metadata_key`` must name a ``PoseEstimation`` entry (in
      ``Behavior/Pose/PoseEstimations``) whose container is already present in the NWB file when
      :meth:`add_to_nwbfile` is called (i.e. the pose estimation interface must run first).
    - ``video_metadata_key`` optionally names a video entry (in ``Behavior/InternalVideos`` or
      ``Behavior/ExternalVideos``) whose ``ImageSeries`` is already present in the NWB file; each
      ``EthogramBouts`` links to it via ``source_video`` (the video interface must run first).
    - Everything inside a single VAME project links to the same pose estimation and the same video:
      ``pose_estimation_metadata_key`` and ``video_metadata_key`` live on the ``VameProjects`` entry
      (not on the per-run series), so every ``MotifSeries`` / ``CommunitySeries`` and every derived
      ``EthogramBouts`` in that project shares one ``PoseEstimation`` and one ``ImageSeries``. These
      keys are single-valued by design: a VAME project is one aligned session with a single pose
      source. This assumes a single-camera ``PoseEstimation``; a multi-camera project would point the
      same single key at an aggregate multi-camera pose container rather than needing multiple links.
    - To store two completely separate VAME trainings in the same file, create two ``VameInterface``
      instances with different ``metadata_key`` values and wrap them in an
      :class:`~neuroconv.NWBConverter`.
    """

    display_name = "VAME"
    keywords = ("VAME", "behavioral motifs", "pose segmentation")
    associated_suffixes = (".npy", ".yaml")
    info = "Interface for adding data from VAME (Variational Animal Motion Encoding)."

    _timestamps = None

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = (
            "Path to the VAME 'config.yaml' project file. "
            "The full configuration is serialized as JSON and stored in the VAMEProject.vame_config field."
        )
        source_schema["properties"]["session_name"] = {
            "type": "string",
            "description": (
                "Session name as it appears in config.yaml 'session_names'. "
                "When provided, motif labels, latent vectors, and community labels are "
                "auto-discovered from the standard VAME results layout under config.yaml's parent directory. "
                "Explicitly supplied file path arguments take precedence over auto-discovered paths."
            ),
        }
        source_schema["properties"]["motif_labels_file_paths"]["description"] = (
            "Dict mapping a run name to the .npy file containing VAME motif labels "
            "(1D int array, one cluster ID per video frame). "
            'Example: {"kmeans": "path/to/15_kmeans_label.npy", "hmm": "path/to/15_hmm_label.npy"}.'
        )
        source_schema["properties"]["latent_vectors_file_path"]["description"] = (
            "Path to the .npy file containing VAME latent-space vectors "
            "(2D float32 array of shape (n_frames, n_latent_dims)). "
            "Shared across all algorithm runs within the same project. Optional."
        )
        source_schema["properties"]["community_labels_file_paths"]["description"] = (
            "Dict mapping a run name to the .npy file containing VAME community labels "
            "(1D int array, one community ID per video frame). "
            'Example: {"kmeans": "path/to/cohort_community_label.npy"}. Optional.'
        )
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        session_name: str | None = None,
        latent_vectors_file_path: FilePath | None = None,
        motif_labels_file_paths: dict[str, FilePath] | None = None,
        community_labels_file_paths: dict[str, FilePath] | None = None,
        sampling_frequency_hz: float | None = None,
        metadata_key: str = "VAMEProject",
        verbose: bool = False,
    ):
        """Initialize VameInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the VAME ``config.yaml`` project file. The full configuration
            is serialized as JSON and stored in the ``VAMEProject.vame_config`` field.
        session_name : str, optional
            Session name as it appears in ``config.yaml`` under ``session_names``. When
            provided, motif labels, latent vectors, and community labels are auto-discovered
            from the standard VAME results layout under the config file's parent directory::

                <config_parent>/results/<session_name>/VAME/
                    latent_vectors.npy
                    <algorithm>-<n_clusters>/
                        <n_clusters>_<algorithm>_label_<session_name>.npy
                        community/
                            cohort_community_label_<session_name>.npy

            Algorithms and ``n_clusters`` are read from the config. Explicitly supplied
            ``motif_labels_file_paths``, ``latent_vectors_file_path``, or
            ``community_labels_file_paths`` arguments take precedence over auto-discovered paths.
        latent_vectors_file_path : FilePath, optional
            Path to the .npy file containing VAME latent-space vectors (2D float32 array of
            shape ``(n_frames, n_latent_dims)``). Shared across all algorithm runs — a single
            ``LatentSpaceSeries`` is written and each ``MotifSeries`` links to it.
        motif_labels_file_paths : dict[str, FilePath], optional
            Dict mapping a run name to the .npy file containing VAME motif labels
            (1D int array, one cluster ID per video frame). Each entry becomes a separate
            ``MotifSeries`` in the NWB file. Example::
                {"kmeans": "path/to/15_kmeans_label.npy", "hmm": "path/to/15_hmm_label.npy"}
        community_labels_file_paths : dict[str, FilePath], optional
            Dict mapping a run name to the .npy file containing VAME community labels
            (1D int array, one community ID per video frame). When a run key matches one in
            ``motif_labels_file_paths``, the ``CommunitySeries`` is automatically linked to
            that ``MotifSeries``. Example::
                {"kmeans": "path/to/cohort_community_label.npy"}
        sampling_frequency_hz : float, optional
            Video acquisition rate in Hz (frames per second). Required when not providing aligned
            timestamps via :meth:`set_aligned_timestamps`.
        metadata_key : str, default "VAMEProject"
            Key of this interface's ``VAMEProject`` entry in
            ``metadata["Behavior"]["Vame"]["VameProjects"]`` (also the prefix of its series keys).
            Change this when storing
            results from multiple VAME projects in the same NWB file so each project
            has a unique metadata entry and ``VAMEProject`` container.
        verbose : bool, default False
            Controls verbosity of the conversion process.
        """
        import ndx_vame  # noqa: F401 – ensure ndx-vame namespace is registered

        self._vame_config = load_dict_from_file(file_path)

        if session_name is not None:
            (
                motif_labels_file_paths,
                latent_vectors_file_path,
                community_labels_file_paths,
            ) = self._autodiscover_file_paths(
                file_path=Path(file_path),
                session_name=session_name,
                motif_labels_file_paths=motif_labels_file_paths,
                latent_vectors_file_path=latent_vectors_file_path,
                community_labels_file_paths=community_labels_file_paths,
            )

        self._motif_labels_file_paths = (
            {k: Path(v) for k, v in motif_labels_file_paths.items()} if motif_labels_file_paths else None
        )
        self._latent_vectors_file_path = Path(latent_vectors_file_path) if latent_vectors_file_path else None
        self._community_labels_file_paths = (
            {k: Path(v) for k, v in community_labels_file_paths.items()} if community_labels_file_paths else None
        )
        self._sampling_frequency_hz = sampling_frequency_hz
        self._metadata_key = metadata_key

        super().__init__(
            file_path=file_path,
            session_name=session_name,
            motif_labels_file_paths=motif_labels_file_paths,
            latent_vectors_file_path=latent_vectors_file_path,
            community_labels_file_paths=community_labels_file_paths,
            verbose=verbose,
        )

    # Oldest VAME version whose results layout (segmentation_algorithms list + per-algorithm
    # subdirectory naming) we have verified against real test data.
    _AUTODISCOVER_MIN_VAME_VERSION = "0.13.0"

    def _autodiscover_file_paths(
        self,
        *,
        file_path: Path,
        session_name: str,
        motif_labels_file_paths: dict | None,
        latent_vectors_file_path: Path | None,
        community_labels_file_paths: dict | None,
    ) -> tuple:
        """Return (motif_labels_file_paths, latent_vectors_file_path, community_labels_file_paths)
        with any None argument filled in from the standard VAME results layout."""
        vame_version_str = self._vame_config.get("vame_version")
        if vame_version_str is None:
            warnings.warn(
                "The VAME config does not contain a 'vame_version' field. "
                f"Auto-discovery of file paths has only been verified for VAME >= "
                f"{self._AUTODISCOVER_MIN_VAME_VERSION}. Results may be incorrect for older versions.",
                UserWarning,
                stacklevel=3,
            )
        elif Version(str(vame_version_str)) < Version(self._AUTODISCOVER_MIN_VAME_VERSION):
            warnings.warn(
                f"VAME version {vame_version_str} is older than {self._AUTODISCOVER_MIN_VAME_VERSION}. "
                "Auto-discovery of file paths has only been verified for VAME >= "
                f"{self._AUTODISCOVER_MIN_VAME_VERSION} and may not work correctly for this version.",
                UserWarning,
                stacklevel=3,
            )

        algorithms = self._vame_config.get("segmentation_algorithms", [])
        n_clusters = self._vame_config.get("n_clusters")
        if not algorithms or n_clusters is None:
            warnings.warn(
                "Cannot auto-discover VAME file paths: 'segmentation_algorithms' or 'n_clusters' "
                "is missing from config.yaml. Provide file paths explicitly.",
                UserWarning,
                stacklevel=3,
            )
            return (
                motif_labels_file_paths,
                latent_vectors_file_path,
                community_labels_file_paths,
            )

        project_dir = file_path.parent
        session_vame_dir = project_dir / "results" / session_name / "VAME"

        if motif_labels_file_paths is None:
            discovered = {
                algo: session_vame_dir / f"{algo}-{n_clusters}" / f"{n_clusters}_{algo}_label_{session_name}.npy"
                for algo in algorithms
                if (
                    session_vame_dir / f"{algo}-{n_clusters}" / f"{n_clusters}_{algo}_label_{session_name}.npy"
                ).exists()
            }
            if discovered:
                motif_labels_file_paths = discovered
            else:
                warnings.warn(
                    f"No motif label files were found for session '{session_name}' under '{session_vame_dir}'. "
                    "Provide motif_labels_file_paths explicitly if the files are in a non-standard location.",
                    UserWarning,
                    stacklevel=3,
                )

        if latent_vectors_file_path is None:
            candidate = session_vame_dir / "latent_vectors.npy"
            if candidate.exists():
                latent_vectors_file_path = candidate

        if community_labels_file_paths is None:
            discovered = {
                algo: session_vame_dir
                / f"{algo}-{n_clusters}"
                / "community"
                / f"cohort_community_label_{session_name}.npy"
                for algo in algorithms
                if (
                    session_vame_dir
                    / f"{algo}-{n_clusters}"
                    / "community"
                    / f"cohort_community_label_{session_name}.npy"
                ).exists()
            }
            if discovered:
                community_labels_file_paths = discovered

        return (
            motif_labels_file_paths,
            latent_vectors_file_path,
            community_labels_file_paths,
        )

    # Default metadata keys for this interface's flat series registries. They are project-prefixed
    # (and type-distinct) so several VAME projects can share one NWB file without key collisions, and
    # are derived consistently here so get_metadata and add_to_nwbfile agree on the addresses.
    def _motif_series_key(self, run_key: str) -> str:
        return f"{self._metadata_key}_motif_{run_key}"

    def _community_series_key(self, run_key: str) -> str:
        return f"{self._metadata_key}_community_{run_key}"

    def _latent_space_series_key(self) -> str:
        return f"{self._metadata_key}_latent_space"

    def get_metadata_schema(self) -> dict:
        from ....utils import get_base_schema

        metadata_schema = super().get_metadata_schema()

        # The VAME series live in flat, addressable registries under Behavior/Vame (one per type),
        # each linking UP to its VAMEProject container via vame_project_metadata_key. This mirrors the
        # unified metadata pattern used by ophys/ecephys (flat series registries + *_metadata_key links)
        # rather than nesting the series inside the container.
        vame_project_schema = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the VAMEProject group in the NWB file.",
                },
                "pose_estimation_metadata_key": {
                    "type": ["string", "null"],
                    "description": "Key of a PoseEstimation entry (in Behavior/Pose/PoseEstimations) to link to.",
                },
                "video_metadata_key": {
                    "type": ["string", "null"],
                    "description": "Key of a video entry (in Behavior/InternalVideos or Behavior/ExternalVideos) "
                    "whose ImageSeries the ethogram bouts link to via source_video.",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        }
        motif_entry_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the MotifSeries."},
                "description": {"type": "string"},
                "algorithm": {
                    "type": ["string", "null"],
                    "description": "The algorithm used for motif detection.",
                },
                "vame_project_metadata_key": {
                    "type": ["string", "null"],
                    "description": "Key of the VAMEProject (in Behavior/Vame/VameProjects) this series nests under.",
                },
                "latent_space_metadata_key": {
                    "type": ["string", "null"],
                    "description": "Key of the LatentSpaceSeries (in Behavior/Vame/LatentSpaceSeries) to link to.",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        }
        community_entry_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the CommunitySeries."},
                "description": {"type": "string"},
                "algorithm": {
                    "type": ["string", "null"],
                    "description": "The algorithm used for community clustering.",
                },
                "vame_project_metadata_key": {
                    "type": ["string", "null"],
                    "description": "Key of the VAMEProject (in Behavior/Vame/VameProjects) this series nests under.",
                },
                "motif_series_metadata_key": {
                    "type": ["string", "null"],
                    "description": "Key of the MotifSeries (in Behavior/Vame/MotifSeries) this series links to.",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        }
        latent_entry_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the LatentSpaceSeries."},
                "description": {"type": "string"},
                "vame_project_metadata_key": {
                    "type": ["string", "null"],
                    "description": "Key of the VAMEProject (in Behavior/Vame/VameProjects) this series nests under.",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        }
        named_entry_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        }
        # Curated ndx-ethogram entry: lives in the shared top-level Behavior/Ethograms registry, not
        # under Behavior/Vame, because the curated layer is producer-agnostic.
        ethogram_entry_schema = {
            "type": "object",
            "properties": {
                "EthogramBouts": named_entry_schema,
                "Ethogram": named_entry_schema,
            },
            "additionalProperties": False,
        }

        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        metadata_schema["properties"]["Behavior"]["properties"] = {
            "Vame": {
                "type": "object",
                "properties": {
                    "VameProjects": {"type": "object", "properties": {}, "additionalProperties": vame_project_schema},
                    "MotifSeries": {"type": "object", "properties": {}, "additionalProperties": motif_entry_schema},
                    "CommunitySeries": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": community_entry_schema,
                    },
                    "LatentSpaceSeries": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": latent_entry_schema,
                    },
                },
                "additionalProperties": False,
            },
            "Ethograms": {
                "type": "object",
                "properties": {},
                "additionalProperties": ethogram_entry_schema,
            },
        }

        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        # The container and its series live in separate, flat registries under Behavior/Vame; each
        # series links UP to its project via vame_project_metadata_key (the unified metadata pattern).
        vame_metadata: dict = {"VameProjects": {self._metadata_key: dict(name=self._metadata_key)}}

        latent_key = None
        if self._latent_vectors_file_path is not None:
            zdims = self._vame_config.get("zdims")
            dims_info = f" ({zdims} dimensions per frame)" if zdims else ""
            latent_key = self._latent_space_series_key()
            vame_metadata["LatentSpaceSeries"] = {
                latent_key: dict(
                    name="LatentSpaceSeries",
                    description=f"VAME latent-space embeddings{dims_info}.",
                    vame_project_metadata_key=self._metadata_key,
                )
            }

        if self._motif_labels_file_paths is not None:
            vame_metadata["MotifSeries"] = {
                self._motif_series_key(run_key): dict(
                    name=f"MotifSeries{run_key.capitalize()}",
                    description="VAME behavioral motif labels.",
                    algorithm=run_key,
                    vame_project_metadata_key=self._metadata_key,
                    latent_space_metadata_key=latent_key,
                )
                for run_key in self._motif_labels_file_paths
            }

        if self._community_labels_file_paths is not None:
            vame_metadata["CommunitySeries"] = {
                self._community_series_key(run_key): dict(
                    name=f"CommunitySeries{run_key.capitalize()}",
                    description="VAME community labels grouping motifs into higher-level behavioral states.",
                    algorithm=run_key,
                    vame_project_metadata_key=self._metadata_key,
                    motif_series_metadata_key=(
                        self._motif_series_key(run_key)
                        if self._motif_labels_file_paths and run_key in self._motif_labels_file_paths
                        else None
                    ),
                )
                for run_key in self._community_labels_file_paths
            }

        metadata["Behavior"]["Vame"] = vame_metadata

        # Curated ndx-ethogram products derived from each MotifSeries live in a shared, top-level
        # Behavior/Ethograms registry (not nested under the VAME project) because the curated layer is
        # producer-agnostic: other segmenters (keypoint-MoSeq, B-SOiD, a standalone EthogramInterface)
        # populate the same registry. Each entry bundles the run-length-encoded EthogramBouts timeline
        # and its Ethogram catalogue (one of each per motif run). The entry key and the object names are
        # prefixed with the project key (metadata_key) so several VAME projects can share one NWB file
        # without collision.
        if self._motif_labels_file_paths is not None:
            metadata["Behavior"]["Ethograms"] = {
                f"{self._metadata_key}_{run_key}": dict(
                    EthogramBouts=dict(
                        name=f"{self._metadata_key}EthogramBouts{run_key.capitalize()}",
                        description="VAME behavioral motifs as run-length-encoded bouts.",
                    ),
                    Ethogram=dict(
                        name=f"{self._metadata_key}Ethogram{run_key.capitalize()}",
                        description="VAME motif catalogue (coding scheme): one row per motif id.",
                    ),
                )
                for run_key in self._motif_labels_file_paths
            }

        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        if self._sampling_frequency_hz is None:
            raise ValueError(
                "VameInterface cannot generate original timestamps without a sampling_frequency_hz. "
                "Provide sampling_frequency_hz at construction or call set_aligned_timestamps()."
            )
        if self._motif_labels_file_paths:
            reference_file = next(iter(self._motif_labels_file_paths.values()))
        elif self._latent_vectors_file_path:
            reference_file = self._latent_vectors_file_path
        elif self._community_labels_file_paths:
            reference_file = next(iter(self._community_labels_file_paths.values()))
        else:
            raise ValueError(
                "VameInterface cannot generate original timestamps without any data file. "
                "Provide at least one of motif_labels_file_paths, latent_vectors_file_path, or "
                "community_labels_file_paths, or call set_aligned_timestamps()."
            )
        num_frames = np.load(reference_file).shape[0]
        time_window = self._vame_config.get("time_window", 0)
        offset_frames = int(time_window // 2)
        starting_time = offset_frames / self._sampling_frequency_hz
        return starting_time + np.arange(num_frames) / self._sampling_frequency_hz

    def get_timestamps(self) -> np.ndarray:
        timestamps = self._timestamps if self._timestamps is not None else self.get_original_timestamps()
        return timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = np.asarray(aligned_timestamps)

    @staticmethod
    def get_available_sessions(file_path: FilePath) -> list[str]:
        """Return the session names listed in a VAME ``config.yaml`` project file.

        Parameters
        ----------
        file_path : FilePath
            Path to the VAME ``config.yaml`` project file.

        Returns
        -------
        list[str]
            Session names from the ``session_names`` field of the config, or an empty list
            if that field is absent.
        """
        config = load_dict_from_file(file_path)
        return list(config.get("session_names", []))

    @staticmethod
    def _get_pose_estimation(nwbfile: NWBFile, name: str):
        pose_estimation_containers = {
            obj.name: obj for obj in nwbfile.objects.values() if type(obj).__name__ == "PoseEstimation"
        }
        if name in pose_estimation_containers:
            return pose_estimation_containers[name]
        if pose_estimation_containers:
            raise ValueError(
                f"No PoseEstimation container named '{name}' was found in the NWB file. "
                f"Available PoseEstimation containers: {list(pose_estimation_containers)}."
            )
        raise ValueError(
            f"No PoseEstimation container named '{name}' was found in the NWB file. "
            "No PoseEstimation containers exist in the file — ensure the pose estimation interface "
            "runs before VameInterface."
        )

    @staticmethod
    def _get_image_series(nwbfile: NWBFile, name: str):
        image_series = {obj.name: obj for obj in nwbfile.objects.values() if type(obj).__name__ == "ImageSeries"}
        if name in image_series:
            return image_series[name]
        if image_series:
            raise ValueError(
                f"No ImageSeries named '{name}' was found in the NWB file. "
                f"Available ImageSeries: {list(image_series)}."
            )
        raise ValueError(
            f"No ImageSeries named '{name}' was found in the NWB file. "
            "No ImageSeries exist in the file — ensure the video interface runs before VameInterface."
        )

    def _add_ethogram_for_run(
        self,
        *,
        behavior_module,
        run_key: str,
        motif_series,
        motif_data: np.ndarray,
        community_data: np.ndarray | None,
        timestamps: np.ndarray,
        frame_period: float,
        pose_estimation,
        source_video,
        bouts_metadata: dict | None,
        catalogue_metadata: dict | None,
    ) -> None:
        """Derive and add a curated ``EthogramBouts`` + ``Ethogram`` catalogue for one motif run.

        Thin VAME-specific adapter over the tool-agnostic
        :func:`neuroconv.tools.behavior.build_ethogram_from_labels`: it supplies VAME's names,
        provenance, full motif label space (``n_clusters``), and the per-frame community labels that
        become the catalogue's ``category`` column.
        """
        if bouts_metadata is None or catalogue_metadata is None:
            return
        from ....tools.behavior import build_ethogram_from_labels

        n_clusters = self._vame_config.get("n_clusters")
        vame_version = str(self._vame_config.get("vame_version", "")).strip()
        parameters = json.dumps(
            dict(
                n_clusters=n_clusters,
                time_window=self._vame_config.get("time_window"),
                algorithm=run_key,
            )
        )
        bouts, catalogue = build_ethogram_from_labels(
            labels=motif_data,
            timestamps=timestamps,
            frame_period=frame_period,
            bouts_name=bouts_metadata["name"],
            bouts_description=bouts_metadata["description"],
            labeling_method="automated",
            source_software=f"VAME {vame_version}" if vame_version else "VAME",
            parameters=parameters,
            source=motif_series,
            source_pose=pose_estimation,
            source_video=source_video,
            catalogue_name=catalogue_metadata["name"],
            catalogue_description=catalogue_metadata["description"],
            class_ids=range(int(n_clusters)) if n_clusters is not None else None,
            class_definition="VAME unsupervised motif; the cluster id has no a-priori meaning.",
            category_labels=community_data,
            exclusive=True,  # VAME motifs are a single-label partition.
        )
        if catalogue is not None:
            behavior_module.add(catalogue)
        behavior_module.add(bouts)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
    ) -> None:
        """Write VAME outputs to an NWBFile as a ``VAMEProject`` container.

        The container name and all series descriptions are taken from the flat registries under
        ``metadata["Behavior"]["Vame"]``. Call :meth:`get_metadata` to
        inspect the defaults and override specific fields before conversion.

        Parameters
        ----------
        nwbfile : NWBFile
            Target NWB file.
        metadata : dict, optional
            Metadata dictionary. VAME-specific fields live in flat registries under
            ``metadata["Behavior"]["Vame"]``:

            - ``"VameProjects"`` – dict of project key →
              ``{name, pose_estimation_metadata_key, video_metadata_key}``.
              ``pose_estimation_metadata_key`` references a ``PoseEstimation`` entry whose container is
              already present in the NWB file (the pose interface must run first); ``video_metadata_key``
              optionally references a video entry (in ``Behavior/InternalVideos`` or
              ``Behavior/ExternalVideos``) whose ``ImageSeries`` the ethogram bouts link to.
            - ``"MotifSeries"`` – dict of series key →
              ``{name, description, algorithm, vame_project_metadata_key, latent_space_metadata_key}``.
            - ``"CommunitySeries"`` – dict of series key →
              ``{name, description, algorithm, vame_project_metadata_key, motif_series_metadata_key}``.
            - ``"LatentSpaceSeries"`` – dict of series key →
              ``{name, description, vame_project_metadata_key}``.

            Each series links to its project via ``vame_project_metadata_key``.
        stub_test : bool, default False
            If ``True``, only the first 100 frames of each data array are written.

        Notes
        -----
        For each motif run this also writes a curated ``ndx-ethogram`` product derived from the
        per-frame ``MotifSeries``: an ``EthogramBouts`` table (the motif labels run-length-encoded
        into one row per bout) and its ``Ethogram`` catalogue. The faithful ``MotifSeries`` is kept;
        the bouts link back to it via ``source``.
        """
        from ndx_vame import (
            CommunitySeries,
            LatentSpaceSeries,
            MotifSeries,
            VAMEProject,
        )

        default_metadata = DeepDict(self.get_metadata())
        if metadata is not None:
            default_metadata.deep_update(metadata)

        vame_metadata = default_metadata["Behavior"]["Vame"]
        project_metadata = vame_metadata["VameProjects"][self._metadata_key]
        project_name = project_metadata["name"]

        n_frames = min(100, len(self.get_timestamps())) if stub_test else None

        timestamps = self.get_timestamps()[:n_frames]
        rate = calculate_regular_series_rate(series=timestamps)

        timing_kwargs = {}
        if rate is None:
            timing_kwargs["timestamps"] = timestamps.astype(np.float64)
        else:
            timing_kwargs["rate"] = float(rate)
            timing_kwargs["starting_time"] = timestamps[0]

        # This interface owns exactly its own project's series, so it resolves each series entry from
        # the flat Behavior/Vame registries by the key it derives from its own run data, dropping the
        # link fields (resolved here in code) before passing the rest as ndx-vame kwargs.
        latent_registry = vame_metadata.get("LatentSpaceSeries", {})
        motif_registry = vame_metadata.get("MotifSeries", {})
        community_registry = vame_metadata.get("CommunitySeries", {})

        # LatentSpaceSeries (optional, shared across algorithm runs)
        latent_series = None
        latent_series_metadata = latent_registry.get(self._latent_space_series_key())
        if self._latent_vectors_file_path is not None and latent_series_metadata is not None:
            latent_meta = dict(latent_series_metadata)
            latent_meta.pop("vame_project_metadata_key", None)
            latent_data = np.load(self._latent_vectors_file_path)[:n_frames].astype(np.float32)
            latent_series = LatentSpaceSeries(data=latent_data, **latent_meta, **timing_kwargs)

        # MotifSeries — one per run key, keyed by its flat-registry metadata key
        motif_series_objects = {}  # motif metadata key -> object
        motif_data_by_run = {}
        for run_key, file_path in (self._motif_labels_file_paths or {}).items():
            motif_key = self._motif_series_key(run_key)
            motif_meta = dict(motif_registry.get(motif_key, {}))
            motif_meta.pop("vame_project_metadata_key", None)
            motif_meta.pop("latent_space_metadata_key", None)
            motif_data = np.load(file_path)[:n_frames].astype(np.int32)
            motif_data_by_run[run_key] = motif_data
            motif_kwargs: dict = dict(data=motif_data, **motif_meta, **timing_kwargs)
            if latent_series is not None:
                motif_kwargs["latent_space_series"] = latent_series
            motif_series_objects[motif_key] = MotifSeries(**motif_kwargs)

        # CommunitySeries — one per run key, optionally linked to a MotifSeries by metadata key
        community_series_objects = {}
        community_data_by_run = {}
        for run_key, file_path in (self._community_labels_file_paths or {}).items():
            community_key = self._community_series_key(run_key)
            community_meta = dict(community_registry.get(community_key, {}))
            community_meta.pop("vame_project_metadata_key", None)
            motif_link_key = community_meta.pop("motif_series_metadata_key", None)
            community_data = np.load(file_path)[:n_frames].astype(np.int32)
            community_data_by_run[run_key] = community_data
            community_kwargs: dict = dict(data=community_data, **community_meta, **timing_kwargs)
            if motif_link_key is not None:
                if motif_link_key not in motif_series_objects:
                    raise ValueError(
                        f"motif_series_metadata_key '{motif_link_key}' on CommunitySeries "
                        f"'{community_key}' does not match any MotifSeries in this project. "
                        f"Available MotifSeries keys: {list(motif_series_objects)}."
                    )
                community_kwargs["motif_series"] = motif_series_objects[motif_link_key]
            community_series_objects[community_key] = CommunitySeries(**community_kwargs)

        # Optional link to an upstream PoseEstimation container, resolved strictly through the
        # Behavior/Pose/PoseEstimations registry. The key is a registry address, not the object name,
        # so it must be registered; there is no name fallback.
        pose_estimation = None
        pose_estimation_key = project_metadata.get("pose_estimation_metadata_key")
        if pose_estimation_key is not None:
            pose_estimations_registry = default_metadata.get("Behavior", {}).get("Pose", {}).get("PoseEstimations", {})
            if pose_estimation_key not in pose_estimations_registry:
                raise ValueError(
                    f"pose_estimation_metadata_key '{pose_estimation_key}' was not found in "
                    f"metadata['Behavior']['Pose']['PoseEstimations']. Available keys: "
                    f"{list(pose_estimations_registry)}."
                )
            pose_container_name = pose_estimations_registry[pose_estimation_key]["name"]
            pose_estimation = self._get_pose_estimation(nwbfile, pose_container_name)

        # Optional link to an upstream video ImageSeries (internal or external video interface),
        # resolved strictly through the Behavior/InternalVideos + Behavior/ExternalVideos registries.
        # The key is a registry address, not the object name, so it must be registered; no fallback.
        source_video = None
        video_key = project_metadata.get("video_metadata_key")
        if video_key is not None:
            behavior_metadata = default_metadata.get("Behavior", {})
            videos_registry = {
                **behavior_metadata.get("InternalVideos", {}),
                **behavior_metadata.get("ExternalVideos", {}),
            }
            if video_key not in videos_registry:
                raise ValueError(
                    f"video_metadata_key '{video_key}' was not found in "
                    f"metadata['Behavior']['InternalVideos'] or metadata['Behavior']['ExternalVideos']. "
                    f"Available keys: {list(videos_registry)}."
                )
            image_series_name = videos_registry[video_key]["name"]
            source_video = self._get_image_series(nwbfile, image_series_name)

        vame_project_kwargs = dict(
            name=project_name,
            vame_config=json.dumps(self._vame_config),
            time_window_samples=int(self._vame_config.get("time_window", 0)),
            vame_version=str(self._vame_config.get("vame_version", "")),
        )
        if latent_series is not None:
            vame_project_kwargs["latent_space_series"] = latent_series
        if motif_series_objects:
            vame_project_kwargs["motif_series"] = list(motif_series_objects.values())
        if community_series_objects:
            vame_project_kwargs["community_series"] = list(community_series_objects.values())

        vame_project = VAMEProject(**vame_project_kwargs)
        if pose_estimation is not None:
            vame_project.pose_estimation = pose_estimation

        behavior_module = get_module(nwbfile, name="behavior", description="processed behavioral data")
        behavior_module.add(vame_project)

        # Curated ndx-ethogram products derived from each MotifSeries (kept alongside the faithful
        # series). Resolved from the shared top-level Behavior/Ethograms registry, keyed by
        # f"{metadata_key}_{run_key}". The source MotifSeries is wired directly (this interface holds
        # the object), so no source_metadata_key resolution is needed.
        if motif_series_objects:
            frame_period = 1.0 / rate if rate is not None else float(np.median(np.diff(timestamps)))
            ethograms_metadata = default_metadata["Behavior"].get("Ethograms", {})
            for run_key in self._motif_labels_file_paths:
                motif_series = motif_series_objects[self._motif_series_key(run_key)]
                ethogram_metadata = ethograms_metadata.get(f"{self._metadata_key}_{run_key}")
                self._add_ethogram_for_run(
                    behavior_module=behavior_module,
                    run_key=run_key,
                    motif_series=motif_series,
                    motif_data=motif_data_by_run[run_key],
                    community_data=community_data_by_run.get(run_key),
                    timestamps=timestamps,
                    frame_period=frame_period,
                    pose_estimation=pose_estimation,
                    source_video=source_video,
                    bouts_metadata=ethogram_metadata.get("EthogramBouts") if ethogram_metadata else None,
                    catalogue_metadata=ethogram_metadata.get("Ethogram") if ethogram_metadata else None,
                )
