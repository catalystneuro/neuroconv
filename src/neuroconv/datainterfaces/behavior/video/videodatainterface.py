"""Authors: Heberto Mayorquin, Saksham Sharda, Cody Baker and Ben Dichter."""
from logging import warning
from pathlib import Path
from typing import Optional, List
from warnings import warn
import warnings
import psutil

import numpy as np
from hdmf.backends.hdf5.h5_utils import H5DataIO
from hdmf.data_utils import DataChunkIterator
from pynwb import NWBFile
from pynwb.image import ImageSeries
from tqdm import tqdm

from .video_utils import VideoCaptureContext
from ....basedatainterface import BaseDataInterface
from ....tools import get_package
from ....tools.nwb_helpers import get_module, make_or_load_nwbfile
from ....utils import get_schema_from_hdmf_class, get_base_schema, calculate_regular_series_rate, OptionalFilePathType


def _check_duplicates(videos_metadata, file_paths):
    """
    Accumulates metadata for when multiple video files go in one ImageSeries container.

    Parameters
    ----------
    videos_metadata: List[Dict]
        The metadata corresponding to the videos should be organized as follow
                videos_metadata =[
                            dict(name="Video1", description="This is the first video.."),
                            dict(name="SecondVideo", description="Video #2 details..."),
                ]
    -------
    videos_metadata_unique: List[Dict]
        if metadata has common names (case when the user intends to put multiple video files
        under the same ImageSeries container), this removes the duplicate names.
    file_paths_list: List[List[str]]
        len(file_paths_list)==len(videos_metadata_unique)
    """
    keys_set = []
    videos_metadata_unique = []
    file_paths_list = []
    for n, video in enumerate(videos_metadata):
        if video["name"] not in keys_set:
            keys_set.append(video["name"])
            file_paths_list.append([file_paths[n]])
            videos_metadata_unique.append(dict(video))
        else:
            idx = keys_set.index(video["name"])
            file_paths_list[idx].append(file_paths[n])

    return videos_metadata_unique, file_paths_list


