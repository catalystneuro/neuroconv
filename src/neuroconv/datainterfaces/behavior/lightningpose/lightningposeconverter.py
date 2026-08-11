import warnings
from copy import deepcopy

from pydantic import FilePath, validate_call
from pynwb import NWBFile

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.datainterfaces import LightningPoseDataInterface
from neuroconv.datainterfaces.behavior.video.externalvideointerface import (
    ExternalVideoInterface,
)
from neuroconv.utils import (
    DeepDict,
    dict_deep_update,
)


class LightningPoseConverter(BaseDataInterface):
    """Primary conversion class for handling Lightning Pose data streams."""

    display_name = "Lightning Pose Converter"
    keywords = ("pose estimation", "video")
    associated_suffixes = (".csv", ".mp4")
    info = "Interface for handling multiple streams of lightning pose data."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        original_video_file_path: FilePath,
        labeled_video_file_path: FilePath | None = None,
        image_series_original_video_name: str | None = None,
        image_series_labeled_video_name: str | None = None,
        verbose: bool = False,
    ):
        """
        The converter for Lightning Pose format to convert the pose estimation data
        along with the original and the optional labeled video added as ImageSeries to NWB.

        Parameters
        ----------
        file_path : FilePath
            Path to the .csv file that contains the predictions from Lightning Pose.
        original_video_file_path : FilePath
            Path to the original video file (.mp4).
        labeled_video_file_path : FilePath, optional
            Path to the labeled video file (.mp4).
        image_series_original_video_name: string, optional
            The name of the ImageSeries to add for the original video.
        image_series_labeled_video_name: string, optional
            The name of the ImageSeries to add for the labeled video.
        verbose : bool, default: False
            controls verbosity. ``True`` by default.
        """
        self.verbose = verbose

        self.original_video_name = image_series_original_video_name or "ImageSeriesOriginalVideo"
        self.labeled_video_name = None

        self.data_interface_objects = dict(
            OriginalVideo=ExternalVideoInterface(
                file_paths=[original_video_file_path],
                metadata_key="original_video",
                video_name=self.original_video_name,
            ),
            PoseEstimation=LightningPoseDataInterface(
                file_path=file_path,
                original_video_file_path=original_video_file_path,
                labeled_video_file_path=labeled_video_file_path,
            ),
        )
        if labeled_video_file_path:
            self.labeled_video_name = image_series_labeled_video_name or "ImageSeriesLabeledVideo"
            self.data_interface_objects["LabeledVideo"] = ExternalVideoInterface(
                file_paths=[labeled_video_file_path],
                metadata_key="labeled_video",
                video_name=self.labeled_video_name,
            )

    def get_metadata(self) -> DeepDict:
        metadata = self.data_interface_objects["PoseEstimation"].get_metadata()
        original_video_interface = self.data_interface_objects["OriginalVideo"]
        original_videos_metadata = original_video_interface.get_metadata()
        original_videos_metadata["Behavior"]["ExternalVideos"]["original_video"].update(
            description="The original video used for pose estimation.",
        )
        metadata = dict_deep_update(metadata, original_videos_metadata)

        if "LabeledVideo" in self.data_interface_objects:
            labeled_video_interface = self.data_interface_objects["LabeledVideo"]
            labeled_videos_metadata = labeled_video_interface.get_metadata()
            labeled_videos_metadata["Behavior"]["ExternalVideos"]["labeled_video"].update(
                description="The video recorded by camera with the pose estimation labels.",
            )
            metadata = dict_deep_update(metadata, labeled_videos_metadata)

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        reference_frame: str | None = None,
        confidence_definition: str | None = None,
        starting_frames_original_videos: list[int] | None = None,
        starting_frames_labeled_videos: list[int] | None = None,
        stub_test: bool = False,
    ):
        """
        Add behavior and pose estimation data, including original and labeled videos, to the specified NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile object to which the data will be added.
        metadata : dict
            Metadata dictionary containing information about the behavior and videos.
        reference_frame : str, optional
            Description of the reference frame for pose estimation, by default None.
        confidence_definition : str, optional
            Definition for the confidence levels in pose estimation, by default None.
        starting_frames_original_videos : list of int, optional
            List of starting frames for the original videos, by default None.
        starting_frames_labeled_videos : list of int, optional
            List of starting frames for the labeled videos, by default None.
        stub_test : bool, optional
            If True, only a subset of the data will be added for testing purposes, by default False.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "reference_frame",
                "confidence_definition",
                "starting_frames_original_videos",
                "starting_frames_labeled_videos",
                "stub_test",
            ]
            num_positional_args_before_args = 2  # nwbfile, metadata
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"add_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                    f"{len(args) + num_positional_args_before_args} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to LightningPoseConverter.add_to_nwbfile() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            reference_frame = positional_values.get("reference_frame", reference_frame)
            confidence_definition = positional_values.get("confidence_definition", confidence_definition)
            starting_frames_original_videos = positional_values.get(
                "starting_frames_original_videos", starting_frames_original_videos
            )
            starting_frames_labeled_videos = positional_values.get(
                "starting_frames_labeled_videos", starting_frames_labeled_videos
            )
            stub_test = positional_values.get("stub_test", stub_test)

        original_video_interface = self.data_interface_objects["OriginalVideo"]
        metadata_copy = deepcopy(metadata)
        original_video_interface.add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata_copy,
            starting_frames=starting_frames_original_videos,
        )

        if "LabeledVideo" in self.data_interface_objects:
            labeled_video_interface = self.data_interface_objects["LabeledVideo"]
            labeled_video_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata_copy,
                starting_frames=starting_frames_labeled_videos,
                parent_container="processing/behavior",
            )

        pose_metadata = deepcopy(metadata)
        videos_list = [dict(name=self.original_video_name)]
        if self.labeled_video_name is not None:
            videos_list.append(dict(name=self.labeled_video_name))
        pose_metadata["Behavior"]["Videos"] = videos_list
        self.data_interface_objects["PoseEstimation"].add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=pose_metadata,
            reference_frame=reference_frame,
            confidence_definition=confidence_definition,
            stub_test=stub_test,
        )
