"""DataInterface for keypoint-MoSeq behavioral segmentation output."""

from typing import Literal

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.base import TimeSeries
from pynwb.behavior import CompassDirection, Position, SpatialSeries

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module
from ....utils import DeepDict, calculate_regular_series_rate

# keypoint-MoSeq expresses the centroid in whatever coordinate space the pose it was given used
# (image pixels for 2D DeepLabCut output, the triangulation's own space for 3D), and results.h5
# records neither the unit nor the frame. Both are required by SpatialSeries, so they are filled here
# rather than reported by get_metadata().
_CENTROID_UNIT_PLACEHOLDER = "unknown"
_REFERENCE_FRAME_PLACEHOLDER = (
    "PLACEHOLDER: keypoint-MoSeq does not record the coordinate frame of the pose it was given."
)


def _get_container_by_name(nwbfile: NWBFile, name: str, type_name: str):
    """Return the container of type ``type_name`` named ``name``, raising if it is not in the file."""
    containers = {obj.name: obj for obj in nwbfile.all_children() if type(obj).__name__ == type_name}
    if name in containers:
        return containers[name]
    if containers:
        raise ValueError(
            f"No {type_name} named '{name}' was found in the NWB file. Available {type_name}s: {list(containers)}."
        )
    raise ValueError(
        f"No {type_name} named '{name}' was found in the NWB file. No {type_name} objects exist in the file, "
        "so ensure the interface that writes it runs before MoseqKeyPointsInterface."
    )


