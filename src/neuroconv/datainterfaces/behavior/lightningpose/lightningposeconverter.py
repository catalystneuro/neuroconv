from copy import deepcopy
from typing import Optional

from pydantic import FilePath, validate_call
from pynwb import NWBFile

from neuroconv import NWBConverter
from neuroconv.datainterfaces import LightningPoseDataInterface, VideoInterface
from neuroconv.tools.nwb_helpers import make_or_load_nwbfile
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
        labeled_video_file_path: Optional[FilePath] = None,
        image_series_original_video_name: Optional[str] = None,
        image_series_labeled_video_name: Optional[str] = None,
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
            OriginalVideo=VideoInterface(file_paths=[original_video_file_path]),
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
            self.data_interface_objects.update(dict(LabeledVideo=VideoInterface(file_paths=[labeled_video_file_path])))

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
        reference_frame: Optional[str] = None,
        confidence_definition: Optional[str] = None,
        external_mode: bool = True,
        starting_frames_original_videos: Optional[list[int]] = None,
        starting_frames_labeled_videos: Optional[list[int]] = None,
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
            If True, the videos will be referenced externally rather than embedded within the NWB file, by default True.
        starting_frames_original_videos : list of int, optional
            List of starting frames for the original videos, by default None.
        starting_frames_labeled_videos : list of int, optional
            List of starting frames for the labeled videos, by default None.
        stub_test : bool, optional
            If True, only a subset of the data will be added for testing purposes, by default False.
        """
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

    def run_conversion(
        self,
        nwbfile_path: Optional[FilePath] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        reference_frame: Optional[str] = None,
        confidence_definition: Optional[str] = None,
        external_mode: bool = True,
        starting_frames_original_videos: Optional[list] = None,
        starting_frames_labeled_videos: Optional[list] = None,
        stub_test: bool = False,
    ) -> None:
        """
        Run the full conversion process, adding behavior, video, and pose estimation data to an NWB file.

        Parameters
        ----------
        nwbfile_path : FilePath, optional
            The file path where the NWB file will be saved. If None, the file is handled in memory.
        nwbfile : NWBFile, optional
            An in-memory NWBFile object. If None, a new NWBFile object will be created.
        metadata : dict, optional
            Metadata dictionary for describing the NWB file contents. If None, it is auto-generated.
        overwrite : bool, optional
            If True, overwrites the NWB file at `nwbfile_path` if it exists. If False, appends to the file, by default False.
        reference_frame : str, optional
            Description of the reference frame for pose estimation, by default None.
        confidence_definition : str, optional
            Definition for confidence levels in pose estimation, by default None.
        external_mode : bool, optional
            If True, the videos will be referenced externally rather than embedded within the NWB file, by default True.
        starting_frames_original_videos : list of int, optional
            List of starting frames for the original videos, by default None.
        starting_frames_labeled_videos : list of int, optional
            List of starting frames for the labeled videos, by default None.
        stub_test : bool, optional
            If True, only a subset of the data will be added for testing purposes, by default False.

        """
        if metadata is None:
            metadata = self.get_metadata()

        self.validate_metadata(metadata=metadata)

        self.temporally_align_data_interfaces()

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
        ) as nwbfile_out:
            self.add_to_nwbfile(
                nwbfile=nwbfile_out,
                metadata=metadata,
                reference_frame=reference_frame,
                confidence_definition=confidence_definition,
                external_mode=external_mode,
                starting_frames_original_videos=starting_frames_original_videos,
                starting_frames_labeled_videos=starting_frames_labeled_videos,
                stub_test=stub_test,
            )
