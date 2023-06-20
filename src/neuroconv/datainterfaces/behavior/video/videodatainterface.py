from pathlib import Path
from typing import List, Literal, Optional
from warnings import warn

import numpy as np
import psutil
from hdmf.backends.hdf5.h5_utils import H5DataIO
from hdmf.data_utils import DataChunkIterator
from pynwb import NWBFile
from pynwb.image import ImageSeries
from tqdm import tqdm

from .video_utils import VideoCaptureContext
from ....basedatainterface import BaseDataInterface
from ....tools import get_package
from ....tools.nwb_helpers import get_module
from ....utils import get_base_schema, get_schema_from_hdmf_class


class VideoInterface(BaseDataInterface):
    """Data interface for writing videos as ImageSeries."""

    def __init__(self, file_paths: list, verbose: bool = False):  # TODO - debug why List[FilePathType] fails
        """
        Create the interface for writing videos as ImageSeries.

        Parameters
        ----------
        file_paths : list of FilePathTypes
            Many video storage formats segment a sequence of videos over the course of the experiment.
            Pass the file paths for this videos as a list in sorted, consecutive order.
        """
        get_package(package_name="cv2", installation_instructions="pip install opencv-python-headless")
        self.verbose = verbose
        self._number_of_files = len(file_paths)
        self._timestamps = None
        self._segment_starting_times = None
        super().__init__(file_paths=file_paths)

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        image_series_metadata_schema = get_schema_from_hdmf_class(ImageSeries)
        # TODO: in future PR, add 'exclude' option to get_schema_from_hdmf_class to bypass this popping
        exclude = ["format", "conversion", "starting_time", "rate"]
        for key in exclude:
            image_series_metadata_schema["properties"].pop(key)
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        metadata_schema["properties"]["Behavior"].update(
            required=["Videos"],
            properties=dict(
                Videos=dict(
                    type="array",
                    minItems=1,
                    items=image_series_metadata_schema,
                )
            ),
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        behavior_metadata = dict(
            Videos=[
                dict(name=f"Video: {Path(file_path).stem}", description="Video recorded by camera.", unit="Frames")
                for file_path in self.source_data["file_paths"]
            ]
        )
        metadata["Behavior"] = behavior_metadata

        return metadata

    def get_original_timestamps(self, stub_test: bool = False) -> List[np.ndarray]:
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
        timing_type : 'starting_time and rate' or 'timestamps'
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

    def get_timestamps(self, stub_test: bool = False) -> List[np.ndarray]:
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

    def set_aligned_timestamps(self, aligned_timestamps: List[np.ndarray]):
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

    def set_aligned_segment_starting_times(self, aligned_segment_starting_times: List[float], stub_test: bool = False):
        """
        Align the individual starting time for each video (segment) in this interface relative to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        starting_times : list of floats
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
        starting_frames: Optional[list] = None,
        chunk_data: bool = True,
        module_name: Optional[str] = None,
        module_description: Optional[str] = None,
        compression: Optional[str] = "gzip",
        compression_options: Optional[int] = None,
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
        compression: str, default: "gzip"
            Compression strategy to use for :py:class:`hdmf.backends.hdf5.h5_utils.H5DataIO`. For full list of currently
            supported filters, see
            https://docs.h5py.org/en/latest/high/dataset.html#lossless-compression-filters
        compression_options: int, optional
            Parameter(s) for compression filter. Currently, only supports the compression level (integer from 0 to 9) of
            compression="gzip".
        """
        metadata = metadata or dict()

        file_paths = self.source_data["file_paths"]

        videos_metadata = metadata.get("Behavior", dict()).get("Videos", None)
        if videos_metadata is None:
            videos_metadata = self.get_metadata()["Behavior"]["Videos"]

        assert len(videos_metadata) == self._number_of_files, (
            "Incomplete metadata "
            f"(number of metadata in video {len(videos_metadata)})"
            f"is not equal to the number of file_paths {self._number_of_files}"
        )

        videos_name_list = [video["name"] for video in videos_metadata]
        any_duplicated_video_names = len(set(videos_name_list)) < len(videos_name_list)
        if any_duplicated_video_names:
            raise ValueError("There are duplicated file names in the metadata!")

        # Iterate over unique videos
        stub_frames = 10
        timing_type = self.get_timing_type()
        if external_mode:
            image_series_kwargs = videos_metadata[0]
            if self._number_of_files > 1 and starting_frames is None:
                raise TypeError(
                    "Multiple paths were specified for the ImageSeries, but no starting_frames were specified!"
                )
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
        else:
            for file_index, (image_series_kwargs, file) in enumerate(zip(videos_metadata, file_paths)):
                if self._number_of_files > 1:
                    raise NotImplementedError(
                        "Multiple file_paths with external_mode=False is not yet supported! "
                        "Please initialize a separate VideoInterface for each file."
                    )

                uncompressed_estimate = Path(file).stat().st_size * 70
                available_memory = psutil.virtual_memory().available
                if not chunk_data and not stub_test and uncompressed_estimate >= available_memory:
                    warn(
                        f"Not enough memory (estimated {round(uncompressed_estimate/1e9, 2)} GB) to load video file as "
                        f"array ({round(available_memory/1e9, 2)} GB available)! Forcing chunk_data to True."
                    )
                    chunk_data = True
                with VideoCaptureContext(str(file)) as video_capture_ob:
                    if stub_test:
                        video_capture_ob.frame_count = stub_frames
                    total_frames = video_capture_ob.get_video_frame_count()
                    frame_shape = video_capture_ob.get_frame_shape()

                maxshape = (total_frames, *frame_shape)
                tqdm_pos, tqdm_mininterval = (0, 10)

                if chunk_data:
                    chunks = (1, frame_shape[0], frame_shape[1], 3)  # best_gzip_chunk
                    video_capture_ob = VideoCaptureContext(str(file))
                    if stub_test:
                        video_capture_ob.frame_count = stub_frames
                    iterable = DataChunkIterator(
                        data=tqdm(
                            iterable=video_capture_ob,
                            desc=f"Copying video data for {Path(file).name}",
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
                    with VideoCaptureContext(str(file)) as video_capture_ob:
                        if stub_test:
                            video_capture_ob.frame_count = stub_frames
                        with tqdm(
                            desc=f"Reading video data for {Path(file).name}",
                            position=tqdm_pos,
                            total=total_frames,
                            mininterval=tqdm_mininterval,
                        ) as pbar:
                            for n, frame in enumerate(video_capture_ob):
                                video[n, :, :, :] = frame
                                pbar.update(1)
                    iterable = video

                # Wrap data for compression
                wrapped_io_data = H5DataIO(
                    iterable,
                    compression=compression,
                    compression_opts=compression_options,
                    chunks=chunks,
                )
                image_series_kwargs.update(data=wrapped_io_data)

                if timing_type == "starting_time and rate":
                    starting_time = (
                        self._segment_starting_times[file_index] if self._segment_starting_times is not None else 0.0
                    )
                    with VideoCaptureContext(file_path=str(file)) as video:
                        rate = video.get_video_fps()
                    image_series_kwargs.update(starting_time=starting_time, rate=rate)
                elif timing_type == "timestamps":
                    image_series_kwargs.update(timestamps=self._timestamps[file_index])

        # Attach image series
        image_series = ImageSeries(**image_series_kwargs)
        if module_name is None:
            nwbfile.add_acquisition(image_series)
        else:
            get_module(nwbfile=nwbfile, name=module_name, description=module_description).add(image_series)

        return nwbfile
