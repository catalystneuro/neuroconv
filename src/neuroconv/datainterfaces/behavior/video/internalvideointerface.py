import warnings
from copy import deepcopy
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import psutil
from hdmf.data_utils import DataChunkIterator
from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.image import ImageSeries
from tqdm import tqdm

from .video_utils import VideoCaptureContext
from ....basedatainterface import BaseDataInterface
from ....tools import get_package
from ....tools.nwb_helpers import get_module
from ....utils import dict_deep_update, get_base_schema, get_schema_from_hdmf_class
from ....utils.str_utils import human_readable_size


class InternalVideoInterface(BaseDataInterface):
    """Data interface for writing videos as internally represented ImageSeries."""

    display_name = "Video"
    keywords = ("video",)
    associated_suffixes = (".mp4", ".avi", ".wmv", ".mov", ".flx", ".mkv")
    # Other suffixes, while they can be opened by OpenCV, are not supported by DANDI so should probably not list here
    info = "Interface for handling standard video file formats and writing them as ImageSeries with internal data."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = False,
        *,
        video_name: Optional[str] = None,
    ):
        """
        Initialize the interface.

        This interface handles a single video file and writes it as an internally represented ImageSeries. For writing
        videos as external files, use the ExternalVideoInterface.

        Parameters
        ----------
        file_path : FilePath
            The path to the video file.
        verbose : bool, optional
            If True, display verbose output. Defaults to False.
        video_name : str, optional
            The name of this video as it will appear in the ImageSeries.
            Defaults to f"Video {file_path.stem}" if not provided.

            This key is essential when multiple video streams are present in a single experiment.
            The associated metadata should be a nested dictionary structure, where each key
            corresponds to a video name, and each value is a dictionary containing metadata for that video:

            ```
            metadata["Behavior"]["InternalVideos"] = {
                "InternalVideo1": dict(description="description 1.", unit="Frames", **video1_metadata),
                "InternalVideo2": dict(description="description 2.", unit="Frames", **video2_metadata),
                ...
            }
            ```

            Where each entry corresponds to a separate VideoInterface and ImageSeries. Note, that
            metadata["Behavior"]["InternalVideos"] is specific to the InternalVideoInterface.
        """
        get_package(package_name="cv2", installation_instructions="pip install opencv-python-headless")
        self.verbose = verbose
        file_path = Path(file_path)
        self._timestamps = None
        self._starting_time = None
        self.video_name = video_name if video_name else f"Video {Path(file_path).stem}"
        self._default_device_name = f"{self.video_name} Camera Device"
        super().__init__(file_path=file_path)

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        image_series_metadata_schema = get_schema_from_hdmf_class(ImageSeries)
        # TODO: in future PR, add 'exclude' option to get_schema_from_hdmf_class to bypass this popping
        exclude = ["format", "conversion", "starting_time", "rate", "name"]
        for key in exclude:
            image_series_metadata_schema["properties"].pop(key)
            if key in image_series_metadata_schema["required"]:
                image_series_metadata_schema["required"].remove(key)
        device_metadata_schema = get_schema_from_hdmf_class(Device)
        image_series_metadata_schema["properties"]["device"] = device_metadata_schema
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        metadata_schema["properties"]["Behavior"]["required"].append("InternalVideos")
        metadata_schema["properties"]["Behavior"]["properties"]["InternalVideos"] = {
            "type": "object",
            "properties": {self.video_name: image_series_metadata_schema},
            "required": [self.video_name],
            "additionalProperties": True,
        }
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        video_metadata = {
            "Behavior": {
                "InternalVideos": {
                    self.video_name: dict(
                        description="Video recorded by camera.",
                        unit="Frames",
                        device=dict(name=self._default_device_name, description="Video camera used for recording."),
                    )
                }
            }
        }
        return dict_deep_update(metadata, video_metadata)

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
        file_path = self.source_data["file_path"]
        with VideoCaptureContext(file_path=str(file_path)) as video:
            # fps = video.get_video_fps()  # There is some debate about whether the OpenCV timestamp
            # method is simply returning range(length) / fps 100% of the time for any given format
            return video.get_video_timestamps(max_frames=max_frames)

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
        if self._timestamps is not None:
            return self._timestamps
        else:
            return self.get_original_timestamps(stub_test=stub_test)

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
        else:
            self._starting_time = aligned_starting_time

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray):
        raise NotImplementedError("The `align_by_interpolation` method has not been developed for this interface yet.")

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        buffer_data: bool = True,
        parent_container: Literal["acquisition", "processing/behavior"] = "acquisition",
        module_description: Optional[str] = None,
        always_write_timestamps: bool = False,
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
            Dictionary of metadata information such as name and description of the video, as well as
            device information for the camera that captured the video. The keys must correspond to
            the video_name specified in the constructor.
            Should be organized as follows::

                metadata = dict(
                    Behavior=dict(
                        InternalVideos=dict(
                            InternalVideo=dict(
                                description="Description of the video..",
                                device=dict(name="Camera name", description="Camera description", ...),
                                ...,
                            )
                        )
                    )
                )

            The InternalVideo section may contain most keywords normally accepted by an ImageSeries
            (https://pynwb.readthedocs.io/en/stable/pynwb.image.html#pynwb.image.ImageSeries).

            The device section may contain most keywords normally accepted by a Device
            (https://pynwb.readthedocs.io/en/stable/pynwb.device.html#pynwb.device.Device).

            The device will be created and linked to the ImageSeries, establishing a connection between
            the video data and the camera that captured it.
        stub_test : bool, default: False
            If ``True``, truncates the write operation for fast testing.
        buffer_data : bool, default: True
            If True, uses a DataChunkIterator to read and write the video, reducing overhead RAM usage at the cost of
            reduced conversion speed (compared to loading video entirely into RAM as an array). This will also force to
            True, even if manually set to False, whenever the video file size exceeds available system RAM by a factor
            of 70 (from compression experiments). Based on experiments for a ~30 FPS system of ~400 x ~600 color
            frames, the equivalent uncompressed RAM usage is around 2GB per minute of video. The default is True.
        parent_container: {'acquisition', 'processing/behavior'}
            The container where the ImageSeries is added, default is nwbfile.acquisition.
            When 'processing/behavior' is chosen, the ImageSeries is added to nwbfile.processing['behavior'].
        module_description: str, optional
            If parent_container is 'processing/behavior', and the module does not exist,
            it will be created with this description. The default description is the same as used by the
            conversion_tools.get_module function.
        always_write_timestamps: bool, default: False
            Set to True to always write timestamps.
            By default (False), the function checks if timestamps are available, and if not, uses starting_time and rate.
            If set to True, timestamps will be written explicitly, regardless of whether they were set directly or need
            to be retrieved from the video file.
        """
        if parent_container not in {"acquisition", "processing/behavior"}:
            raise ValueError(
                f"parent_container must be either 'acquisition' or 'processing/behavior', not {parent_container}."
            )
        metadata = metadata or dict()

        file_path = Path(self.source_data["file_path"])

        # Be sure to copy metadata at this step to avoid mutating in-place
        videos_metadata = deepcopy(metadata).get("Behavior", dict()).get("InternalVideos", None)
        # If no metadata is provided use the default metadata
        if videos_metadata is None or self.video_name not in videos_metadata:
            videos_metadata = deepcopy(self.get_metadata()["Behavior"]["InternalVideos"])
        image_series_kwargs = videos_metadata[self.video_name]
        image_series_kwargs["name"] = self.video_name
        device_kwargs = image_series_kwargs.pop("device", None)

        if device_kwargs is not None:
            if device_kwargs["name"] in nwbfile.devices:
                device = nwbfile.devices[device_kwargs["name"]]
            else:
                device = Device(**device_kwargs)
                nwbfile.add_device(device)
            image_series_kwargs["device"] = device

        stub_frames = 10

        uncompressed_estimate = file_path.stat().st_size * 70
        available_memory = psutil.virtual_memory().available
        if not buffer_data and not stub_test and uncompressed_estimate >= available_memory:
            warnings.warn(
                f"Not enough memory (estimated {human_readable_size(uncompressed_estimate)}) to load video file"
                f"as array ({human_readable_size(available_memory)} available)! Forcing buffer_data to True."
            )
            buffer_data = True
        with VideoCaptureContext(str(file_path)) as video_capture_ob:
            if stub_test:
                video_capture_ob.frame_count = stub_frames
            total_frames = video_capture_ob.get_video_frame_count()
            frame_shape = video_capture_ob.get_frame_shape()

        maxshape = (total_frames, *frame_shape)
        tqdm_pos, tqdm_mininterval = (0, 10)

        if buffer_data:
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

        from ....utils import calculate_regular_series_rate

        if always_write_timestamps:
            timestamps = self.get_timestamps()
            image_series_kwargs.update(timestamps=timestamps)
        elif self._timestamps is not None:
            # Check if timestamps are regular
            rate = calculate_regular_series_rate(series=self._timestamps)
            if rate is not None:
                starting_time = self._timestamps[0]
                image_series_kwargs.update(starting_time=starting_time, rate=rate)
            else:
                image_series_kwargs.update(timestamps=self._timestamps)
        else:
            starting_time = self._starting_time if self._starting_time is not None else 0.0
            with VideoCaptureContext(file_path=str(file_path)) as video:
                rate = video.get_video_fps()
            image_series_kwargs.update(starting_time=starting_time, rate=rate)

        # Attach image series
        image_series = ImageSeries(**image_series_kwargs)
        if parent_container == "acquisition":
            nwbfile.add_acquisition(image_series)
        elif parent_container == "processing/behavior":
            get_module(nwbfile=nwbfile, name="behavior", description=module_description).add(image_series)

        return nwbfile
