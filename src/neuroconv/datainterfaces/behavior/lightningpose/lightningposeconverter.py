import warnings
from copy import deepcopy

from pydantic import FilePath, validate_call
from pynwb import NWBFile

from neuroconv import NWBConverter
from neuroconv.datainterfaces import LightningPoseDataInterface
from neuroconv.datainterfaces.behavior.video.videodatainterface import _VideoInterface
from neuroconv.utils import (
    DeepDict,
    dict_deep_update,
    get_json_schema_from_method_signature,
)


class LightningPoseConverter(NWBConverter):
    """Primary conversion class for handling Lightning Pose data streams."""

    display_name = "Lightning Pose Converter"
    keywords = ("pose estimation", "video")
    associated_suffixes = (".csv", ".mp4")
    info = "Interface for handling multiple streams of lightning pose data."

    @classmethod
    def get_source_schema(cls):
        return get_json_schema_from_method_signature(cls)

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

        self.data_interface_objects = dict(
            OriginalVideo=_VideoInterface(file_paths=[original_video_file_path]),
            PoseEstimation=LightningPoseDataInterface(
                file_path=file_path,
                original_video_file_path=original_video_file_path,
                labeled_video_file_path=labeled_video_file_path,
            ),
        )
        self.original_video_name = image_series_original_video_name or "ImageSeriesOriginalVideo"
        self.labeled_video_name = None
        if labeled_video_file_path:
            self.labeled_video_name = image_series_labeled_video_name or "ImageSeriesLabeledVideo"
            self.data_interface_objects.update(dict(LabeledVideo=_VideoInterface(file_paths=[labeled_video_file_path])))

    def get_conversion_options_schema(self) -> dict:
        conversion_options_schema = get_json_schema_from_method_signature(
            method=self.add_to_nwbfile, exclude=["nwbfile", "metadata"]
        )

        return conversion_options_schema

    def get_metadata(self) -> DeepDict:
        metadata = self.data_interface_objects["PoseEstimation"].get_metadata()
        original_video_interface = self.data_interface_objects["OriginalVideo"]
        original_videos_metadata = original_video_interface.get_metadata()
        metadata = dict_deep_update(metadata, original_videos_metadata)

        original_videos_metadata["Behavior"]["Videos"][0].update(
            name=self.original_video_name,
            description="The original video used for pose estimation.",
        )

        if "LabeledVideo" in self.data_interface_objects:
            labeled_video_interface = self.data_interface_objects["LabeledVideo"]
            labeled_videos_metadata = labeled_video_interface.get_metadata()
            labeled_videos_metadata["Behavior"]["Videos"][0].update(
                name=self.labeled_video_name,
                description="The video recorded by camera with the pose estimation labels.",
            )

            metadata = dict_deep_update(metadata, labeled_videos_metadata)

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *args,
        reference_frame: str | None = None,
        confidence_definition: str | None = None,
        external_mode: bool = True,
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
        external_mode : bool, optional
            DEPRECATED. This parameter will be removed in May 2026.
            If True, the videos will be referenced externally rather than embedded within the NWB file, by default True.
        starting_frames_original_videos : list of int, optional
            List of starting frames for the original videos, by default None.
        starting_frames_labeled_videos : list of int, optional
            List of starting frames for the labeled videos, by default None.
        stub_test : bool, optional
            If True, only a subset of the data will be added for testing purposes, by default False.
        """
        # Handle deprecated positional arguments
        # TODO: Remove after May 2026 - only keyword arguments will be supported
        if args:
            parameter_names = [
                "reference_frame",
                "confidence_definition",
                "external_mode",
                "starting_frames_original_videos",
                "starting_frames_labeled_videos",
                "stub_test",
            ]
            num_positional_args_before_args = 2  # nwbfile, metadata
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"add_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                    f"{len(args) + num_positional_args_before_args} were given. "
                    "Note: Positional arguments are deprecated and will be removed in May 2026. Please use keyword arguments."
                )
            # Map positional args to keyword args, positional args take precedence
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally is deprecated and will be removed in May 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            reference_frame = positional_values.get("reference_frame", reference_frame)
            confidence_definition = positional_values.get("confidence_definition", confidence_definition)
            external_mode = positional_values.get("external_mode", external_mode)
            starting_frames_original_videos = positional_values.get(
                "starting_frames_original_videos", starting_frames_original_videos
            )
            starting_frames_labeled_videos = positional_values.get(
                "starting_frames_labeled_videos", starting_frames_labeled_videos
            )
            stub_test = positional_values.get("stub_test", stub_test)

        # Deprecate external_mode parameter
        # TODO: Remove after May 2026 - Only external videos will be supported
        if external_mode is not True:
            warnings.warn(
                "The 'external_mode' parameter is deprecated and will be removed in May 2026. "
                "After May 2026, only external videos will be supported by LightningPoseConverter.",
                FutureWarning,
                stacklevel=2,
            )

        # Detect old metadata structure and warn user to migrate
        if "Videos" in metadata.get("Behavior", {}):
            warnings.warn(
                "The 'Videos' metadata structure is deprecated and will be removed in May 2026. "
                "Please use 'ExternalVideos' metadata structure instead.",
                FutureWarning,
                stacklevel=2,
            )

        # Convert new metadata structure to old structure for _VideoInterface compatibility
        # TODO: Remove after May 2026 when _VideoInterface is replaced
        metadata = self._convert_new_metadata_to_old(metadata)

        original_video_interface = self.data_interface_objects["OriginalVideo"]

        original_video_metadata = next(
            video_metadata
            for video_metadata in metadata["Behavior"]["Videos"]
            if video_metadata["name"] == self.original_video_name
        )
        if original_video_metadata is None:
            raise ValueError(f"Metadata for '{self.original_video_name}' not found in metadata['Behavior']['Videos'].")
        metadata_copy = deepcopy(metadata)
        metadata_copy["Behavior"]["Videos"] = [original_video_metadata]
        original_video_interface.add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata_copy,
            stub_test=stub_test,
            external_mode=external_mode,
            starting_frames=starting_frames_original_videos,
        )

        if "LabeledVideo" in self.data_interface_objects:
            labeled_video_interface = self.data_interface_objects["LabeledVideo"]
            labeled_video_metadata = next(
                video_metadata
                for video_metadata in metadata["Behavior"]["Videos"]
                if video_metadata["name"] == self.labeled_video_name
            )
            if labeled_video_metadata is None:
                raise ValueError(
                    f"Metadata for '{self.labeled_video_name}' not found in metadata['Behavior']['Videos']."
                )
            metadata_copy["Behavior"]["Videos"] = [labeled_video_metadata]
            labeled_video_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata_copy,
                stub_test=stub_test,
                external_mode=external_mode,
                starting_frames=starting_frames_labeled_videos,
                module_name="behavior",
            )

        self.data_interface_objects["PoseEstimation"].add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            reference_frame=reference_frame,
            confidence_definition=confidence_definition,
            stub_test=stub_test,
        )

    def _convert_new_metadata_to_old(self, metadata: dict) -> dict:
        """
        Convert new ExternalVideos dict metadata to old Videos list metadata.

        TODO: Remove after May 2026 when _VideoInterface is replaced with ExternalVideoInterface.
        """
        metadata = deepcopy(metadata)

        # Check if new metadata structure is being used
        if "ExternalVideos" in metadata.get("Behavior", {}):
            # Convert ExternalVideos dict to Videos list
            videos_dict = metadata["Behavior"]["ExternalVideos"]
            videos_list = []
            for video_name, video_metadata in videos_dict.items():
                video_dict = {"name": video_name}
                # Copy all metadata except device (not in old structure)
                video_dict.update({k: v for k, v in video_metadata.items() if k != "device"})
                videos_list.append(video_dict)

            metadata["Behavior"]["Videos"] = videos_list
            # Remove new structure key
            del metadata["Behavior"]["ExternalVideos"]

        return metadata
