"""DataInterface for keypoint-MoSeq behavioral segmentation output."""

import copy
import warnings
from typing import Literal

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.base import TimeSeries
from pynwb.behavior import CompassDirection, Position, SpatialSeries

from ..basebehavioralsegmentationinterface import BaseBehavioralSegmentationInterface
from ....tools import get_module
from ....utils import DeepDict, calculate_regular_series_rate


class MoseqKeyPointsInterface(BaseBehavioralSegmentationInterface):
    """DataInterface for keypoint-MoSeq output (``results.h5``).

    Writes one recording of a ``results.h5``: the syllables as an ``ndx-ethogram`` ``EthogramBouts``
    table with its ``Ethogram`` catalogue, the centroid as a ``SpatialSeries`` in ``Position``, the
    heading as a ``SpatialSeries`` in ``CompassDirection``, and the latent-state trajectory as a
    ``TimeSeries``.

    Notes
    -----
    - **There is no time base in the source.** ``results.h5`` carries neither timestamps nor a frame
      rate; the rate is a property of the recording the keypoints came from and lives only in the
      keypoint-MoSeq project ``config.yml``, where it was typed by the user rather than measured, so
      ``sampling_frequency_hz`` has to be supplied.
    - **The first frames of every recording are padding.** The autoregressive model has no state for
      the first ``nlags`` frames (3 by default), so keypoint-MoSeq fills them by repeating the first
      real syllable. Those frames are written as they are, which makes the first bout start earlier
      than the first true syllable; the padding repeats a real value, so it cannot be detected from
      the file.
    - **Syllable ids carry no meaning outside the run that produced them.** They are renumbered at the
      end of a fit by how often each state is entered, and only the states the fit actually entered
      get an id, so the ids are neither stable across runs nor contiguous. The catalogue therefore
      enumerates the ids present in this recording rather than the configured state space, which
      ``results.h5`` does not record.
    - **A recording name maps to no session or subject.** It comes from the input filename, so it
      carries a DeepLabCut scorer suffix when the pose came from DeepLabCut and is a bare name
      otherwise. Nothing in the file relates it to a session, so the links to an upstream
      ``PoseEstimation`` and to a behavioral video are supplied through metadata and never parsed
      from the name.
    """

    display_name = "keypoint-MoSeq"
    keywords = ("keypoint-MoSeq", "MoSeq", "behavioral syllables", "pose segmentation")
    associated_suffixes = (".h5",)
    info = "Interface for adding data from keypoint-MoSeq (Motion Sequencing on pose keypoints)."

    source_software = "keypoint-MoSeq"
    behavior_definition = (
        "keypoint-MoSeq unsupervised syllable; the id is specific to the run that produced it and carries no meaning "
        "outside it."
    )

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"][
            "description"
        ] = "Path to the keypoint-MoSeq 'results.h5', which holds one group per recording."
        source_schema["properties"]["recording_name"]["description"] = (
            "Name of the recording group to write. Optional when the file holds a single recording. "
            "Call get_available_recordings() to list them."
        )
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        sampling_frequency_hz: float,
        recording_name: str | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize MoseqKeyPointsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the keypoint-MoSeq ``results.h5``.
        sampling_frequency_hz : float
            Frame rate of the video the keypoints came from, in Hz. Required because keypoint-MoSeq
            records no time base of its own; take it from that video or from the ``fps`` field of the
            keypoint-MoSeq project's ``config.yml``.
        recording_name : str, optional
            Name of the recording group to write. Recordings in one file are separate recordings with
            their own frame counts, so one interface writes one of them. Optional when the file holds
            a single recording; required otherwise. Use :meth:`get_available_recordings` to list them.
        metadata_key : str, optional
            Key of this interface's entries in the ``metadata["Behavior"]["MoseqKeyPoints"]`` registries, in
            ``metadata["Behavior"]["Ethograms"]`` and ``metadata["Behavior"]["EthogramBouts"]``, and of its
            object in ``temporal_alignment``. Defaults to ``"keypoint_moseq"``. Change it when writing two
            recordings into one NWB file so their entries do not collide.
        verbose : bool, default False
            Controls verbosity of the conversion process.
        """
        available_recordings = self.get_available_recordings(file_path)
        if recording_name is None:
            if len(available_recordings) != 1:
                raise ValueError(
                    f"'{file_path}' holds {len(available_recordings)} recordings, so recording_name is required. "
                    f"Available recordings: {available_recordings}."
                )
            recording_name = available_recordings[0]
        elif recording_name not in available_recordings:
            raise ValueError(
                f"No recording named '{recording_name}' was found in '{file_path}'. "
                f"Available recordings: {available_recordings}."
            )

        self._recording_name = recording_name
        self.metadata_key = metadata_key or "keypoint_moseq"
        self._sampling_frequency_hz = sampling_frequency_hz

        super().__init__(file_path=file_path, recording_name=recording_name, verbose=verbose)

    @staticmethod
    def get_available_recordings(file_path: FilePath) -> list[str]:
        """Return the names of the recordings held in a keypoint-MoSeq ``results.h5``.

        Parameters
        ----------
        file_path : FilePath
            Path to the keypoint-MoSeq ``results.h5``.

        Returns
        -------
        list of str
            One name per recording group, as keypoint-MoSeq derived it from the input filename.
        """
        import h5py

        with h5py.File(file_path, "r") as file:
            return list(file.keys())

    def _read_dataset(self, dataset_name: str) -> np.ndarray:
        """Return one dataset of this interface's recording group."""
        import h5py

        with h5py.File(self.source_data["file_path"], "r") as file:
            return file[self._recording_name][dataset_name][:]

    def _get_labels(self) -> np.ndarray:
        return self._read_dataset("syllable")

    def _get_native_times(self) -> np.ndarray:
        return np.arange(len(self._get_labels())) / self._sampling_frequency_hz

    def _get_source(self, nwbfile: NWBFile, metadata: dict):
        # The bouts point back at the latent trajectory they came from when it is in the file. With
        # data_to_write="ethogram" it is not, and there is nothing to link to.
        if "behavior" not in nwbfile.processing:
            return None
        latent_state_name = metadata["Behavior"]["MoseqKeyPoints"]["LatentStates"][self.metadata_key]["name"]
        return nwbfile.processing["behavior"].data_interfaces.get(latent_state_name)

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()

        # Deprecated: the two links moved to the bouts entry in Behavior/EthogramBouts, as
        # source_pose_metadata_key and source_video_metadata_key. Kept until v0.13.0 so metadata written for
        # earlier versions still validates.
        recording_entry_schema = {
            "type": "object",
            "properties": {
                "pose_estimation_metadata_key": {
                    "type": ["string", "null"],
                    "description": "Key of a PoseEstimation entry (in Pose/PoseEstimations) the bouts link to.",
                },
                "video_metadata_key": {
                    "type": ["string", "null"],
                    "description": "Key of a video entry (in Behavior/InternalVideos or Behavior/ExternalVideos) "
                    "whose ImageSeries the bouts link to via source_video.",
                },
            },
            "additionalProperties": False,
        }
        centroid_entry_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the centroid SpatialSeries."},
                "description": {"type": "string"},
                "unit": {"type": "string"},
                "reference_frame": {"type": "string"},
                "container_name": {
                    "type": "string",
                    "description": "Name of the Position container the SpatialSeries is written into.",
                },
            },
            "required": ["name", "container_name"],
            "additionalProperties": False,
        }
        heading_entry_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the heading SpatialSeries."},
                "description": {"type": "string"},
                "unit": {"type": "string"},
                "reference_frame": {"type": "string"},
                "container_name": {
                    "type": "string",
                    "description": "Name of the CompassDirection container the SpatialSeries is written into.",
                },
            },
            "required": ["name", "container_name"],
            "additionalProperties": False,
        }
        latent_state_entry_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the latent-state TimeSeries."},
                "description": {"type": "string"},
                "unit": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        }
        metadata_schema["properties"]["Behavior"]["properties"]["MoseqKeyPoints"] = {
            "type": "object",
            "properties": {
                "Recordings": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": recording_entry_schema,
                },
                "Centroids": {"type": "object", "properties": {}, "additionalProperties": centroid_entry_schema},
                "Headings": {"type": "object", "properties": {}, "additionalProperties": heading_entry_schema},
                "LatentStates": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": latent_state_entry_schema,
                },
            },
            "additionalProperties": False,
        }

        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        latent_dimension = self._read_dataset("latent_state").shape[1]
        recording = self._recording_name

        # The series live in flat, addressable registries under Behavior/MoseqKeyPoints, one per
        # type, following the unified metadata pattern.
        metadata["Behavior"]["MoseqKeyPoints"] = {
            "Centroids": {
                self.metadata_key: dict(
                    name="MoseqKeyPointsCentroid",
                    description=(
                        f"Centroid of the animal for recording '{recording}', as estimated by keypoint-MoSeq in the "
                        "coordinate space of the pose keypoints it was given."
                    ),
                    container_name="Position",
                )
            },
            "Headings": {
                self.metadata_key: dict(
                    name="MoseqKeyPointsHeading",
                    description=(f"Heading of the animal for recording '{recording}', as estimated by keypoint-MoSeq."),
                    unit="radians",
                    container_name="CompassDirection",
                )
            },
            "LatentStates": {
                self.metadata_key: dict(
                    name="MoseqKeyPointsLatentState",
                    description=(
                        f"keypoint-MoSeq latent-state trajectory for recording '{recording}' "
                        f"({latent_dimension} dimensions per frame), the model's own description of pose."
                    ),
                    unit="a.u.",
                )
            },
        }

        metadata["Behavior"]["Ethograms"][self.metadata_key] = dict(
            name="MoseqKeyPointsEthogram",
            description=(
                "keypoint-MoSeq syllable catalogue (coding scheme): one row per syllable id present in this recording."
            ),
        )
        # The links to the pose and the video (source_pose_metadata_key, source_video_metadata_key) are absent
        # because results.h5 evidences neither.
        metadata["Behavior"]["EthogramBouts"][self.metadata_key] = dict(
            name="MoseqKeyPointsEthogramBouts",
            description=(
                f"keypoint-MoSeq syllables for recording '{recording}' as run-length-encoded bouts. The first frames "
                "of the recording are model padding repeated from the first real syllable, so the first bout starts "
                "earlier than the first syllable the model assigned."
            ),
            labeling_method="automated",
            ethogram_metadata_key=self.metadata_key,
        )

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        data_to_write: Literal["algorithm_output", "ethogram", "both"] = "both",
    ) -> None:
        """Write one keypoint-MoSeq recording to an NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            Target NWB file.
        metadata : dict, optional
            Metadata dictionary. Defaults to ``get_metadata()``. The series are described by flat registries
            under ``metadata["Behavior"]["MoseqKeyPoints"]``, each keyed by ``metadata_key``:

            - ``"Centroids"`` – ``{name, description, unit, reference_frame, container_name}`` for the
              centroid ``SpatialSeries`` and the ``Position`` container holding it.
            - ``"Headings"`` – the same fields for the heading ``SpatialSeries`` and its
              ``CompassDirection`` container.
            - ``"LatentStates"`` – ``{name, description, unit}`` for the latent-state ``TimeSeries``.

            The bouts table is described by ``metadata["Behavior"]["EthogramBouts"][metadata_key]``, whose
            ``ethogram_metadata_key`` names the catalogue's entry in ``metadata["Behavior"]["Ethograms"]``. Its
            optional ``source_pose_metadata_key`` and ``source_video_metadata_key`` name an entry of
            ``metadata["Pose"]["PoseEstimations"]`` and of ``metadata["Behavior"]["InternalVideos"]`` or
            ``["ExternalVideos"]``, whose object must already be in the file.
        data_to_write : {"algorithm_output", "ethogram", "both"}, default "both"
            Which of the two outputs to write. ``"algorithm_output"`` writes only the per-frame arrays
            keypoint-MoSeq produced: the centroid, the heading and the latent-state trajectory.
            ``"ethogram"`` writes only the derived ``ndx-ethogram`` products, and since the
            latent-state series is then absent from the file the bouts' ``source`` back-link to it is
            dropped; the ``source_pose`` and ``source_video`` links are external references and are
            kept. ``"both"`` (the default) writes both.
        """
        metadata = self._migrate_deprecated_metadata(metadata) if metadata is not None else self.get_metadata()
        moseq_metadata = metadata["Behavior"]["MoseqKeyPoints"]

        if data_to_write in ("algorithm_output", "both"):
            # Every series shares the one clock of the syllables, the frames as aligned.
            timestamps = self.temporal_alignment[self.metadata_key].get_times()
            rate = calculate_regular_series_rate(series=timestamps)
            if rate:
                timing_kwargs = dict(rate=rate, starting_time=float(timestamps[0]))
            else:
                timing_kwargs = dict(timestamps=timestamps)

            behavior_module = get_module(nwbfile, name="behavior", description="processed behavioral data")

            # keypoint-MoSeq expresses the centroid in whatever coordinate space the pose it was given used,
            # image pixels for 2D DeepLabCut output and the triangulation's own space for 3D, and results.h5
            # records neither the unit nor the frame. SpatialSeries requires both, so they are filled here
            # rather than reported by get_metadata().
            placeholder_reference_frame = (
                "PLACEHOLDER: keypoint-MoSeq does not record the coordinate frame of the pose it was given."
            )

            # The centroid is (T, 2) for 2D pose and (T, 3) for 3D, so the width is read off the array.
            centroid_metadata = dict(moseq_metadata["Centroids"][self.metadata_key])
            position_container_name = centroid_metadata.pop("container_name")
            centroid_series = SpatialSeries(
                data=self._read_dataset("centroid"),
                unit=centroid_metadata.pop("unit", "unknown"),
                reference_frame=centroid_metadata.pop("reference_frame", placeholder_reference_frame),
                **centroid_metadata,
                **timing_kwargs,
            )
            behavior_module.add(Position(name=position_container_name, spatial_series=centroid_series))

            heading_metadata = dict(moseq_metadata["Headings"][self.metadata_key])
            compass_container_name = heading_metadata.pop("container_name")
            heading_series = SpatialSeries(
                data=self._read_dataset("heading"),
                reference_frame=heading_metadata.pop("reference_frame", placeholder_reference_frame),
                **heading_metadata,
                **timing_kwargs,
            )
            behavior_module.add(CompassDirection(name=compass_container_name, spatial_series=heading_series))

            latent_state_metadata = dict(moseq_metadata["LatentStates"][self.metadata_key])
            behavior_module.add(
                TimeSeries(data=self._read_dataset("latent_state"), **latent_state_metadata, **timing_kwargs)
            )

        # The syllables are the curated layer and the only one. Run-length encoding is exactly invertible
        # given the timestamps, so the bout table loses nothing about the labels, and the material a faithful
        # keypoint-MoSeq container would hold (kappa, num_states, the checkpoint) is not in results.h5 at all.
        if data_to_write in ("ethogram", "both"):
            super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    def _migrate_deprecated_metadata(self, metadata: dict) -> dict:
        """Move the metadata of versions before v0.11.0 to where this version reads it, with a ``FutureWarning``.

        Before v0.11.0 the catalogue and the bouts were described by one ``Behavior/Ethograms`` entry holding an
        ``Ethogram`` and an ``EthogramBouts`` key, and the links to the pose and the video by a
        ``Behavior/MoseqKeyPoints/Recordings`` entry. Returns a copy; the caller's metadata is left as it is.
        """
        metadata = copy.deepcopy(metadata)
        behavior_metadata = metadata["Behavior"]
        ethogram_entry = behavior_metadata.get("Ethograms", {}).get(self.metadata_key, {})
        recording_entry = behavior_metadata.get("MoseqKeyPoints", {}).get("Recordings", {}).pop(self.metadata_key, None)
        if "Ethogram" not in ethogram_entry and "EthogramBouts" not in ethogram_entry and recording_entry is None:
            return metadata

        bouts_entry = behavior_metadata.setdefault("EthogramBouts", {}).setdefault(
            self.metadata_key, dict(ethogram_metadata_key=self.metadata_key)
        )
        if "Ethogram" in ethogram_entry or "EthogramBouts" in ethogram_entry:
            warnings.warn(
                f"The 'Ethogram' and 'EthogramBouts' keys of metadata['Behavior']['Ethograms']['{self.metadata_key}'] "
                "are deprecated and will be removed in v0.13.0. Give the catalogue's name and description in "
                f"metadata['Behavior']['Ethograms']['{self.metadata_key}'] itself, and the bouts' in "
                f"metadata['Behavior']['EthogramBouts']['{self.metadata_key}'].",
                FutureWarning,
                stacklevel=3,
            )
            ethogram_entry.update(ethogram_entry.pop("Ethogram", {}))
            bouts_entry.update(ethogram_entry.pop("EthogramBouts", {}))

        if recording_entry is not None:
            warnings.warn(
                f"metadata['Behavior']['MoseqKeyPoints']['Recordings'] is deprecated and will be removed in v0.13.0. "
                f"Give the links in metadata['Behavior']['EthogramBouts']['{self.metadata_key}'] as "
                "'source_pose_metadata_key' and 'source_video_metadata_key'.",
                FutureWarning,
                stacklevel=3,
            )
            links = dict(
                source_pose_metadata_key=recording_entry.get("pose_estimation_metadata_key"),
                source_video_metadata_key=recording_entry.get("video_metadata_key"),
            )
            for link_name, old_value in links.items():
                if old_value is None:
                    continue
                new_value = bouts_entry.get(link_name)
                if new_value is not None and new_value != old_value:
                    raise ValueError(
                        f"metadata['Behavior']['MoseqKeyPoints']['Recordings']['{self.metadata_key}'] links to "
                        f"'{old_value}' while metadata['Behavior']['EthogramBouts']['{self.metadata_key}']"
                        f"['{link_name}'] is '{new_value}'. Give the link in the bouts entry only."
                    )
                bouts_entry[link_name] = old_value

        return metadata
