import warnings
from copy import deepcopy
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import psutil
from hdmf.data_utils import DataChunkIterator
from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.image import ImageSeries
from tqdm import tqdm

from .video_utils import VideoCaptureContext
from ....basedatainterface import BaseDataInterface
from ....tools import get_package
from ....tools.nwb_helpers import get_module
from ....utils import dict_deep_update, get_base_schema, get_schema_from_hdmf_class
from ....utils.str_utils import human_readable_size


class InternalVideoInterface(BaseDataInterface):
    """Data interface for writing videos as ImageSeries."""

    display_name = "Video"
    keywords = ("movie", "natural behavior", "tracking")
    associated_suffixes = (".mp4", ".avi", ".wmv", ".mov", ".flx", ".mkv")
    # Other suffixes, while they can be opened by OpenCV, are not supported by DANDI so should probably not list here
    info = "Interface for handling standard video file formats."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = False,
        *,
        video_name: str = "Video1",
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
        get_package(package_name="cv2", installation_instructions="pip install opencv-python-headless")
        self.verbose = verbose
        self._timestamps = None
        self.video_name = video_name
        super().__init__(file_path=file_path)

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
        dict_deep_update(metadata, video_metadata)
        return metadata

    def get_original_timestamps(self, stub_test: bool = False) -> np.ndarray:
        """
        Retrieve the original unaltered timestamps for the data in this interface.

        This function should retrieve the data on-demand by re-initializing the IO.

        Parameters
        ----------
        stub_test : bool, default: False
            If True, limits the number of frames to scan through to 10.

        Returns
        -------
        timestamps : numpy.ndarray
            The timestamps for the data stream.
        """
        max_frames = 10 if stub_test else None
        file_path = self.source_data["file_paths"]
        with VideoCaptureContext(file_path=str(file_path)) as video:
            # fps = video.get_video_fps()  # There is some debate about whether the OpenCV timestamp
            # method is simply returning range(length) / fps 100% of the time for any given format
            return video.get_video_timestamps(max_frames=max_frames)

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
        else:
            return "starting_time and rate"  # default behavior assumes data is pre-aligned; starting_times = [0.0]

    def get_timestamps(self, stub_test: bool = False) -> np.ndarray:
        """
        Retrieve the timestamps for the data in this interface.

        Parameters
        ----------
        stub_test : bool, default: False
            If True, limits the number of frames to scan through to 10.

        Returns
        -------
        timestamps : numpy.ndarray
            The timestamps for the data stream.
        """
        return self._timestamps or self.get_original_timestamps(stub_test=stub_test)

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        """
        Replace all timestamps for this interface with those aligned to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_timestamps : numpy.ndarray
            The synchronized timestamps for data in this interface.
        """
        assert (
            self._starting_time is None
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
            aligned_timestamps = self.get_timestamps(stub_test=stub_test) + aligned_starting_time
            self.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)
        elif self._starting_time is not None:
            self._starting_time = self._starting_time + aligned_starting_time
        else:
            raise ValueError("There are no timestamps or starting times set to shift by a common value!")

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray):
        raise NotImplementedError("The `align_by_interpolation` method has not been developed for this interface yet.")

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        chunk_data: bool = True,
        module_name: Optional[str] = None,
        module_description: Optional[str] = None,
    ):
        """
        Convert the video data files to :py:class:`~pynwb.image.ImageSeries` and write them in the
        :py:class:`~pynwb.file.NWBFile`. Data is written in the :py:class:`~pynwb.image.ImageSeries` container as
        RGB. [times, x, y, 3-RGB].

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
        stub_test : bool, default: False
            If ``True``, truncates the write operation for fast testing.
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

        file_path = Path(self.source_data["file_path"])

        # Be sure to copy metadata at this step to avoid mutating in-place
        videos_metadata = deepcopy(metadata).get("Behavior", dict()).get("Video", None)
        if videos_metadata is None:
            videos_metadata = deepcopy(self.get_metadata()["Behavior"]["Video"])
        image_series_kwargs = next(meta for meta in videos_metadata if meta["name"] == self.video_name)

        stub_frames = 10
        timing_type = self.get_timing_type()

        uncompressed_estimate = file_path.stat().st_size * 70
        available_memory = psutil.virtual_memory().available
        if not chunk_data and not stub_test and uncompressed_estimate >= available_memory:
            warnings.warn(
                f"Not enough memory (estimated {human_readable_size(uncompressed_estimate)}) to load video file"
                f"as array ({human_readable_size(available_memory)} available)! Forcing chunk_data to True."
            )
            chunk_data = True
        with VideoCaptureContext(str(file_path)) as video_capture_ob:
            if stub_test:
                video_capture_ob.frame_count = stub_frames
            total_frames = video_capture_ob.get_video_frame_count()
            frame_shape = video_capture_ob.get_frame_shape()

        maxshape = (total_frames, *frame_shape)
        tqdm_pos, tqdm_mininterval = (0, 10)

        if chunk_data:
            chunks = (1, frame_shape[0], frame_shape[1], 3)  # best_gzip_chunk
            video_capture_ob = VideoCaptureContext(str(file_path))
            if stub_test:
                video_capture_ob.frame_count = stub_frames
            iterable = DataChunkIterator(
                data=tqdm(
                    iterable=video_capture_ob,
                    desc=f"Copying video data for {file_path.name}",
                    position=tqdm_pos,
                    total=total_frames,
                    mininterval=tqdm_mininterval,
                ),
                iter_axis=0,  # nwb standard is time as zero axis
                maxshape=maxshape,
            )

        else:
            # Load the video
            chunks = None
            video = np.zeros(shape=maxshape, dtype="uint8")
            with VideoCaptureContext(str(file_path)) as video_capture_ob:
                if stub_test:
                    video_capture_ob.frame_count = stub_frames
                with tqdm(
                    desc=f"Reading video data for {Path(file_path).name}",
                    position=tqdm_pos,
                    total=total_frames,
                    mininterval=tqdm_mininterval,
                ) as pbar:
                    for n, frame in enumerate(video_capture_ob):
                        video[n, :, :, :] = frame
                        pbar.update(1)
            iterable = video

        image_series_kwargs.update(data=iterable)

        if timing_type == "starting_time and rate":
            starting_time = self._starting_time if self._starting_time is not None else 0.0
            with VideoCaptureContext(file_path=str(file_path)) as video:
                rate = video.get_video_fps()
            image_series_kwargs.update(starting_time=starting_time, rate=rate)
        elif timing_type == "timestamps":
            image_series_kwargs.update(timestamps=self._timestamps)

        # Attach image series
        image_series = ImageSeries(**image_series_kwargs)
        if module_name is None:
            nwbfile.add_acquisition(image_series)
        else:
            get_module(nwbfile=nwbfile, name=module_name, description=module_description).add(image_series)

        return nwbfile
