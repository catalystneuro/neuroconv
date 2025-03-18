import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module
from ....utils import (
    DeepDict,
    calculate_regular_series_rate,
    get_base_schema,
)


class LightningPoseDataInterface(BaseTemporalAlignmentInterface):
    """Data interface for Lightning Pose datasets."""

    display_name = "Lightning Pose"
    keywords = ("pose estimation", "video")
    associated_suffixes = (".csv", ".mp4")
    info = "Interface for handling a single stream of lightning pose data."

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")

        metadata_schema["properties"]["Behavior"].update(
            required=["PoseEstimation"],
            properties=dict(
                PoseEstimation=dict(
                    type="object",
                    required=["name"],
                    properties=dict(
                        name=dict(type="string", default="PoseEstimation"),
                        description=dict(type="string"),
                        scorer=dict(type="string"),
                        source_software=dict(type="string", default="LightningPose"),
                        camera_name=dict(type="string", default="CameraPoseEstimation"),
                    ),
                    patternProperties={
                        "^(?!(name|description|scorer|source_software|camera_name)$)[a-zA-Z0-9_]+$": dict(
                            title="PoseEstimationSeries",
                            type="object",
                            properties=dict(name=dict(type="string"), description=dict(type="string")),
                            minProperties=1,
                            additionalProperties=False,
                        )
                    },
                    minProperties=2,
                    additionalProperties=False,
                )
            ),
        )

        return metadata_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        original_video_file_path: FilePath,
        labeled_video_file_path: Optional[FilePath] = None,
        verbose: bool = False,
    ):
        """
        Interface for writing pose estimation data from the Lightning Pose algorithm.

        Parameters
        ----------
        file_path : FilePath
            Path to the .csv file that contains the predictions from Lightning Pose.
        original_video_file_path : FilePath
            Path to the original video file (.mp4).
        labeled_video_file_path : a string or a path, optional
            Path to the labeled video file (.mp4).
        verbose : bool, default: False
            controls verbosity. ``True`` by default.
        """

        # This import is to assure that the ndx_pose is in the global namespace when an pynwb.io object is created
        # For more detail, see https://github.com/rly/ndx-pose/issues/36
        from importlib.metadata import version

        import ndx_pose  # noqa: F401
        from packaging import version as version_parse

        ndx_pose_version = version("ndx-pose")
        if version_parse.parse(ndx_pose_version) < version_parse.parse("0.2.0"):
            raise ImportError(
                "LightningPose interface requires ndx-pose version 0.2.0 or later. "
                f"Found version {ndx_pose_version}. Please upgrade: "
                "pip install 'ndx-pose>=0.2.0'"
            )

        from neuroconv.datainterfaces.behavior.video.video_utils import (
            VideoCaptureContext,
        )

        self._vc = VideoCaptureContext

        self.file_path = Path(file_path)
        assert self.file_path.exists(), f"The file '{self.file_path}' does not exist."
        self.original_video_file_path = Path(original_video_file_path)
        assert (
            self.original_video_file_path.exists()
        ), f"The original video file '{self.original_video_file_path}' does not exist."

        super().__init__(
            verbose,
            file_path=file_path,
            original_video_file_path=original_video_file_path,
            labeled_video_file_path=labeled_video_file_path,
        )

        # dimension is width by height
        self.dimension = self._get_original_video_shape()

        pose_estimation_data = self._load_source_data()
        _, self.scorer_name = pose_estimation_data.columns.get_level_values(0).drop_duplicates()
        self.pose_estimation_data = pose_estimation_data[self.scorer_name]
        self.keypoint_names = self.pose_estimation_data.columns.get_level_values(0).drop_duplicates().tolist()

        self._times = None

    def _load_source_data(self):
        import pandas as pd

        # The order of the header is "scorer", "bodyparts", "coords"
        pose_estimation_data = pd.read_csv(self.file_path, header=[0, 1, 2])
        return pose_estimation_data

    def _get_original_video_shape(self) -> tuple[int, int]:
        with self._vc(file_path=str(self.original_video_file_path)) as video:
            video_shape = video.get_frame_shape()
        # image size of the original video is in height x width
        return video_shape[0], video_shape[1]

    def get_original_timestamps(self, stub_test: bool = False) -> np.ndarray:
        max_frames = 10 if stub_test else None
        with self._vc(file_path=str(self.original_video_file_path)) as video:
            timestamps = video.get_video_timestamps(max_frames=max_frames)
        return timestamps

    def get_timestamps(self, stub_test: bool = False) -> np.ndarray:
        max_frames = 10 if stub_test else None
        if self._times is None:
            return self.get_original_timestamps(stub_test=stub_test)

        timestamps = self._times if not stub_test else self._times[:max_frames]
        return timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        self._times = aligned_timestamps

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        # Update the session start time if folder structure is saved in the format: YYYY-MM-DD/HH-MM-SS
        pattern = r"(?P<date_time>\d{4}-\d{2}-\d{2}/\d{2}-\d{2}-\d{2})"
        # Convert the file path parts to a string with forward slashes
        file_path = "/".join(self.file_path.parts)
        match = re.search(pattern, file_path)
        if match and "session_start_time" not in metadata["NWBFile"]:
            datetime_str = match.group("date_time")
            session_start_time = datetime.strptime(datetime_str, "%Y-%m-%d/%H-%M-%S")
            metadata["NWBFile"].update(session_start_time=session_start_time)

        metadata["Behavior"]["PoseEstimation"].update(
            name="PoseEstimation",
            description="Contains the pose estimation series for each keypoint.",
            scorer=self.scorer_name,
            source_software="LightningPose",
            camera_name="CameraPoseEstimation",
        )
        for keypoint_name in self.keypoint_names:
            keypoint_name_without_spaces = keypoint_name.replace(" ", "")
            pose_estimation_series_metadata = {
                keypoint_name: dict(
                    name=f"PoseEstimationSeries{keypoint_name_without_spaces}",
                    description=f"The estimated position (x, y) of {keypoint_name} over time.",
                )
            }
            metadata["Behavior"]["PoseEstimation"].update(pose_estimation_series_metadata)

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        reference_frame: Optional[str] = None,
        confidence_definition: Optional[str] = None,
        stub_test: Optional[bool] = False,
    ) -> None:
        """
        Add the pose estimation data to the nwbfile.

        Parameters
        ----------
        nwbfile : NWBFile
            The nwbfile to which the pose estimation data is added.
        metadata : dict, optional
            The metadata for the pose estimation data.
        reference_frame : str, optional
            The description defining what the (0, 0) coordinate corresponds to.
        confidence_definition : str, optional
            The description of how the confidence was computed, e.g., 'Softmax output of the deep neural network'.
        stub_test : bool, default: False
        """
        from ndx_pose import PoseEstimation, PoseEstimationSeries, Skeleton, Skeletons

        metadata_copy = deepcopy(metadata)

        # The parameters for the pose estimation container
        pose_estimation_metadata = metadata_copy["Behavior"]["PoseEstimation"]

        behavior = get_module(nwbfile, "behavior")

        pose_estimation_name = pose_estimation_metadata["name"]
        if pose_estimation_name in behavior.data_interfaces:
            raise ValueError(f"The nwbfile already contains a data interface with the name '{pose_estimation_name}'.")

        if "Videos" not in metadata_copy["Behavior"]:
            original_video_name = str(self.original_video_file_path)
        else:
            original_video_name = metadata_copy["Behavior"]["Videos"][0]["name"]
        camera_name = pose_estimation_metadata["camera_name"]
        if camera_name in nwbfile.devices:
            camera = nwbfile.devices[camera_name]
        else:
            camera = nwbfile.create_device(
                name=camera_name,
                description="Camera used for behavioral recording and pose estimation.",
            )

        pose_estimation_data = self.pose_estimation_data if not stub_test else self.pose_estimation_data.head(n=10)
        timestamps = self.get_timestamps(stub_test=stub_test)
        rate = calculate_regular_series_rate(series=timestamps)
        if rate:
            pose_estimation_series_kwargs = dict(rate=rate, starting_time=timestamps[0])
        else:
            assert len(timestamps) == len(
                pose_estimation_data
            ), f"The length of timestamps ({len(timestamps)}) and pose estimation data ({len(pose_estimation_data)}) must be equal."
            pose_estimation_series_kwargs = dict(timestamps=timestamps)

        pose_estimation_series = []
        for keypoint_name in self.keypoint_names:
            pose_estimation_series_data = pose_estimation_data[keypoint_name]
            keypoint_name_without_spaces = keypoint_name.replace(" ", "")

            pose_estimation_series_kwargs.update(
                name=pose_estimation_metadata[keypoint_name_without_spaces]["name"],
                description=pose_estimation_metadata[keypoint_name_without_spaces]["description"],
                data=pose_estimation_series_data[["x", "y"]].values,
                confidence=pose_estimation_series_data["likelihood"].values,
                reference_frame=reference_frame or "(0,0) is unknown.",
                unit="px",
            )

            if confidence_definition:
                pose_estimation_series_kwargs.update(confidence_definition=confidence_definition)

            pose_estimation_series.append(PoseEstimationSeries(**pose_estimation_series_kwargs))

        # Add Skeleton(s)
        nodes = [keypoint_name.replace(" ", "") for keypoint_name in self.keypoint_names]
        subject = nwbfile.subject if nwbfile.subject is not None else None
        name = f"Skeleton{pose_estimation_name}"
        skeleton = Skeleton(name=name, nodes=nodes, subject=subject)
        if "Skeletons" in behavior.data_interfaces:
            skeletons = behavior.data_interfaces["Skeletons"]
            skeletons.add_skeletons(skeleton)
        else:
            skeletons = Skeletons(skeletons=[skeleton])
            behavior.add(skeletons)

        pose_estimation_kwargs = dict(
            name=pose_estimation_metadata["name"],
            description=pose_estimation_metadata["description"],
            source_software=pose_estimation_metadata["source_software"],
            scorer=pose_estimation_metadata["scorer"],
            original_videos=[original_video_name],
            dimensions=[self.dimension],
            pose_estimation_series=pose_estimation_series,
            devices=[camera],
            skeleton=skeleton,
        )

        if self.source_data["labeled_video_file_path"]:
            if "Videos" not in metadata_copy["Behavior"]:
                labeled_video_name = str(self.source_data["labeled_video_file_path"])
            else:
                labeled_video_name = metadata_copy["Behavior"]["Videos"][1]["name"]

            pose_estimation_kwargs.update(labeled_videos=[labeled_video_name])

        # Create the container for pose estimation
        pose_estimation = PoseEstimation(**pose_estimation_kwargs)

        behavior.add(pose_estimation)
