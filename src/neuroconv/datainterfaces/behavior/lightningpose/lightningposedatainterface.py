import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from pynwb import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools import get_module
from ....utils import (
    DeepDict,
    FilePathType,
    calculate_regular_series_rate,
    get_base_schema,
)


class LightningPoseDataInterface(BaseTemporalAlignmentInterface):
    """Data interface for Lightning Pose datasets."""

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")

        metadata_schema["properties"]["Behavior"].update(
            required=["PoseEstimation"],
            properties=dict(
                PoseEstimation=dict(
                    type="object",
                    properties=dict(
                        name=dict(type="string", default="PoseEstimation"),
                        description=dict(type="string"),
                        scorer=dict(type="string"),
                        source_software=dict(type="string", default="LightningPose"),
                        patternProperties={
                            "^[a-zA-Z0-9]+$": dict(
                                title="PoseEstimationSeries",
                                type="object",
                                properties=dict(name=dict(type="string"), description=dict(type="string")),
                            )
                        },
                    ),
                )
            ),
        )

        return metadata_schema

    def __init__(self, file_path: FilePathType, original_video_file_path: FilePathType, verbose: bool = True):
        """
        Interface for writing pose estimation data from the Lightning Pose algorithm.

        Parameters
        ----------
        file_path : a string or a path
            Path to the .csv file that contains the predictions from Lightning Pose.
        original_video_file_path : a string or a path
            Path to the original video file (.mp4)
        verbose : bool, default: True
            controls verbosity. ``True`` by default.
        """
        from neuroconv.datainterfaces.behavior.video.video_utils import (
            VideoCaptureContext,
        )

        self._vc = VideoCaptureContext

        self.file_path = Path(file_path)
        assert self.file_path.exists(), f"The file '{self.file_path}' does not exist."
        parent_folder = self.file_path.parent

        labeled_video_file_path = list(parent_folder.rglob(f"{self.file_path.stem}*_labeled.mp4"))
        self.labeled_video_file_path = labeled_video_file_path[0] if labeled_video_file_path else None

        self.original_video_file_path = Path(original_video_file_path)
        assert (
            self.original_video_file_path.exists()
        ), f"The original video file '{self.original_video_file_path}' does not exist."

        super().__init__(verbose, file_path=file_path, original_video_file_path=original_video_file_path)

        # image size of the original video is in height x width
        self.dimension = self._get_original_video_shape()

        pose_estimation_data = self._load_source_data()
        _, self.scorer_name = pose_estimation_data.columns.get_level_values(0).drop_duplicates()
        self.pose_estimation_data = pose_estimation_data[self.scorer_name]
        self.keypoint_names = self.pose_estimation_data.columns.get_level_values(0).drop_duplicates().tolist()

        self._timestamps = None

    def _load_source_data(self):
        import pandas as pd

        # The order of the header is "scorer", "bodyparts", "coords"
        pose_estimation_data = pd.read_csv(self.file_path, header=[0, 1, 2])
        return pose_estimation_data

    def _get_original_video_shape(self) -> Tuple[int, int]:
        with self._vc(file_path=str(self.original_video_file_path)) as video:
            video_shape = video.get_frame_shape()
        return video_shape[0], video_shape[1]

    def get_original_timestamps(self, stub_test: bool = False) -> np.ndarray:
        max_frames = 10 if stub_test else None
        with self._vc(file_path=str(self.original_video_file_path)) as video:
            timestamps = video.get_video_timestamps(max_frames=max_frames)
        return timestamps

    def get_timestamps(self) -> np.ndarray:
        timestamps = self._timestamps if self._timestamps is not None else self.get_original_timestamps()
        return timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        self._timestamps = aligned_timestamps

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        # Update the session start time if folder structure is saved in the format: YYYY-MM-DD/HH-MM-SS
        pattern = r"(?P<date_time>\d{4}-\d{2}-\d{2}/\d{2}-\d{2}-\d{2})"
        match = re.search(pattern, str(self.file_path))
        if match and "session_start_time" not in metadata["NWBFile"]:
            datetime_str = match.group("date_time")
            session_start_time = datetime.strptime(datetime_str, "%Y-%m-%d/%H-%M-%S")
            metadata["NWBFile"].update(session_start_time=session_start_time)

        metadata["Behavior"]["PoseEstimation"].update(
            name="PoseEstimation",
            scorer=self.scorer_name,
            source_software="LightningPose",
        )
        for keypoint_name in self.keypoint_names:
            series_name_suffix = keypoint_name.replace("_", "-").replace(" ", "")
            pose_estimation_series_metadata = {
                keypoint_name: dict(
                    name=f"PoseEstimationSeries{series_name_suffix}",
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
    ) -> None:
        from ndx_pose import PoseEstimation, PoseEstimationSeries

        # The parameters for the pose estimation container
        pose_estimation_metadata = metadata["Behavior"]["PoseEstimation"]

        behavior = get_module(nwbfile, "behavior", "Processed behavior data.")

        pose_estimation_name = pose_estimation_metadata["name"]
        if pose_estimation_name in behavior.data_interfaces:
            raise ValueError(f"The nwbfile already contains a data interface with the name '{pose_estimation_name}'.")

        pose_estimation_kwargs = dict(
            name=pose_estimation_metadata["name"],
            source_software=pose_estimation_metadata["source_software"],
            scorer=pose_estimation_metadata["scorer"],
            original_videos=[str(self.original_video_file_path)],
            dimensions=[self.dimension],
        )

        timestamps = self.get_timestamps()
        rate = calculate_regular_series_rate(series=timestamps)
        pose_estimation_series_kwargs = dict()
        if rate:
            pose_estimation_series_kwargs.update(rate=rate, starting_time=timestamps[0])
        else:
            pose_estimation_series_kwargs.update(timestamps=timestamps)

        pose_estimation_series = []
        for keypoint_name in self.keypoint_names:
            pose_estimation_series_data = self.pose_estimation_data[keypoint_name]

            pose_estimation_series_kwargs.update(
                name=pose_estimation_metadata[keypoint_name]["name"],
                description=pose_estimation_metadata[keypoint_name]["description"],
                data=pose_estimation_series_data[["x", "y"]].values,
                confidence=pose_estimation_series_data["likelihood"].values,
                reference_frame=reference_frame or "(0,0) is unknown.",
                unit="px",
            )

            if confidence_definition:
                pose_estimation_series_kwargs.update(confidence_definition=confidence_definition)

            pose_estimation_series.append(PoseEstimationSeries(**pose_estimation_series_kwargs))

        pose_estimation_kwargs.update(
            pose_estimation_series=pose_estimation_series,
        )

        if self.labeled_video_file_path:
            pose_estimation_kwargs.update(labeled_videos=[str(self.labeled_video_file_path)])

        # Create the container for pose estimation
        pose_estimation = PoseEstimation(**pose_estimation_kwargs)

        behavior.add(pose_estimation)
