from copy import deepcopy
from typing import Literal, Optional

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.image import ImageSeries

from .video_utils import VideoCaptureContext
from ....basedatainterface import BaseDataInterface
from ....tools import get_package
from ....tools.nwb_helpers import get_module
from ....utils import dict_deep_update, get_base_schema, get_schema_from_hdmf_class


class ExternalVideoInterface(BaseDataInterface):
    """Data interface for writing videos as external_file ImageSeries."""

    display_name = "Video"
    keywords = ("video", "behavior")
    associated_suffixes = (".mp4", ".avi", ".wmv", ".mov", ".flx", ".mkv")
    # Other suffixes, while they can be opened by OpenCV, are not supported by DANDI so should probably not list here
    info = "Interface for handling standard video file formats."

    @validate_call
    def __init__(
        self,
        file_paths: list[FilePath],
        verbose: bool = False,
        *,
        video_name: str = "Video1",
    ):
        """
        Initialize the interface.

        This interface handles multiple video segments and writes them as an ImageSeries with a link to external_file.
        For writing videos internally with just an ImageSeries object, use the InternalVideoInterface.

        Parameters
        ----------
        file_paths : list of FilePaths
            Many video storage formats segment a sequence of videos over the course of the experiment.
            Pass the file paths for this videos as a list in sorted, consecutive order.
        verbose : bool, optional
            If True, display verbose output. Defaults to False.
        video_name : str, optional
            The name of this video as it will appear in the ImageSeries.
            Defaults to "Video1".

            This key is essential when multiple video streams are present in a single experiment.
            The associated metadata should be a list of dictionaries, with each dictionary
            containing metadata for a single video stream comprised of potentially multiple segments:

            ```
            metadata["Behavior"]["Video"] = [
                dict(name="Video1", description="description 1.", unit="Frames", **video1_metadata),
                dict(name="Video2", description="description 2.", unit="Frames", **video2_metadata),
                ...
            ]
            ```

            Where each entry corresponds to a separate VideoInterface and ImageSeries. Note, that
            metadata["Behavior"]["Video"] is shared with the InternalVideoInterface.
        """
        get_package(package_name="cv2", installation_instructions="pip install opencv-python-headless")
        self.verbose = verbose
        self._number_of_files = len(file_paths)
        self._timestamps = None
        self._segment_starting_times = None
        self.video_name = video_name
        super().__init__(file_paths=file_paths)

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        image_series_metadata_schema = get_schema_from_hdmf_class(ImageSeries)
        # TODO: in future PR, add 'exclude' option to get_schema_from_hdmf_class to bypass this popping
        exclude = ["format", "conversion", "starting_time", "rate"]
        for key in exclude:
            image_series_metadata_schema["properties"].pop(key)
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        metadata_schema["properties"]["Behavior"]["required"].append("Video")
        metadata_schema["properties"]["Behavior"]["properties"]["Video"] = dict(
            type="array",
            minItems=1,
            items=image_series_metadata_schema,
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        video_metadata = {
            "Behavior": {"Video": [dict(name=self.video_name, description="Video recorded by camera.", unit="Frames")]}
        }
        return dict_deep_update(metadata, video_metadata)

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
        starting_frames: Optional[list[int]] = None,
        parent_container: Literal["acquisition", "processing/behavior"] = "acquisition",
        module_description: Optional[str] = None,
    ):
        """
        Convert the video data file(s) to :py:class:`~pynwb.image.ImageSeries` and write them in the
        :py:class:`~pynwb.file.NWBFile`. Data is written in a single :py:class:`~pynwb.image.ImageSeries` container with
        a path to each external file.

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
            Each dictionary in the list corresponds to a single VideoInterface and ImageSeries.
        starting_frames : list, optional
            List of start frames for each video written using external mode.
            Required if more than one path is specified.
        parent_container: {'acquisition', 'processing/behavior'}
            The container where the ImageSeries is added, default is nwbfile.acquisition.
            When 'processing/behavior' is chosen, the ImageSeries is added to nwbfile.processing['behavior'].
        module_description: str, optional
            If parent_container is 'processing/behavior', and the module does not exist,
            it will be created with this description. The default description is the same as used by the
            conversion_tools.get_module function.
        """
        metadata = metadata or dict()

        file_paths = self.source_data["file_paths"]

        # Be sure to copy metadata at this step to avoid mutating in-place
        videos_metadata = deepcopy(metadata).get("Behavior", dict()).get("Video", None)
        if videos_metadata is None:
            videos_metadata = deepcopy(self.get_metadata()["Behavior"]["Video"])
        image_series_kwargs = next(meta for meta in videos_metadata if meta["name"] == self.video_name)

        timing_type = self.get_timing_type()
        if self._number_of_files > 1 and starting_frames is None:
            raise TypeError("Multiple paths were specified for the ImageSeries, but no starting_frames were specified!")
        elif starting_frames is not None and len(starting_frames) != self._number_of_files:
            raise ValueError(
                f"Multiple paths ({self._number_of_files}) were specified for the ImageSeries, "
                f"but the length of starting_frames ({len(starting_frames)}) did not match the number of paths!"
            )
        elif starting_frames is not None:
            image_series_kwargs.update(starting_frame=starting_frames)

        image_series_kwargs.update(format="external", external_file=file_paths)

        if timing_type == "starting_time and rate":
            starting_time = self._segment_starting_times[0] if self._segment_starting_times is not None else 0.0
            with VideoCaptureContext(file_path=str(file_paths[0])) as video:
                rate = video.get_video_fps()
            image_series_kwargs.update(starting_time=starting_time, rate=rate)
        elif timing_type == "timestamps":
            image_series_kwargs.update(timestamps=np.concatenate(self._timestamps))
        else:
            raise ValueError(f"Unrecognized timing_type: {timing_type}")

        # Attach image series
        image_series = ImageSeries(**image_series_kwargs)
        if parent_container == "acquisition":
            nwbfile.add_acquisition(image_series)
        elif parent_container == "processing/behavior":
            get_module(nwbfile=nwbfile, name="behavior", description=module_description).add(image_series)
        else:
            raise ValueError(
                f"parent_container must be either 'acquisition' or 'processing/behavior', not {parent_container}."
            )

        return nwbfile