class VideoInterface(BaseDataInterface):
    """Data interface for writing videos as ImageSeries."""

    def __init__(self, file_paths: list, verbose: bool = False):
        """
        Create the interface for writing videos as ImageSeries.

        Parameters
        ----------
        file_paths : list of FilePathTypes
            Many video storage formats segment a sequence of videos over the course of the experiment.
            Pass the file paths for this videos as a list in sorted, consecutive order.
        """
        get_package(package_name="cv2", installation_instructions="pip install opencv-python")
        self.verbose = verbose
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
            required=["Movies"],
            properties=dict(
                Movies=dict(
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
            Movies=[
                dict(name=f"Video: {Path(file_path).stem}", description="Video recorded by camera.", unit="Frames")
                for file_path in self.source_data["file_paths"]
            ]
        )
        metadata["Behavior"] = behavior_metadata

        return metadata

    def run_conversion(
        self,
        nwbfile_path: OptionalFilePathType = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        stub_test: bool = False,
        external_mode: bool = True,
        starting_times: Optional[list] = None,
        starting_frames: Optional[list] = None,
        timestamps: Optional[list] = None,
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
        nwbfile_path: FilePathType
            Path for where to write or load (if overwrite=False) the NWBFile.
            If specified, this context will always write to this location.
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata : dict
            Dictionary of metadata information such as names and description of each video.
            Metadata should be passed for each video file passed in the file_paths argument during ``__init__``.
            If storing as 'external mode', then provide duplicate metadata for video files that go in the
            same :py:class:`~pynwb.image.ImageSeries` container. ``len(metadata["Behavior"]["Movies"]==len(file_paths)``.
            Should be organized as follows::

                metadata = dict(
                    Behavior=dict(
                        Movies=[
                            dict(name="Video1", description="This is the first video.."),
                            dict(name="SecondVideo", description="Video #2 details..."),
                            ...
                        ]
                    )
                )
            and may contain most keywords normally accepted by an ImageSeries
            (https://pynwb.readthedocs.io/en/stable/pynwb.image.html#pynwb.image.ImageSeries).
            The list for the 'Movies' key should correspond one to the video files in the file_paths list.
            If multiple videos need to be in the same :py:class:`~pynwb.image.ImageSeries`, then supply the same value for "name" key.
            Storing multiple videos in the same :py:class:`~pynwb.image.ImageSeries` is only supported if 'external_mode'=True.
        overwrite: bool, optional
            Whether or not to overwrite the NWBFile if one exists at the nwbfile_path.
        stub_test : bool
            If ``True``, truncates the write operation for fast testing. The default is ``False``.
        external_mode : bool
            :py:class:`~pynwb.image.ImageSeries` may contain either video data or file paths to external video files.
            If True, this utilizes the more efficient method of writing the relative path to the video files (recommended).
        starting_times : list, optional
            List of start times for each video. If unspecified, assumes that the videos in the file_paths list are in
            sequential order and are contiguous.
        starting_frames : list, optional
            List of start frames for each video written using external mode.
            Required if more than one path is specified per ImageSeries in external mode.
        timestamps : list, optional
            List of timestamps for the videos. If unspecified, timestamps are extracted from each video data.
        chunk_data : bool
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
        compression: str, optional
            Compression strategy to use for :py:class:`hdmf.backends.hdf5.h5_utils.H5DataIO`. For full list of currently
            supported filters, see
            https://docs.h5py.org/en/latest/high/dataset.html#lossless-compression-filters
        compression_options: int, optional
            Parameter(s) for compression filter. Currently only supports the compression level (integer from 0 to 9) of
            compression="gzip".
        """
        file_paths = self.source_data["file_paths"]

        if starting_times is not None:
            assert isinstance(starting_times, list) and all(
                [isinstance(x, float) for x in starting_times]
            ), "Argument 'starting_times' must be a list of floats."

        videos_metadata = metadata.get("Behavior", dict()).get("Movies", None)
        if videos_metadata is None:
            videos_metadata = self.get_metadata()["Behavior"]["Movies"]

        number_of_file_paths = len(file_paths)
        assert len(videos_metadata) == number_of_file_paths, (
            "Incomplete metadata "
            f"(number of metadata in video {len(videos_metadata)})"
            f"is not equal to the number of file_paths {number_of_file_paths}"
        )

        videos_name_list = [video["name"] for video in videos_metadata]
        some_video_names_are_not_unique = len(set(videos_name_list)) < len(videos_name_list)
        if some_video_names_are_not_unique:
            assert external_mode, "For multiple video files under the same ImageSeries name, use exernal_mode=True."

        videos_metadata_unique, file_paths_list = _check_duplicates(videos_metadata, file_paths)

        if starting_times is not None:
            assert len(starting_times) == len(videos_metadata_unique), (
                f"starting times list length {len(starting_times)} must be equal to number of unique "
                f"ImageSeries {len(videos_metadata_unique)} \n"
                f"Movies metadata provided as input {videos_metadata} \n"
                f"starting times = {starting_times} \n"
                f"Image series after _check_duplicates {videos_metadata_unique}"
            )
        else:
            if len(videos_metadata_unique) == 1:
                warn("starting_times not provided, setting to 0.0")
                starting_times = [0.0]
            else:
                raise ValueError("provide starting times as a list of len " f"{len(videos_metadata_unique)}")

        # Iterate over unique videos
        stub_frames = 10
        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=self.verbose
        ) as nwbfile_out:
            for j, (image_series_kwargs, file_list) in enumerate(zip(videos_metadata_unique, file_paths_list)):

                with VideoCaptureContext(str(file_list[0])) as vc:
                    fps = vc.get_video_fps()
                    max_frames = stub_frames if stub_test else None
                    extracted_timestamps = vc.get_video_timestamps(max_frames)
                    video_timestamps = (
                        starting_times[j] + extracted_timestamps if timestamps is None else timestamps[:max_frames]
                    )

                if external_mode:
                    num_files = len(file_list)
                    if num_files > 1 and starting_frames is None:
                        raise TypeError(
                            f"Multiple paths were specified for ImageSeries index {j}, but no starting_frames were specified!"
                        )
                    elif num_files > 1 and num_files != len(starting_frames[j]):
                        raise ValueError(
                            f"Multiple paths ({num_files}) were specified for ImageSeries index {j}, "
                            f"but the length of starting_frames ({len(starting_frames[j])}) did not match the number of paths!"
                        )
                    elif num_files > 1:
                        image_series_kwargs.update(starting_frame=starting_frames[j])

                    image_series_kwargs.update(
                        format="external",
                        external_file=file_list,
                    )
                else:
                    file = file_list[0]
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
                    best_gzip_chunk = (1, frame_shape[0], frame_shape[1], 3)
                    tqdm_pos, tqdm_mininterval = (0, 10)
                    if chunk_data:
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
                        data = H5DataIO(
                            iterable,
                            compression=compression,
                            compression_opts=compression_options,
                            chunks=best_gzip_chunk,
                        )
                    else:
                        iterable = np.zeros(shape=maxshape, dtype="uint8")
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
                                    iterable[n, :, :, :] = frame
                                    pbar.update(1)
                        data = H5DataIO(
                            DataChunkIterator(
                                tqdm(
                                    iterable=iterable,
                                    desc=f"Writing video data for {Path(file).name}",
                                    position=tqdm_pos,
                                    mininterval=tqdm_mininterval,
                                ),
                                iter_axis=0,  # nwb standard is time as zero axis
                                maxshape=maxshape,
                            ),
                            compression="gzip",
                            compression_opts=compression_options,
                            chunks=best_gzip_chunk,
                        )
                    image_series_kwargs.update(data=data)

                # Store sampling rate if timestamps are regular
                rate = calculate_regular_series_rate(series=video_timestamps)
                if rate is not None:
                    if fps != rate:
                        warn(
                            f"The fps={fps:.2g} from video data is unequal to the difference in "
                            f"regular timestamps. Using fps={rate:.2g} from timestamps instead.",
                            UserWarning,
                        )
                    image_series_kwargs.update(starting_time=starting_times[j], rate=rate)
                else:
                    image_series_kwargs.update(timestamps=video_timestamps)

                # Attach image series
                image_series = ImageSeries(**image_series_kwargs)

                if module_name is None:
                    nwbfile_out.add_acquisition(image_series)
                else:
                    get_module(nwbfile=nwbfile_out, name=module_name, description=module_description).add(image_series)

        return nwbfile_out


class MovieInterface(VideoInterface):
    def __init__(self, file_paths: list, verbose: bool = False):
        super().__init__(file_paths, verbose)
        warnings.warn(
            "MovieInterface is to be deprecated after April 2023, use VideoInterface instead", DeprecationWarning
        )
