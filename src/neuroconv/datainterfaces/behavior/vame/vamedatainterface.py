"""DataInterface for VAME behavioral segmentation data."""

import json
from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module
from ....utils import DeepDict, calculate_regular_series_rate, load_dict_from_file


class VameInterface(BaseTemporalAlignmentInterface):
    """DataInterface for VAME behavioral segmentation data using the ndx-vame NWB extension.

    EthoML/VAME (Variational Animal Motion Encoding) segments animal behavior into discrete motifs
    by training a variational autoencoder on pose estimation time series. This interface
    writes the per-frame outputs—motif labels, optional latent-space embeddings, and optional
    community labels to NWB using the ``ndx-vame`` extension.

    The NWB container name and all series descriptions are controlled via the metadata dict
    under ``metadata["VAME"][metadata_key]``.

    To store two VAME runs (e.g. k-means and HMM) in the same NWB file, create two
    ``VameInterface`` instances with different ``metadata_key`` values and
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
        source_schema["properties"]["motif_labels_file_path"]["description"] = (
            "Path to the .npy file containing VAME motif labels "
            "(1D int array, one cluster ID per video frame). "
            "Typically named '{n_clusters}_{algorithm}_label_{session}.npy'."
        )
        source_schema["properties"]["latent_vectors_file_path"]["description"] = (
            "Path to the .npy file containing VAME latent-space vectors "
            "(2D float32 array of shape (n_frames, n_latent_dims)). "
            "Typically named 'latent_vectors.npy'. Optional."
        )
        source_schema["properties"]["community_labels_file_path"]["description"] = (
            "Path to the .npy file containing VAME community labels "
            "(1D int array, one community ID per video frame). "
            "Typically named 'cohort_community_label_{session}.npy'. Optional."
        )
        source_schema["properties"]["vame_config_file_path"]["description"] = (
            "Path to the VAME 'config.yaml' project file. "
            "The full configuration is serialized as JSON and stored in the VAMEProject.vame_config field."
        )
        return source_schema

    @validate_call
    def __init__(
        self,
        vame_config_file_path: FilePath,
        motif_labels_file_path: FilePath | None = None,
        latent_vectors_file_path: FilePath | None = None,
        community_labels_file_path: FilePath | None = None,
        sampling_frequency_hz: float | None = None,
        metadata_key: str = "VAMEProject",
        pose_estimation_name: str | None = None,
        verbose: bool = False,
    ):
        """Initialize VameInterface.

        Parameters
        ----------
        vame_config_file_path : FilePath
            Path to the VAME ``config.yaml`` project file. The full configuration
            is serialized as JSON and stored in the ``VAMEProject.vame_config`` field.
        motif_labels_file_path : FilePath, optional
            Path to the .npy file containing VAME motif labels (1D int array, one value per frame).
        latent_vectors_file_path : FilePath, optional
            Path to the .npy file containing VAME latent-space vectors (2D float32 array of
            shape ``(n_frames, n_latent_dims)``). Typically located one level above the algorithm-specific sub-directory.
        community_labels_file_path : FilePath, optional
            Path to the .npy file containing VAME community labels (1D int array, one value
            per frame). Typically located inside a ``community/`` sub-directory of the algorithm directory.
        sampling_frequency_hz : float, optional
            Video acquisition rate in Hz (frames per second). Required when not providing aligned
            timestamps via :meth:`set_aligned_timestamps`.
        metadata_key : str, default "VAMEProject"
            Key used to look up this interface's metadata inside
            ``metadata["VAME"][metadata_key]``. Change this when storing
            results from multiple VAME runs in the same NWB file so each run has a unique
            metadata entry.
        pose_estimation_name : str, optional
            Name of an existing ``PoseEstimation`` container already present in the NWB file.
            When provided, a soft link from the ``VAMEProject`` to that container is added to
            record the upstream pose data used by VAME. Raises ``ValueError`` if the name is
            not found, listing any available ``PoseEstimation`` containers to help.
        verbose : bool, default False
            Controls verbosity of the conversion process.
        """
        import ndx_vame  # noqa: F401 – ensure ndx-vame namespace is registered

        self.vame_config_dict = load_dict_from_file(vame_config_file_path)

        self.motif_labels_file_path = Path(motif_labels_file_path) if motif_labels_file_path else None
        self.latent_vectors_file_path = Path(latent_vectors_file_path) if latent_vectors_file_path else None
        self.community_labels_file_path = Path(community_labels_file_path) if community_labels_file_path else None
        self.sampling_frequency_hz = sampling_frequency_hz
        self.metadata_key = metadata_key
        self.pose_estimation_name = pose_estimation_name

        super().__init__(
            motif_labels_file_path=motif_labels_file_path,
            latent_vectors_file_path=latent_vectors_file_path,
            community_labels_file_path=community_labels_file_path,
            vame_config_file_path=vame_config_file_path,
            verbose=verbose,
        )

    def get_metadata_schema(self) -> dict:
        from ....utils import get_base_schema

        metadata_schema = super().get_metadata_schema()

        # Define the schema for VAME metadata
        motif_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the MotifSeries."},
                "algorithm": {
                    "type": ["string", "null"],
                    "description": "The algorithm used for motif detection.",
                },
            },
            "required": ["name"],
        }
        community_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the CommunitySeries."},
                "algorithm": {
                    "type": ["string", "null"],
                    "description": "The algorithm used for community clustering.",
                },
            },
            "required": ["name"],
        }

        vame_schema = get_base_schema(tag="VAME")
        vame_schema["additionalProperties"] = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the group that holds VAME project data.",
                },
                "MotifSeries": motif_schema,
                "LatentSpaceSeries": {
                    "type": "object",
                    "properties": {"name": {"type": "string", "description": "Name of the LatentSpaceSeries."}},
                    "required": ["name"],
                },
                "CommunitySeries": community_schema,
            },
            "required": ["name"],
            "additionalProperties": False,
        }

        metadata_schema["properties"]["VAME"] = vame_schema

        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        vame_project_metadata: dict = dict(name=self.metadata_key)

        if self.motif_labels_file_path is not None:
            vame_project_metadata["MotifSeries"] = dict(name="MotifSeries", description="VAME behavioral motif labels.")

        if self.latent_vectors_file_path is not None:
            zdims = self.vame_config_dict.get("zdims")
            dims_info = f" ({zdims} dimensions per frame)" if zdims else ""
            vame_project_metadata["LatentSpaceSeries"] = dict(
                name="LatentSpaceSeries",
                description=f"VAME latent-space embeddings{dims_info}.",
            )

        if self.community_labels_file_path is not None:
            vame_project_metadata["CommunitySeries"] = dict(
                name="CommunitySeries",
                description="VAME community labels grouping motifs into higher-level behavioral states.",
            )

        metadata["VAME"] = {self.metadata_key: vame_project_metadata}

        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        if self.sampling_frequency_hz is None:
            raise ValueError(
                "VameInterface cannot generate original timestamps without a sampling_frequency_hz. "
                "Provide sampling_frequency_hz at construction or call set_aligned_timestamps()."
            )
        reference_file = self.motif_labels_file_path or self.latent_vectors_file_path or self.community_labels_file_path
        if reference_file is None:
            raise ValueError(
                "VameInterface cannot generate original timestamps without any data file. "
                "Provide at least one of motif_labels_file_path, latent_vectors_file_path, or "
                "community_labels_file_path, or call set_aligned_timestamps()."
            )
        n_frames = np.load(reference_file).shape[0]
        return np.arange(n_frames) / self.sampling_frequency_hz

    def get_timestamps(self) -> np.ndarray:
        timestamps = self._timestamps if self._timestamps is not None else self.get_original_timestamps()
        return timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = np.asarray(aligned_timestamps)

    def _get_pose_estimation(self, nwbfile: NWBFile):
        pose_estimation_containers = {
            obj.name: obj for obj in nwbfile.objects.values() if type(obj).__name__ == "PoseEstimation"
        }
        if self.pose_estimation_name in pose_estimation_containers:
            return pose_estimation_containers[self.pose_estimation_name]
        if pose_estimation_containers:
            raise ValueError(
                f"No PoseEstimation container named '{self.pose_estimation_name}' was found in the NWB file. "
                f"Available PoseEstimation containers: {list(pose_estimation_containers)}."
            )
        raise ValueError(
            f"No PoseEstimation container named '{self.pose_estimation_name}' was found in the NWB file. "
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
        ``metadata["VAME"][metadata_key]``. Call :meth:`get_metadata` to
        inspect the defaults and override specific fields before conversion.

        Parameters
        ----------
        nwbfile : NWBFile
            Target NWB file.
        metadata : dict, optional
            Metadata dictionary. VAME-specific fields live under
            ``metadata["VAME"][metadata_key]`` and include:

            - ``"name"`` – name of the ``VAMEProject`` group in the NWB file.
            - ``"MotifSeries"`` – dict with ``name``, ``description``, ``algorithm``.
            - ``"LatentSpaceSeries"`` – dict with ``name`` and ``description``.
              Omit the key entirely to suppress writing even when a file was provided.
            - ``"CommunitySeries"`` – dict with ``name``, ``description``, ``algorithm``.
              Same suppression rule as ``LatentSpaceSeries``.
        stub_test : bool, default: False
            If ``True``, only the first 100 frames of each data array are written. Useful
            for fast, lightweight testing without loading full datasets.
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

        vame_metadata = default_metadata["VAME"][self.metadata_key]
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

        # LatentSpaceSeries (optional)
        latent_series = None
        latent_series_metadata = vame_metadata.get("LatentSpaceSeries")
        if self.latent_vectors_file_path is not None and latent_series_metadata is not None:
            latent_data = np.load(self.latent_vectors_file_path)[:n_frames].astype(np.float32)
            latent_series = LatentSpaceSeries(
                data=latent_data,
                **latent_series_metadata,
                **timing_kwargs,
            )

        # MotifSeries (optional)
        motif_series = None
        motif_metadata = vame_metadata.get("MotifSeries")
        if self.motif_labels_file_path is not None and motif_metadata is not None:
            motif_data = np.load(self.motif_labels_file_path)[:n_frames].astype(np.int32)
            motif_kwargs: dict = dict(data=motif_data, **motif_metadata, **timing_kwargs)
            if latent_series is not None:
                motif_kwargs["latent_space_series"] = latent_series
            motif_series = MotifSeries(**motif_kwargs)

        # CommunitySeries (optional)
        community_series = None
        community_metadata = vame_metadata.get("CommunitySeries")
        if self.community_labels_file_path is not None and community_metadata is not None:
            community_data = np.load(self.community_labels_file_path)[:n_frames].astype(np.int32)
            community_kwargs: dict = dict(
                data=community_data,
                **community_metadata,
                **timing_kwargs,
                motif_series=motif_series,
            )
            community_series = CommunitySeries(**community_kwargs)

        # Optional link to an upstream PoseEstimation container
        pose_estimation = None
        behavior_module = get_module(nwbfile, name="behavior", description="Processed behavioral data.")
        if self.pose_estimation_name is not None:
            pose_estimation = self._get_pose_estimation(nwbfile)

        vame_project = VAMEProject(
            name=project_name,
            pose_estimation=pose_estimation,
            latent_space_series=latent_series,
            motif_series=motif_series,
            community_series=community_series,
            vame_config=json.dumps(self.vame_config_dict),
        )

        behavior_module.add(vame_project)
