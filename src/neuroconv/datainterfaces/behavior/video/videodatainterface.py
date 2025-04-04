import warnings
from copy import deepcopy
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.image import ImageSeries

from .externalvideointerface import ExternalVideoInterface
from .internalvideointerface import InternalVideoInterface
from .video_utils import VideoCaptureContext
from ....basedatainterface import BaseDataInterface
from ....tools import get_package
from ....utils import get_base_schema, get_schema_from_hdmf_class


class VideoInterface(BaseDataInterface):
    """Data interface for writing videos as ImageSeries."""

    display_name = "Video"
    keywords = ("movie", "natural behavior", "tracking")
    associated_suffixes = (".mp4", ".avi", ".wmv", ".mov", ".flx", ".mkv")
    # Other suffixes, while they can be opened by OpenCV, are not supported by DANDI so should probably not list here
    info = "Interface for handling standard video file formats."

    @validate_call
    def __init__(
        self,
        file_paths: list[FilePath],
        verbose: bool = False,
        *,
        metadata_key_name: str = "Videos",
    ):
        """
        Create the interface for writing videos as ImageSeries.

        Parameters
        ----------
        file_paths : list of FilePaths
            Many video storage formats segment a sequence of videos over the course of the experiment.
            Pass the file paths for this videos as a list in sorted, consecutive order.
        metadata_key_name : str, optional
            The key used to identify this video data within the overall experiment metadata.
            Defaults to "Videos".

            This key is essential when multiple video streams are present in a single experiment.
            The associated metadata should be a list of dictionaries, with each dictionary
            containing metadata for a specific video segment:

            ```
            metadata["Behavior"][metadata_key_name] = [
                {video1_metadata},
                {video2_metadata},
                ...
            ]
            ```

            If other video interfaces exist, they would follow a similar structure:

            ```
            metadata["Behavior"]["other_video_key_name"] = [
                {other_video1_metadata},
                {other_video2_metadata},
                ...
            ]
        """
        warnings.warn(
            "The VideoInterface is deprecated and will be removed on or after September 2025. "
            "Please use the ExternalVideoInterface or InternalVideoInterface instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        get_package(package_name="cv2", installation_instructions="pip install opencv-python-headless")
        self.verbose = verbose
        self._number_of_files = len(file_paths)
        self._timestamps = None
        self._segment_starting_times = None
        self.metadata_key_name = metadata_key_name
        super().__init__(file_paths=file_paths)

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        image_series_metadata_schema = get_schema_from_hdmf_class(ImageSeries)
        # TODO: in future PR, add 'exclude' option to get_schema_from_hdmf_class to bypass this popping
        exclude = ["format", "conversion", "starting_time", "rate"]
        for key in exclude:
            image_series_metadata_schema["properties"].pop(key)
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        metadata_schema["properties"]["Behavior"]["required"].append(self.metadata_key_name)
        metadata_schema["properties"]["Behavior"]["properties"][self.metadata_key_name] = dict(
            type="array",
            minItems=1,
            items=image_series_metadata_schema,
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        behavior_metadata = {
            self.metadata_key_name: [
                dict(name=f"Video {Path(file_path).stem}", description="Video recorded by camera.", unit="Frames")
                for file_path in self.source_data["file_paths"]
            ]
        }
        metadata["Behavior"] = behavior_metadata

        return metadata

    def get_original_timestamps(self, stub_test: bool = False) -> list[np.ndarray]:
        """
        Retrieve the original unaltered timestamps for the data in this interface.

        This function should retrieve the data on-demand by re-initializing the IO.

        Returns
        -------
        timestamps : numpy.ndarray
            The timestamps for the data stream.
        stub_test : bool, default: False
            This method scans through each video; a process which can take some time to complete.

            To limit that scan to a small number of frames, set `stub_test=True`.
        """
        max_frames = 10 if stub_test else None
        timestamps = list()
        for j, file_path in enumerate(self.source_data["file_paths"]):
            with VideoCaptureContext(file_path=str(file_path)) as video:
                # fps = video.get_video_fps()  # There is some debate about whether the OpenCV timestamp
                # method is simply returning range(length) / fps 100% of the time for any given format
                timestamps.append(video.get_video_timestamps(max_frames=max_frames))
        return timestamps

    def get_timing_type(self) -> Literal["starting_time and rate", "timestamps"]:
        """
        Determine the type of timing used by this interface.

        Returns
        -------
        Literal["starting_time and rate", "timestamps"]
            The type of timing that has been set explicitly according to alignment.

            If only timestamps have been set, then only those will be used.
            If only starting times have been set, then only those will be used.

            If timestamps were set, and then starting times were set, the timestamps will take precedence
            as they will then be shifted by the corresponding starting times.

            If neither has been set, and there is only one video in the file_paths,
            it is assumed the video is regularly sampled and pre-aligned with
            a starting_time of 0.0 relative to the session start time.
        """
        if self._timestamps is not None:
            return "timestamps"
        elif self._segment_starting_times is not None:
            return "starting_time and rate"
        elif self._timestamps is None and self._segment_starting_times is None and self._number_of_files == 1:
            return "starting_time and rate"  # default behavior assumes data is pre-aligned; starting_times = [0.0]
        else:
            raise ValueError(
                f"No timing information is specified and there are {self._number_of_files} total video files! "
                "Please specify the temporal alignment of each video."
            )

    def get_timestamps(self, stub_test: bool = False) -> list[np.ndarray]:
        """
        Retrieve the timestamps for the data in this interface.

        Returns
        -------
        timestamps : numpy.ndarray
            The timestamps for the data stream.
        stub_test : bool, default: False
            If timestamps have not been set to this interface, it will attempt to retrieve them
            using the `.get_original_timestamps` method, which scans through each video;
            a process which can take some time to complete.

            To limit that scan to a small number of frames, set `stub_test=True`.
        """
        return self._timestamps or self.get_original_timestamps(stub_test=stub_test)

    def set_aligned_timestamps(self, aligned_timestamps: list[np.ndarray]):
        """
        Replace all timestamps for this interface with those aligned to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_timestamps : list of numpy.ndarray
            The synchronized timestamps for data in this interface.
        """
        assert (
            self._segment_starting_times is None
        ), "If setting both timestamps and starting times, please set the timestamps first so they can be shifted by the starting times."
        self._timestamps = aligned_timestamps

    def set_aligned_starting_time(self, aligned_starting_time: float, stub_test: bool = False):
        """
        Align all starting times for all videos in this interface relative to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_starting_time : float
            The common starting time for all segments of temporal data in this interface.
        stub_test : bool, default: False
            If timestamps have not been set to this interface, it will attempt to retrieve them
            using the `.get_original_timestamps` method, which scans through each video;
            a process which can take some time to complete.

            To limit that scan to a small number of frames, set `stub_test=True`.
        """
        if self._timestamps is not None:
            aligned_timestamps = [
                timestamps + aligned_starting_time for timestamps in self.get_timestamps(stub_test=stub_test)
            ]
            self.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)
        elif self._segment_starting_times is not None:
            self._segment_starting_times = [
                segment_starting_time + aligned_starting_time for segment_starting_time in self._segment_starting_times
            ]
        else:
            raise ValueError("There are no timestamps or starting times set to shift by a common value!")

    def set_aligned_segment_starting_times(self, aligned_segment_starting_times: list[float], stub_test: bool = False):
        """
        Align the individual starting time for each video (segment) in this interface relative to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_segment_starting_times : list of floats
            The relative starting times of each video.
        stub_test : bool, default: False
            If timestamps have not been set to this interface, it will attempt to retrieve them
            using the `.get_original_timestamps` method, which scans through each video;
            a process which can take some time to complete.

            To limit that scan to a small number of frames, set `stub_test=True`.
        """
        aligned_segment_starting_times_length = len(aligned_segment_starting_times)
        assert aligned_segment_starting_times_length == self._number_of_files, (
            f"The length of the 'aligned_segment_starting_times' list ({aligned_segment_starting_times_length}) does not match the "
            "number of video files ({self._number_of_files})!"
        )
        if self._timestamps is not None:
            self.set_aligned_timestamps(
                aligned_timestamps=[
                    timestamps + segment_starting_time
                    for timestamps, segment_starting_time in zip(
                        self.get_timestamps(stub_test=stub_test), aligned_segment_starting_times
                    )
                ]
            )
        else:
            self._segment_starting_times = aligned_segment_starting_times

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray):
        raise NotImplementedError("The `align_by_interpolation` method has not been developed for this interface yet.")

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        external_mode: bool = True,
        starting_frames: Optional[list[int]] = None,
        chunk_data: bool = True,
        module_name: Optional[str] = None,
        module_description: Optional[str] = None,
    ):
        """
        Convert the video data files to :py:class:`~pynwb.image.ImageSeries` and write them in the
        :py:class:`~pynwb.file.NWBFile`. Data is written in the :py:class:`~pynwb.image.ImageSeries` container as
        RGB. [times, x, y, 3-RGB].

        This method acts as a router, delegating the actual conversion to either InternalVideoInterface or
        ExternalVideoInterface based on the external_mode parameter.

        Parameters
        ----------
        nwbfile : NWBFile, optional
            nwb file to which the recording information is to be added
        metadata : dict, optional
            Dictionary of metadata information such as names and description of each video.
            Metadata should be passed for each video file passed in the file_paths.
            If storing as 'external mode', then provide duplicate metadata for video files that go in the
            same :py:class:`~pynwb.image.ImageSeries` container.
            Should be organized as follows::

                metadata = dict(
                    Behavior=dict(
                        Videos=[
                            dict(name="Video1", description="This is the first video.."),
                            dict(name="SecondVideo", description="Video #2 details..."),
                            ...
                        ]
                    )
                )

            and may contain most keywords normally accepted by an ImageSeries
            (https://pynwb.readthedocs.io/en/stable/pynwb.image.html#pynwb.image.ImageSeries).
            The list for the 'Videos' key should correspond one to the video files in the file_paths list.
            If multiple videos need to be in the same :py:class:`~pynwb.image.ImageSeries`, then supply the same value for "name" key.
            Storing multiple videos in the same :py:class:`~pynwb.image.ImageSeries` is only supported if 'external_mode'=True.
        stub_test : bool, default: False
            If ``True``, truncates the write operation for fast testing.
        external_mode : bool, default: True
            :py:class:`~pynwb.image.ImageSeries` may contain either video data or file paths to external video files.
            If True, this utilizes the more efficient method of writing the relative path to the video files (recommended).
        starting_frames : list, optional
            List of start frames for each video written using external mode.
            Required if more than one path is specified per ImageSeries in external mode.
        chunk_data : bool, default: True
            If True, uses a DataChunkIterator to read and write the video, reducing overhead RAM usage at the cost of
            reduced conversion speed (compared to loading video entirely into RAM as an array). This will also force to
            True, even if manually set to False, whenever the video file size exceeds available system RAM by a factor
            of 70 (from compression experiments). Based on experiments for a ~30 FPS system of ~400 x ~600 color
            frames, the equivalent uncompressed RAM usage is around 2GB per minute of video. The default is True.
        module_name: str, optional
            Name of the processing module to add the ImageSeries object to. Default behavior is to add as acquisition.
        module_description: str, optional
            If the processing module specified by module_name does not exist, it will be created with this description.
            The default description is the same as used by the conversion_tools.get_module function.
        """
        metadata = metadata or dict()
        file_paths = self.source_data["file_paths"]

        # Be sure to copy metadata at this step to avoid mutating in-place
        videos_metadata = deepcopy(metadata).get("Behavior", dict()).get(self.metadata_key_name, None)
        if videos_metadata is None:
            videos_metadata = deepcopy(self.get_metadata()["Behavior"][self.metadata_key_name])

        assert len(videos_metadata) == self._number_of_files, (
            "Incomplete metadata "
            f"(number of metadata in video {len(videos_metadata)})"
            f"is not equal to the number of file_paths {self._number_of_files}"
        )

        videos_name_list = [video["name"] for video in videos_metadata]
        any_duplicated_video_names = len(set(videos_name_list)) < len(videos_name_list)
        if any_duplicated_video_names:
            raise ValueError("There are duplicated file names in the metadata!")

        # Transform metadata from list format to nested dictionary format
        metadata_reformatted = deepcopy(metadata)
        if "Behavior" not in metadata_reformatted:
            metadata_reformatted["Behavior"] = dict()

        video_name = videos_metadata[0].pop("name")
        # Use appropriate metadata key based on external_mode
        if external_mode:
            metadata_reformatted["Behavior"]["ExternalVideos"] = {video_name: videos_metadata[0]}
        else:
            metadata_reformatted["Behavior"]["InternalVideos"] = {video_name: videos_metadata[0]}

        parent_container = "acquisition" if module_name is None else "processing/behavior"
        if parent_container == "processing/behavior":
            assert module_name == "behavior", f"module_name must be 'behavior' or None but got {module_name}."

        # Create the appropriate interface based on external_mode parameter
        if external_mode:
            # Use ExternalVideoInterface for external_mode=True
            # First convert metadata from old structure to the structure expected by ExternalVideoInterface
            external_interface = ExternalVideoInterface(
                file_paths=file_paths,
                verbose=self.verbose,
                video_name=video_name,
            )

            # Copy timing information
            if self._timestamps is not None:
                external_interface.set_aligned_timestamps(self._timestamps)
            elif self._segment_starting_times is not None:
                external_interface.set_aligned_segment_starting_times(self._segment_starting_times)

            # Call ExternalVideoInterface's add_to_nwbfile method
            return external_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata_reformatted,
                starting_frames=starting_frames,
                parent_container=parent_container,
                module_description=module_description,
            )

        # Use InternalVideoInterface for external_mode=False
        # Validate that we only have one file (required by InternalVideoInterface)
        if self._number_of_files > 1:
            raise NotImplementedError(
                "Multiple file_paths with external_mode=False is not supported! "
                "Please initialize a separate VideoInterface for each file."
            )

        # Create InternalVideoInterface
        internal_interface = InternalVideoInterface(
            file_path=file_paths[0],
            verbose=self.verbose,
            video_name=video_name,
        )

        # Copy timing information
        if self._timestamps is not None:
            internal_interface.set_aligned_timestamps(self._timestamps[0])
        elif self._segment_starting_times is not None:
            internal_interface.set_aligned_starting_time(self._segment_starting_times[0])

        # Call InternalVideoInterface's add_to_nwbfile method
        return internal_interface.add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata_reformatted,
            stub_test=stub_test,
            buffer_data=chunk_data,
            parent_container=parent_container,
            module_description=module_description,
        )
