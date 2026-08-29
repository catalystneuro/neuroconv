import warnings
from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from ._sleap_legacy import _SLEAPLegacyInterface
from .sleap_utils import extract_timestamps
from ..baseposeestimationinterface import BasePoseEstimationInterface
from ....utils import DeepDict


class SLEAPInterface(BasePoseEstimationInterface):
    """Data interface for SLEAP datasets."""

    display_name = "SLEAP"
    keywords = ("pose estimation", "tracking", "video")
    associated_suffixes = (".slp", ".mp4")
    info = "Interface for SLEAP pose estimation datasets."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .slp file (the output of sleap)"
        source_schema["properties"]["video_file_path"][
            "description"
        ] = "Path of the video for extracting timestamps (optional)."
        return source_schema

    @staticmethod
    def get_available_tracks(file_path: FilePath) -> list[str]:
        """Return the names of the tracks that carry at least one instance, in the file's own order.

        ``Labels.tracks`` records the identities the tracking run created rather than the ones that
        survived it, so a file can declare a track that no frame holds an instance for. Those are not
        offered, since selecting one has nothing to write. Reading the frames costs nothing here, as
        ``load_slp`` has already read them.

        A file holding several recordings is answered as a whole: a track offered here can still be
        empty in one of them, which is caught when the recording is selected.
        """
        from sleap_io import load_slp

        labels = load_slp(Path(file_path))
        populated_track_names = {
            instance.track.name
            for labeled_frame in labels.labeled_frames
            for instance in labeled_frame.instances
            if instance.track is not None
        }
        return [track.name for track in labels.tracks if track.name in populated_track_names]

    @staticmethod
    def _get_declared_track_names(file_path: FilePath) -> list[str]:
        """Every track the file declares, populated or not, for the constructor's error message."""
        from sleap_io import load_slp

        return [track.name for track in load_slp(Path(file_path)).tracks]

    @staticmethod
    def get_available_videos(file_path: FilePath) -> list[str]:
        """Return the video names in a .slp file, one per recording labeled in it.

        The stems of the paths the file stores, since those are absolute paths from the machine that did
        the labeling and rarely resolve on the machine doing the conversion.
        """
        from sleap_io import load_slp

        return [Path(video.filename).stem for video in load_slp(Path(file_path)).videos]

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        video_file_path: FilePath | None = None,
        verbose: bool = False,
        frames_per_second: float | None = None,
        track_name: str | None = None,
        video_name: str | None = None,
        metadata_key: str | None = None,
    ):
        """
        Interface for writing sleap .slp files to nwb using the sleap-io library.

        Parameters
        ----------
        file_path : FilePath
            Path to the .slp file (the output of sleap)
        verbose : bool, default: False
            controls verbosity. ``True`` by default.
        video_file_path : FilePath, optional
            The file path of the video for extracting timestamps.
        frames_per_second : float, optional
            The frames per second (fps) or sampling rate of the video.
        track_name : str, optional
            Which tracked individual to write. An NWB file holds one subject, so a multi-animal ``.slp``
            takes one interface per track. Call ``get_available_tracks`` to see them. Required when the
            file has more than one; the only track is used when it has one. A file where no instance
            carries a track, a labeling project or an untracked single-animal recording, is written as
            one individual and takes no track name.
        video_name : str, optional
            Which recording to write, as the stem of its path. A ``.slp`` assembled in the SLEAP GUI can
            hold several recordings, and those are separate sessions rather than separate views, so they
            belong in separate NWB files. Call ``get_available_videos`` to see them. Required when the
            file holds more than one; the only recording is used when it holds one.
        metadata_key : str, optional
            Key addressing this interface's entries in the dict-based metadata. Derived from the track
            when not given (``"sleap_track_0"``), so one interface per track of the same file gets a
            distinct key and a converter can merge them.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "video_file_path",
                "verbose",
                "frames_per_second",
            ]
            num_positional_args_before_args = 1  # file_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to SLEAPInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            video_file_path = positional_values.get("video_file_path", video_file_path)
            verbose = positional_values.get("verbose", verbose)
            frames_per_second = positional_values.get("frames_per_second", frames_per_second)

        # This import is to assure that the ndx_pose is in the global namespace when an pynwb.io object is created
        # For more detail, see https://github.com/rly/ndx-pose/issues/36
        import ndx_pose  # noqa: F401

        self.file_path = Path(file_path)
        self.video_file_path = video_file_path
        self.video_sample_rate = frames_per_second
        self.verbose = verbose
        self._timestamps = None
        self._labels = None

        track_names = self.get_available_tracks(file_path=file_path)
        # A file where no instance carries a track is a labeling project, or a single-animal recording
        # that was never tracked. SLEAP's own analysis export reads that as one individual, through
        # `tracks = labels.tracks or [None]`, and so does this interface: there is one thing being
        # tracked and nobody named it.
        self._writes_untracked_instances = not track_names

        if track_name is not None:
            if self._writes_untracked_instances:
                raise ValueError(
                    f"Track '{track_name}' cannot be selected, as no instance in this file carries a track. "
                    "That is what a labeling project or an untracked single-animal recording looks like, and "
                    "it is written as one individual without naming a track."
                )
            if track_name not in track_names:
                if track_name in self._get_declared_track_names(file_path=file_path):
                    raise ValueError(
                        f"Track '{track_name}' is declared in this file but no frame carries an instance for "
                        f"it. Tracks that do: {track_names}."
                    )
                raise ValueError(f"Track '{track_name}' is not in this file. Available tracks: {track_names}.")
        elif len(track_names) == 1:
            track_name = track_names[0]
        self.track_name = track_name

        # Every path but the deprecated one writes a single container, and only that one handles a file
        # holding several recordings by itself.
        writes_one_container = track_name is not None or self._writes_untracked_instances

        video_names = self.get_available_videos(file_path=file_path)
        if video_name is not None:
            if video_names.count(video_name) > 1:
                raise ValueError(
                    f"Video '{video_name}' names {video_names.count(video_name)} recordings in this file. "
                    "Two recordings share a file name, so the stem cannot address one of them."
                )
            if video_name not in video_names:
                raise ValueError(f"Video '{video_name}' is not in this file. Available videos: {video_names}.")
        elif len(video_names) > 1 and writes_one_container:
            raise ValueError(
                f"This file holds {len(video_names)} recordings ({video_names}). They are separate sessions "
                "rather than separate views of one, so name the one to write with 'video_name' and use one "
                "interface per recording; 'get_available_videos' lists them."
            )
        self.video_name = video_name if video_name is not None else (video_names[0] if video_names else None)
        # Derived rather than constant: one file yields one interface per track, and a static default
        # would collide on a single registry entry the moment a converter merged them.
        self.metadata_key = metadata_key or ("sleap" if track_name is None else f"sleap_{track_name}")

        # TODO: remove with the deprecation, along with _sleap_legacy.py and the five forwards below.
        # Naming no track means the pre-track_name behaviour, which shares nothing with this class: a
        # different writer, different timing and no pose metadata. It is the whole object that is legacy
        # rather than one method of it, so the old interface is kept verbatim and delegated to.
        self._legacy_interface = None
        if not writes_one_container:
            warnings.warn(
                f"This file tracks {len(track_names)} individuals and an NWB file holds one subject, so "
                "writing them all into one file is deprecated and will be removed on or after August 2027. "
                "Name the individual with 'track_name' and use one interface per track; "
                "'get_available_tracks' lists them.",
                FutureWarning,
                stacklevel=2,
            )
            self._legacy_interface = _SLEAPLegacyInterface(
                file_path=file_path,
                video_file_path=video_file_path,
                verbose=verbose,
                frames_per_second=frames_per_second,
            )

        super().__init__(file_path=file_path)

    def _get_labels(self):
        """Read the .slp file once and cache it."""
        if self._labels is None:
            from sleap_io import load_slp

            self._labels = load_slp(self.file_path)
        return self._labels

    def _get_track_samples(self) -> list[tuple]:
        """This track's ``(labeled frame, instance)`` pairs in this recording, in frame order.

        One pair per sample written, and the single place the selection is made: the timestamps and the
        rows are both read from it, so the number of frames and the number of rows cannot disagree.

        Where a frame holds both a human-placed ``Instance`` and a ``PredictedInstance`` for this track,
        the human's wins, because proofreading a file means correcting what the network got wrong.

        Both filters matter: ``frame_idx`` is only unique within a video, so a file holding several
        recordings would otherwise collapse their frames onto each other.
        """
        samples = []
        for labeled_frame in self._get_labels().labeled_frames:
            if Path(labeled_frame.video.filename).stem != self.video_name:
                continue
            if self._writes_untracked_instances:
                sample = self._select_untracked_instance(labeled_frame=labeled_frame)
                if sample is not None:
                    samples.append((labeled_frame, sample))
                continue
            for instance in [*labeled_frame.user_instances, *labeled_frame.predicted_instances]:
                if instance.track is not None and instance.track.name == self.track_name:
                    samples.append((labeled_frame, instance))
                    break

        # ``Labels.tracks`` is what the tracking run created rather than a census of the animals present,
        # so a file can declare a track that no frame ever carries an instance for. Selecting one used to
        # reach numpy with nothing to stack, which said nothing about tracks or about this file.
        if not samples:
            if self._writes_untracked_instances:
                raise ValueError(f"No frame of video '{self.video_name}' in {self.file_path} holds an instance.")
            raise ValueError(
                f"Track '{self.track_name}' is declared in {self.file_path} but holds no instances in "
                f"video '{self.video_name}'. {self._describe_populated_tracks()}"
            )

        return sorted(samples, key=lambda sample: sample[0].frame_idx)

    def _select_untracked_instance(self, labeled_frame):
        """The one instance of a frame in a file that tracks nothing, or ``None`` where it holds none.

        Human instances take precedence over the network's, as everywhere else here. A frame holding
        more than one is where SLEAP's own export goes wrong: it writes them all into the single slot
        and the last one wins, so a series silently alternates between two animals. A multi-animal
        labeling project is exactly that file, so this refuses instead.
        """
        instances = [instance for instance in labeled_frame.user_instances if instance.track is None] or [
            instance for instance in labeled_frame.predicted_instances if instance.track is None
        ]
        if not instances:
            return None
        if len(instances) > 1:
            raise ValueError(
                f"Frame {labeled_frame.frame_idx} of video '{self.video_name}' holds {len(instances)} "
                "instances and none of them carries a track, so there is no way to say which individual "
                "each belongs to. Run tracking, or assign the identities in the SLEAP GUI, and convert "
                "the result."
            )
        return instances[0]

    def _describe_populated_tracks(self) -> str:
        """Name the tracks that do carry an instance in this recording, for the error above."""
        populated_track_names = sorted(
            {
                instance.track.name
                for labeled_frame in self._get_labels().labeled_frames
                if Path(labeled_frame.video.filename).stem == self.video_name
                for instance in labeled_frame.instances
                if instance.track is not None
            }
        )
        if not populated_track_names:
            return "No track holds an instance in this video."
        return f"Tracks that do: {populated_track_names}."

    def _get_frame_indices(self) -> np.ndarray:
        """The video frame numbers this track was labeled on, in order."""
        return np.asarray([labeled_frame.frame_idx for labeled_frame, _ in self._get_track_samples()])

    def get_original_timestamps(self) -> np.ndarray:
        if self._legacy_interface is not None:
            return self._legacy_interface.get_original_timestamps()
        return self._get_original_timestamps()

    def _get_original_timestamps(self) -> np.ndarray:
        """One time per labeled frame, which is one per sample written.

        Not every video frame carries a prediction, so this is the video's timeline selected by the frames
        this track was labeled on. Selecting here rather than in ``get_timestamps`` is what lets
        ``set_aligned_timestamps`` take back exactly what ``get_timestamps`` handed out.
        """
        frame_indices = self._get_frame_indices()
        if self.video_file_path is not None:
            return np.asarray(extract_timestamps(self.video_file_path))[frame_indices]
        if self.video_sample_rate is not None:
            return frame_indices / self.video_sample_rate
        raise ValueError(
            "Unable to fetch the original timestamps from the video! "
            "Please specify 'video_file_path' or 'frames_per_second' when initializing the interface."
        )

    def get_timestamps(self) -> np.ndarray:
        if self._legacy_interface is not None:
            return self._legacy_interface.get_timestamps()
        return self._get_timestamps()

    def _get_timestamps(self) -> np.ndarray:
        return self._timestamps if self._timestamps is not None else self._get_original_timestamps()

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        if self._legacy_interface is not None:
            return self._legacy_interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)
        self._timestamps = aligned_timestamps

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, **conversion_options) -> None:
        """Write the named track's ``PoseEstimation`` container to the file's behavior module."""
        if self._legacy_interface is not None:
            return self._legacy_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        self._warn_about_untracked_instances()
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **conversion_options)

    def _warn_about_untracked_instances(self) -> None:
        """Say what this recording holds that no track claims, since none of it is written.

        A point carrying no track belongs to no individual, and one frame can hold several of them, so
        they cannot be written as a series without inventing the identities the tracking was meant to
        establish. The message names no track, so several interfaces reading one file warn once between
        them rather than once each.
        """
        if self._writes_untracked_instances:
            return

        untracked_frame_indices = []
        untracked_instance_count = 0
        for labeled_frame in self._get_labels().labeled_frames:
            if Path(labeled_frame.video.filename).stem != self.video_name:
                continue
            count = sum(1 for instance in labeled_frame.instances if instance.track is None)
            if count:
                untracked_frame_indices.append(labeled_frame.frame_idx)
                untracked_instance_count += count

        if not untracked_instance_count:
            return

        shown_frame_indices = sorted(untracked_frame_indices)[:10]
        frames = ", ".join(str(frame_index) for frame_index in shown_frame_indices)
        if len(untracked_frame_indices) > len(shown_frame_indices):
            frames += ", ..."
        warnings.warn(
            f"{untracked_instance_count} instances in {len(untracked_frame_indices)} frames of video "
            f"'{self.video_name}' carry no track and were not written, since a point with no track belongs "
            f"to no individual. Assign them in the SLEAP GUI to write them. Frames: {frames}.",
            UserWarning,
            stacklevel=2,
        )

    def _get_keypoint_names(self) -> list[str]:
        return [node.name for node in self._get_labels().skeletons[0].nodes]

    def _has_user_instances(self) -> bool:
        """Whether any sample written for this track is a human-placed point rather than a prediction."""
        from sleap_io import PredictedInstance

        return any(not isinstance(instance, PredictedInstance) for _, instance in self._get_track_samples())

    def _get_keypoint_data(self) -> dict[str, tuple[np.ndarray, np.ndarray | None]]:
        from sleap_io import PredictedInstance

        keypoint_names = self._get_keypoint_names()

        # (num_frames, num_keypoints, 3), the last axis being x, y and the point's score. A human-placed
        # Instance carries no score, since a person places a point rather than estimating it, so those
        # points are written as 1.0 and 'confidence_definition' says what the 1.0 means. A point the
        # annotator marked not visible comes back as NaN, and its confidence is NaN too: 1.0 there would
        # claim certainty about a position the person declined to give.
        rows = []
        for _, instance in self._get_track_samples():
            if isinstance(instance, PredictedInstance):
                rows.append(instance.numpy(scores=True))
            else:
                positions = instance.numpy()
                confidence = np.where(np.isnan(positions).any(axis=1), np.nan, 1.0)
                rows.append(np.column_stack([positions, confidence]))

        points = np.stack(rows)
        return {
            keypoint_name: (points[:, index, :2], points[:, index, 2])
            for index, keypoint_name in enumerate(keypoint_names)
        }

    def get_metadata(self) -> DeepDict:
        if self._legacy_interface is not None:
            return self._legacy_interface.get_metadata()
        return self._get_metadata()

    def _get_metadata(self) -> DeepDict:
        """Name the objects after the track and add what the .slp file records about the run."""
        metadata = super().get_metadata()
        labels = self._get_labels()
        skeleton = labels.skeletons[0]
        provenance = labels.provenance or {}

        # No track name to derive one from where the file tracks nothing, and none is wanted: there is a
        # single individual and it is the file's own subject.
        container_name = (
            "PoseEstimation" if self.track_name is None else f"PoseEstimation{self.track_name.title().replace('_', '')}"
        )
        metadata["Pose"]["Skeletons"][self.metadata_key].update(
            name=f"Skeleton{container_name}",
            edges=[[skeleton.index(edge.source), skeleton.index(edge.destination)] for edge in skeleton.edges],
            subject=self.track_name,
        )
        # Both sentences hold for every .slp: the first says what the network's number is, the second
        # what this interface writes where there is no such number. The second states the direction that
        # is true, since a model score is not bounded by 1 and can reach it, so a 1.0 does not identify a
        # human point.
        confidence_definition = (
            "Height of the peak in the SLEAP network's confidence map at the location it placed this "
            "keypoint, so a larger value means the network localized the keypoint more strongly. It is "
            "not a calibrated probability and is not bounded by 1. A point placed by a human annotator "
            "while proofreading carries no network score and is written with a confidence of 1.0, and a "
            "point the annotator marked not visible with NaN."
        )

        series_entry = {}
        for keypoint_name in self._get_keypoint_names():
            series_entry[keypoint_name] = {
                "name": f"PoseEstimationSeries{keypoint_name.title().replace('_', '')}",
                "confidence_definition": confidence_definition,
                "reference_frame": (
                    "(0,0) is the top-left pixel of the video frame, with x increasing to the right "
                    "and y increasing downward."
                ),
            }

        container_entry = dict(
            name=container_name,
            source_software="SLEAP",
            PoseEstimationSeries=series_entry,
        )
        if "sleap_version" in provenance:
            container_entry["source_software_version"] = provenance["sleap_version"]
        if "predictor" in provenance:
            container_entry["scorer"] = provenance["predictor"]
        if labels.videos:
            container_entry["original_videos"] = [str(labels.videos[0].filename)]
        metadata["Pose"]["PoseEstimations"][self.metadata_key].update(**container_entry)

        return metadata
