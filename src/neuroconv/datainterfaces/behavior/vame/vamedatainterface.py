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
    under ``metadata["Behavior"]["VAMEProjects"][metadata_key]``.

    Metadata Structure
    ------------------
    The metadata is organized in a hierarchical structure:

    .. code-block:: python

        metadata = {
            "Behavior": {
                "VAMEProjects": {
                    "VAMEProject": {            # keyed by metadata_key (default "VAMEProject")
                        "name": "VAMEProject",
                        "LatentSpaceSeries": {  # optional — one per project, shared across runs
                            "name": "LatentSpaceSeries",
                            "description": "VAME latent-space embeddings (30 dimensions per frame).",
                        },
                        "MotifSeries": {        # keyed by run name supplied at construction
                            "kmeans": {
                                "name": "MotifSeriesKmeans",
                                "description": "VAME behavioral motif labels.",
                                "algorithm": "kmeans",
                            },
                            "hmm": {
                                "name": "MotifSeriesHmm",
                                "description": "VAME behavioral motif labels.",
                                "algorithm": "hmm",
                            },
                        },
                        "CommunitySeries": {    # keyed by run name; links to MotifSeries via key
                            "kmeans": {
                                "name": "CommunitySeriesKmeans",
                                "description": "VAME community labels ...",
                                "motif_series_key": "kmeans",  # cross-ref to MotifSeries["kmeans"]
                            },
                        },
                        "pose_estimation_metadata_key": "PoseEstimation",  # cross-ref to Behavior/PoseEstimation
                    }
                }
            }
        }

    The metadata can be customized by:

    #. Calling :meth:`get_metadata` to retrieve the defaults.
    #. Modifying the returned dictionary as needed.
    #. Passing the modified metadata to :meth:`add_to_nwbfile` or :meth:`run_conversion`.

    Notes
    -----
    - ``motif_series_key`` in a ``CommunitySeries`` entry is automatically set to the matching
      run key when the same key exists in ``motif_labels_file_paths``.
    - ``pose_estimation_metadata_key`` must name a ``PoseEstimation`` container that is already
      present in the NWB file when :meth:`add_to_nwbfile` is called (i.e. the pose estimation
      interface must run first).
    - To store results from two completely separate VAME model
    trainings, create two ``VameInterface`` instances with different ``metadata_key`` values and
    wrap them in an :class:`~neuroconv.NWBConverter`.
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
            Key used to look up this interface's metadata inside
            ``metadata["Behavior"]["VAMEProjects"][metadata_key]``. Change this when storing
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
            return motif_labels_file_paths, latent_vectors_file_path, community_labels_file_paths

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

        return motif_labels_file_paths, latent_vectors_file_path, community_labels_file_paths

    def get_metadata_schema(self) -> dict:
        from ....utils import get_base_schema

        metadata_schema = super().get_metadata_schema()

        motif_entry_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the MotifSeries."},
                "description": {"type": "string"},
                "algorithm": {"type": ["string", "null"], "description": "The algorithm used for motif detection."},
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
                "motif_series_key": {
                    "type": ["string", "null"],
                    "description": "Key into MotifSeries that this CommunitySeries links to.",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        }
        vame_project_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the VAMEProject group in the NWB file."},
                "LatentSpaceSeries": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name of the LatentSpaceSeries."},
                        "description": {"type": "string"},
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
                "MotifSeries": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": motif_entry_schema,
                },
                "CommunitySeries": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": community_entry_schema,
                },
                "pose_estimation_metadata_key": {
                    "type": ["string", "null"],
                    "description": ("Name of a PoseEstimation container already present in the NWB file to link to."),
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        }

        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        metadata_schema["properties"]["Behavior"]["properties"] = {
            "VAMEProjects": {
                "type": "object",
                "properties": {},
                "additionalProperties": vame_project_schema,
            }
        }

        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        vame_project_metadata: dict = dict(name=self._metadata_key)

        if self._latent_vectors_file_path is not None:
            zdims = self._vame_config.get("zdims")
            dims_info = f" ({zdims} dimensions per frame)" if zdims else ""
            vame_project_metadata["LatentSpaceSeries"] = dict(
                name="LatentSpaceSeries",
                description=f"VAME latent-space embeddings{dims_info}.",
            )

        if self._motif_labels_file_paths is not None:
            vame_project_metadata["MotifSeries"] = {
                run_key: dict(
                    name=f"MotifSeries{run_key.capitalize()}",
                    description="VAME behavioral motif labels.",
                    algorithm=run_key,
                )
                for run_key in self._motif_labels_file_paths
            }

        if self._community_labels_file_paths is not None:
            vame_project_metadata["CommunitySeries"] = {
                run_key: dict(
                    name=f"CommunitySeries{run_key.capitalize()}",
                    description="VAME community labels grouping motifs into higher-level behavioral states.",
                    algorithm=run_key,
                    motif_series_key=(
                        run_key if self._motif_labels_file_paths and run_key in self._motif_labels_file_paths else None
                    ),
                )
                for run_key in self._community_labels_file_paths
            }

        metadata["Behavior"]["VAMEProjects"] = {self._metadata_key: vame_project_metadata}

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

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
    ) -> None:
        """Write VAME outputs to an NWBFile as a ``VAMEProject`` container.

        The container name and all series descriptions are taken from
        ``metadata["Behavior"]["VAMEProjects"][metadata_key]``. Call :meth:`get_metadata` to
        inspect the defaults and override specific fields before conversion.

        Parameters
        ----------
        nwbfile : NWBFile
            Target NWB file.
        metadata : dict, optional
            Metadata dictionary. VAME-specific fields live under
            ``metadata["Behavior"]["VAMEProjects"][metadata_key]`` and include:

            - ``"name"`` – name of the ``VAMEProject`` group.
            - ``"LatentSpaceSeries"`` – dict with ``name`` and ``description``.
            - ``"MotifSeries"`` – dict of run_key → ``{name, description, algorithm}``.
            - ``"CommunitySeries"`` – dict of run_key →
              ``{name, description, algorithm, motif_series_key}``.
              ``motif_series_key`` cross-references a key in ``MotifSeries``.
            - ``"pose_estimation_metadata_key"`` – name of a ``PoseEstimation`` container
              already present in the NWB file to soft-link from the ``VAMEProject``.
        stub_test : bool, default False
            If ``True``, only the first 100 frames of each data array are written.
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

        vame_metadata = default_metadata["Behavior"]["VAMEProjects"][self._metadata_key]
        project_name = vame_metadata["name"]

        n_frames = min(100, len(self.get_timestamps())) if stub_test else None

        timestamps = self.get_timestamps()[:n_frames]
        rate = calculate_regular_series_rate(series=timestamps)

        timing_kwargs = {}
        if rate is None:
            timing_kwargs["timestamps"] = timestamps.astype(np.float64)
        else:
            timing_kwargs["rate"] = float(rate)
            timing_kwargs["starting_time"] = timestamps[0]

        # LatentSpaceSeries (optional, shared across algorithm runs)
        latent_series = None
        latent_series_metadata = vame_metadata.get("LatentSpaceSeries")
        if self._latent_vectors_file_path is not None and latent_series_metadata is not None:
            latent_data = np.load(self._latent_vectors_file_path)[:n_frames].astype(np.float32)
            latent_series = LatentSpaceSeries(data=latent_data, **latent_series_metadata, **timing_kwargs)

        # MotifSeries — one per run key
        motif_series_objects = {}
        motif_series_metadata = vame_metadata.get("MotifSeries", {})
        for run_key, file_path in (self._motif_labels_file_paths or {}).items():
            motif_meta = dict(motif_series_metadata.get(run_key, {}))
            motif_data = np.load(file_path)[:n_frames].astype(np.int32)
            motif_kwargs: dict = dict(data=motif_data, **motif_meta, **timing_kwargs)
            if latent_series is not None:
                motif_kwargs["latent_space_series"] = latent_series
            motif_series_objects[run_key] = MotifSeries(**motif_kwargs)

        # CommunitySeries — one per run key, optionally linked to a MotifSeries
        community_series_objects = {}
        community_series_meta = vame_metadata.get("CommunitySeries", {})
        for run_key, file_path in (self._community_labels_file_paths or {}).items():
            community_meta = dict(community_series_meta.get(run_key, {}))
            motif_series_key = community_meta.pop("motif_series_key", None)
            community_data = np.load(file_path)[:n_frames].astype(np.int32)
            community_kwargs: dict = dict(data=community_data, **community_meta, **timing_kwargs)
            linked_motif = motif_series_objects.get(motif_series_key) if motif_series_key else None
            if linked_motif is not None:
                community_kwargs["motif_series"] = linked_motif
            community_series_objects[run_key] = CommunitySeries(**community_kwargs)

        # Optional link to an upstream PoseEstimation container
        pose_estimation = None
        pose_estimation_key = vame_metadata.get("pose_estimation_metadata_key")
        if pose_estimation_key is not None:
            pose_estimations_registry = default_metadata.get("Behavior", {}).get("Pose", {}).get("PoseEstimations", {})
            if pose_estimation_key in pose_estimations_registry:
                pose_container_name = pose_estimations_registry[pose_estimation_key].get("name", pose_estimation_key)
            else:
                pose_container_name = pose_estimation_key
            pose_estimation = self._get_pose_estimation(nwbfile, pose_container_name)

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