class MoseqKeyPointsInterface(BaseTemporalAlignmentInterface):
    """DataInterface for keypoint-MoSeq output (``results.h5``).

    keypoint-MoSeq fits a switching linear dynamical system to pose keypoints and labels every frame
    with a syllable, a short recurring unit of movement. Its ``results.h5`` holds one group per
    recording, each with exactly four datasets: ``syllable``, ``latent_state``, ``centroid`` and
    ``heading``.

    This interface writes one recording. The syllable sequence becomes a curated ``ndx-ethogram``
    product (an ``EthogramBouts`` table of run-length-encoded bouts plus its ``Ethogram`` catalogue),
    and the three continuous per-frame arrays become core NWB objects: the centroid a
    ``SpatialSeries`` in ``Position``, the heading a ``SpatialSeries`` in ``CompassDirection``, and
    the latent trajectory a ``TimeSeries``.

    Notes
    -----
    - **There is no time base in the source.** ``results.h5`` carries neither timestamps nor a frame
      rate; the rate is a property of the recording the keypoints came from and lives only in the
      keypoint-MoSeq project ``config.yml``, where it was typed by the user rather than measured. So
      either pass ``sampling_frequency_hz`` or call
      :meth:`~.basetemporalalignmentinterface.BaseTemporalAlignmentInterface.set_aligned_timestamps`.
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

    _timestamps = None

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
        recording_name: str | None = None,
        sampling_frequency_hz: float | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize MoseqKeyPointsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the keypoint-MoSeq ``results.h5``.
        recording_name : str, optional
            Name of the recording group to write. Recordings in one file are separate recordings with
            their own frame counts, so one interface writes one of them. Optional when the file holds
            a single recording; required otherwise. Use :meth:`get_available_recordings` to list them.
        sampling_frequency_hz : float, optional
            Frame rate of the video the keypoints came from, in Hz. Required unless aligned timestamps
            are supplied with ``set_aligned_timestamps``, because keypoint-MoSeq records no time base.
        metadata_key : str, optional
            Key of this interface's entries in the ``metadata["Behavior"]["MoseqKeyPoints"]``
            registries and in ``metadata["Behavior"]["Ethograms"]``. Defaults to ``"keypoint_moseq"``.
            Change it when writing two recordings into one NWB file so their entries do not collide.
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

    def _get_number_of_frames(self) -> int:
        import h5py

        with h5py.File(self.source_data["file_path"], "r") as file:
            return file[self._recording_name]["syllable"].shape[0]

    def get_original_timestamps(self) -> np.ndarray:
        if self._sampling_frequency_hz is None:
            raise ValueError(
                "MoseqKeyPointsInterface cannot generate timestamps because keypoint-MoSeq carries no time base: "
                "results.h5 holds neither timestamps nor a frame rate. Pass sampling_frequency_hz at construction, "
                "or call set_aligned_timestamps() with the timestamps of the video the keypoints came from."
            )
        return np.arange(self._get_number_of_frames()) / self._sampling_frequency_hz

    def get_timestamps(self) -> np.ndarray:
        return self._timestamps if self._timestamps is not None else self.get_original_timestamps()

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = np.asarray(aligned_timestamps)

    def get_metadata_schema(self) -> dict:
        from ....utils import get_base_schema

        metadata_schema = super().get_metadata_schema()

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
        named_entry_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        }
        # The curated ndx-ethogram entry lives in the shared top-level Behavior/Ethograms registry
        # rather than under Behavior/MoseqKeyPoints, because the curated layer is producer-agnostic:
        # VAME populates the same registry.
        ethogram_entry_schema = {
            "type": "object",
            "properties": {"EthogramBouts": named_entry_schema, "Ethogram": named_entry_schema},
            "additionalProperties": False,
        }

        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        # Leave the Behavior node open so sibling registries written by other interfaces (a video
        # interface's Behavior/InternalVideos, say) survive validation in a converter. The
        # MoseqKeyPoints and Ethograms sub-schemas stay strict.
        metadata_schema["properties"]["Behavior"]["additionalProperties"] = True
        metadata_schema["properties"]["Behavior"]["properties"] = {
            "MoseqKeyPoints": {
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
            },
            "Ethograms": {"type": "object", "properties": {}, "additionalProperties": ethogram_entry_schema},
        }

        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        latent_dimension = self._read_dataset("latent_state").shape[1]
        recording = self._recording_name

        # The series live in flat, addressable registries under Behavior/MoseqKeyPoints, one per
        # type, following the unified metadata pattern. Behavior/MoseqKeyPoints/Recordings holds the
        # optional links to an upstream PoseEstimation and video; it is absent here because the
        # source evidences neither, and a user who wants those links adds the entry.
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

        # Curated ndx-ethogram products go in the shared, producer-agnostic Behavior/Ethograms
        # registry, the same one VameInterface writes to.
        metadata["Behavior"]["Ethograms"] = {
            self.metadata_key: dict(
                EthogramBouts=dict(
                    name="MoseqKeyPointsEthogramBouts",
                    description=(
                        f"keypoint-MoSeq syllables for recording '{recording}' as run-length-encoded bouts. The "
                        "first frames of the recording are model padding repeated from the first real syllable, so "
                        "the first bout starts earlier than the first syllable the model assigned."
                    ),
                ),
                Ethogram=dict(
                    name="MoseqKeyPointsEthogram",
                    description=(
                        "keypoint-MoSeq syllable catalogue (coding scheme): one row per syllable id present in "
                        "this recording."
                    ),
                ),
            )
        }

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
            Metadata dictionary. This interface's fields live in flat registries under
            ``metadata["Behavior"]["MoseqKeyPoints"]``, each keyed by ``metadata_key``:

            - ``"Centroids"`` – ``{name, description, unit, reference_frame, container_name}`` for the
              centroid ``SpatialSeries`` and the ``Position`` container holding it.
            - ``"Headings"`` – the same fields for the heading ``SpatialSeries`` and its
              ``CompassDirection`` container.
            - ``"LatentStates"`` – ``{name, description, unit}`` for the latent-state ``TimeSeries``.
            - ``"Recordings"`` – ``{pose_estimation_metadata_key, video_metadata_key}``, the optional
              links the curated bouts carry back to the pose and the video they were derived from.
              Both are registry addresses, resolved through ``metadata["Pose"]["PoseEstimations"]``
              and ``metadata["Behavior"]["InternalVideos"]`` / ``["ExternalVideos"]``, so the object
              named there must already be in the file.

            The curated ``EthogramBouts`` and ``Ethogram`` names and descriptions live in the shared
            ``metadata["Behavior"]["Ethograms"][metadata_key]`` registry.
        data_to_write : {"algorithm_output", "ethogram", "both"}, default "both"
            Which of the two outputs to write. ``"algorithm_output"`` writes only the per-frame arrays
            keypoint-MoSeq produced: the centroid, the heading and the latent-state trajectory.
            ``"ethogram"`` writes only the derived ``ndx-ethogram`` products, and since the
            latent-state series is then absent from the file the bouts' ``source`` back-link to it is
            dropped; the ``source_pose`` and ``source_video`` links are external references and are
            kept. ``"both"`` (the default) writes both.
        """
        from ....tools.pose_estimation import _build_ethogram_from_labels

        write_algorithm_output = data_to_write in ("algorithm_output", "both")
        write_curated = data_to_write in ("ethogram", "both")

        default_metadata = DeepDict(self.get_metadata())
        if metadata is not None:
            default_metadata.deep_update(metadata)
        moseq_metadata = default_metadata["Behavior"]["MoseqKeyPoints"]

        timestamps = self.get_timestamps()
        rate = calculate_regular_series_rate(series=timestamps)
        if rate is None:
            timing_kwargs = dict(timestamps=timestamps.astype(np.float64))
            frame_period = float(np.median(np.diff(timestamps)))
        else:
            timing_kwargs = dict(rate=float(rate), starting_time=float(timestamps[0]))
            frame_period = 1.0 / float(rate)

        behavior_module = get_module(nwbfile, name="behavior", description="processed behavioral data")

        latent_state_series = None
        if write_algorithm_output:
            # The centroid is (T, 2) for 2D pose and (T, 3) for 3D, so the width is read off the array.
            centroid_metadata = dict(moseq_metadata["Centroids"][self.metadata_key])
            position_container_name = centroid_metadata.pop("container_name")
            centroid_series = SpatialSeries(
                data=self._read_dataset("centroid"),
                unit=centroid_metadata.pop("unit", _CENTROID_UNIT_PLACEHOLDER),
                reference_frame=centroid_metadata.pop("reference_frame", _REFERENCE_FRAME_PLACEHOLDER),
                **centroid_metadata,
                **timing_kwargs,
            )
            behavior_module.add(Position(name=position_container_name, spatial_series=centroid_series))

            heading_metadata = dict(moseq_metadata["Headings"][self.metadata_key])
            compass_container_name = heading_metadata.pop("container_name")
            heading_series = SpatialSeries(
                data=self._read_dataset("heading"),
                reference_frame=heading_metadata.pop("reference_frame", _REFERENCE_FRAME_PLACEHOLDER),
                **heading_metadata,
                **timing_kwargs,
            )
            behavior_module.add(CompassDirection(name=compass_container_name, spatial_series=heading_series))

            latent_state_metadata = dict(moseq_metadata["LatentStates"][self.metadata_key])
            latent_state_series = TimeSeries(
                data=self._read_dataset("latent_state"), **latent_state_metadata, **timing_kwargs
            )
            behavior_module.add(latent_state_series)

        if not write_curated:
            return

        # Optional links to the upstream pose and video, resolved strictly through the metadata
        # registries. The recording name carries no mapping to a session, so nothing is derived from
        # it; a link exists only where the user addressed one.
        recording_metadata = moseq_metadata.get("Recordings", {}).get(self.metadata_key, {})
        source_pose = None
        pose_estimation_key = recording_metadata.get("pose_estimation_metadata_key")
        if pose_estimation_key is not None:
            pose_estimations_registry = default_metadata.get("Pose", {}).get("PoseEstimations", {})
            if pose_estimation_key not in pose_estimations_registry:
                raise ValueError(
                    f"pose_estimation_metadata_key '{pose_estimation_key}' was not found in "
                    f"metadata['Pose']['PoseEstimations']. Available keys: {list(pose_estimations_registry)}."
                )
            pose_container_name = pose_estimations_registry[pose_estimation_key]["name"]
            source_pose = _get_container_by_name(nwbfile, pose_container_name, "PoseEstimation")

        source_video = None
        video_key = recording_metadata.get("video_metadata_key")
        if video_key is not None:
            behavior_metadata = default_metadata.get("Behavior", {})
            videos_registry = {
                **behavior_metadata.get("InternalVideos", {}),
                **behavior_metadata.get("ExternalVideos", {}),
            }
            if video_key not in videos_registry:
                raise ValueError(
                    f"video_metadata_key '{video_key}' was not found in metadata['Behavior']['InternalVideos'] "
                    f"or metadata['Behavior']['ExternalVideos']. Available keys: {list(videos_registry)}."
                )
            source_video = _get_container_by_name(nwbfile, videos_registry[video_key]["name"], "ImageSeries")

        # The syllables are the curated layer and the only one. Run-length encoding is exactly
        # invertible given the timestamps, so the bout table loses nothing about the labels, and the
        # material a faithful keypoint-MoSeq container would hold (kappa, num_states, the checkpoint)
        # is not in results.h5 at all. The bouts point back at the latent trajectory they came from,
        # when it was written; with data_to_write="ethogram" there is no object to link to.
        ethogram_metadata = default_metadata["Behavior"]["Ethograms"][self.metadata_key]
        bouts, catalogue = _build_ethogram_from_labels(
            labels=self._read_dataset("syllable"),
            timestamps=timestamps,
            frame_period=frame_period,
            bouts_name=ethogram_metadata["EthogramBouts"]["name"],
            bouts_description=ethogram_metadata["EthogramBouts"]["description"],
            labeling_method="automated",
            source_software="keypoint-MoSeq",
            source=latent_state_series,
            source_pose=source_pose,
            source_video=source_video,
            catalogue_name=ethogram_metadata["Ethogram"]["name"],
            catalogue_description=ethogram_metadata["Ethogram"]["description"],
            class_definition=(
                "keypoint-MoSeq unsupervised syllable; the id is specific to the run that produced it and carries "
                "no meaning outside it."
            ),
            exclusive=True,  # keypoint-MoSeq syllables are a single-label partition.
        )
        behavior_module.add(catalogue)
        behavior_module.add(bouts)
