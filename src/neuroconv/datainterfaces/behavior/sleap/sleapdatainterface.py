import warnings
from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call

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
        """Return the track names in a .slp file, one per tracked individual."""
        from sleap_io import load_slp

        return [track.name for track in load_slp(Path(file_path)).tracks]

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        video_file_path: FilePath | None = None,
        verbose: bool = False,
        frames_per_second: float | None = None,
        track_name: str | None = None,
        metadata_key: str = "sleap",
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
            file has more than one; the only track is used when it has one.
        metadata_key : str, default: "sleap"
            Key addressing this interface's entries in the dict-based metadata.
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
        self.metadata_key = metadata_key

        track_names = self.get_available_tracks(file_path=file_path)
        if track_name is None:
            if len(track_names) > 1:
                raise ValueError(
                    f"This file tracks {len(track_names)} individuals ({track_names}) and an NWB file holds "
                    "one subject, so name the one to write with 'track_name' and use one interface per track."
                )
            track_name = track_names[0] if track_names else None
        elif track_name not in track_names:
            raise ValueError(f"Track '{track_name}' is not in this file. Available tracks: {track_names}.")
        self.track_name = track_name

        super().__init__(file_path=file_path)

    def _get_labels(self):
        """Read the .slp file once and cache it."""
        if self._labels is None:
            from sleap_io import load_slp

            self._labels = load_slp(self.file_path)
        return self._labels

    def _get_frame_indices(self) -> np.ndarray:
        """The video frame numbers this track was labeled on, in order."""
        labels = self._get_labels()
        frame_indices = [
            labeled_frame.frame_idx
            for labeled_frame in labels.labeled_frames
            if any(
                instance.track is not None and instance.track.name == self.track_name
                for instance in labeled_frame.instances
            )
        ]
        return np.asarray(sorted(frame_indices))

    def get_original_timestamps(self) -> np.ndarray:
        """One time per labeled frame, read off the video or derived from the frame rate."""
        frame_indices = self._get_frame_indices()
        if self.video_file_path is not None:
            video_timestamps = np.asarray(extract_timestamps(self.video_file_path))
            return video_timestamps[frame_indices]
        if self.video_sample_rate is not None:
            return frame_indices / self.video_sample_rate
        raise ValueError(
            "No timing information is available for this SLEAP output. Its rows are video frames and the "
            ".slp file records no frame rate, so the times cannot be derived from the source. Pass "
            "'video_file_path' or 'frames_per_second' to SLEAPInterface, or call 'set_aligned_timestamps' "
            "with one time per labeled frame."
        )

    def get_timestamps(self) -> np.ndarray:
        timestamps = self._timestamps if self._timestamps is not None else self.get_original_timestamps()
        return timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        self._timestamps = aligned_timestamps

    def get_keypoint_names(self) -> list[str]:
        return [node.name for node in self._get_labels().skeletons[0].nodes]

    def _get_keypoint_data(self) -> dict[str, tuple[np.ndarray, np.ndarray | None]]:
        labels = self._get_labels()
        keypoint_names = self.get_keypoint_names()
        frame_indices = self._get_frame_indices()

        # One row per labeled frame, in frame order. A frame where the track has no instance cannot
        # happen here, since _get_frame_indices selects the frames where it does.
        instances_by_frame = {}
        for labeled_frame in labels.labeled_frames:
            for instance in labeled_frame.instances:
                if instance.track is not None and instance.track.name == self.track_name:
                    instances_by_frame[labeled_frame.frame_idx] = instance

        # (num_frames, num_keypoints, 3), the last axis being x, y and the point's score.
        points = np.stack([instances_by_frame[frame_index].numpy(scores=True) for frame_index in frame_indices])
        return {
            keypoint_name: (points[:, index, :2], points[:, index, 2])
            for index, keypoint_name in enumerate(keypoint_names)
        }

    def get_metadata(self) -> DeepDict:
        """Name the objects after the track and add what the .slp file records about the run."""
        metadata = super().get_metadata()
        labels = self._get_labels()
        skeleton = labels.skeletons[0]
        provenance = labels.provenance or {}

        container_name = f"PoseEstimation{self.track_name.title().replace('_', '')}"
        metadata["Pose"]["Skeletons"][self.metadata_key].update(
            name=f"Skeleton{container_name}",
            edges=[[skeleton.index(edge.source), skeleton.index(edge.destination)] for edge in skeleton.edges],
            subject=self.track_name,
        )
        container_entry = dict(
            name=container_name,
            source_software="SLEAP",
            PoseEstimationSeries={
                keypoint_name: {"name": f"PoseEstimationSeries{keypoint_name.title().replace('_', '')}"}
                for keypoint_name in self.get_keypoint_names()
            },
        )
        if "sleap_version" in provenance:
            container_entry["source_software_version"] = provenance["sleap_version"]
        if "predictor" in provenance:
            container_entry["scorer"] = provenance["predictor"]
        if labels.videos:
            container_entry["original_videos"] = [str(labels.videos[0].filename)]
        metadata["Pose"]["PoseEstimations"][self.metadata_key].update(**container_entry)

        return metadata
