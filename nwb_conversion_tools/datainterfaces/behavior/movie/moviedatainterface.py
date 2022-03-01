"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
from typing import Optional
from warnings import warn

import psutil
import numpy as np
from hdmf.backends.hdf5.h5_utils import H5DataIO
from hdmf.data_utils import DataChunkIterator
from pynwb import NWBFile
from pynwb.image import ImageSeries
from tqdm import tqdm
from nwbinspector.utils import check_regular_series

from .movie_utils import VideoCaptureContext
from ....basedatainterface import BaseDataInterface
from ....tools.nwb_helpers import get_module
from ....utils import get_schema_from_hdmf_class, get_base_schema


class MovieInterface(BaseDataInterface):
    """Data interface for writing movies as ImageSeries."""

    def __init__(self, file_paths: list):
        """
        Create the interface for writing movies as ImageSeries.

        Parameters
        ----------
        file_paths : list of FilePathTypes
            Many movie storage formats segment a sequence of movies over the course of the experiment.
            Pass the file paths for this movies as a list in sorted, consecutive order.
        """
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
        metadata = dict(
            Behavior=dict(
                Movies=[
                    dict(name=f"Video: {Path(file_path).stem}", description="Video recorded by camera.", unit="Frames")
                    for file_path in self.source_data["file_paths"]
                ]
            )
        )
        return metadata

    def run_conversion(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        stub_test: bool = False,
        external_mode: bool = True,
        starting_times: Optional[list] = None,
        chunk_data: bool = True,
        module_name: Optional[str] = None,
        module_description: Optional[str] = None,
        compression: Optional[str] = "gzip",
        compression_options: Optional[int] = None,
    ):
        """
        Convert the movie data files to ImageSeries and write them in the NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
        metadata : dict
            Dictionary of metadata information such as names and description of each video.
            Should be organized as follows:
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
             The list for the 'Movies' key should correspond one to one to the movie files in the file_paths list.
             If multiple movies need to be in the same ImageSeries, then supply the same value for "name" key.
             Storing multiple movies in the same ImageSeries is only supported if 'external_mode'=True.
        stub_test : bool, optional
            If True, truncates the write operation for fast testing. The default is False.
        external_mode : bool, optional
            ImageSeries in NWBFiles may contain either explicit movie data or file paths to external movie files. If
            True, this utilizes the more efficient method of merely encoding the file path linkage (recommended). For
            data sharing, the video files must be contained in the same folder as the NWBFile. If the intention of this
            NWBFile involves an upload to DANDI, the non-NWBFile types are not allowed so this flag would have to be
            set to False. The default is True.
        starting_times : list, optional
            List of start times for each movie. If unspecified, assumes that the movies in the file_paths list are in
            sequential order and are contiguous.
        chunk_data : bool, optional
            If True, uses a DataChunkIterator to read and write the movie, reducing overhead RAM usage at the cost of
            reduced conversion speed (compared to loading video entirely into RAM as an array). This will also force to
            True, even if manually set to False, whenever the video file size exceeds available system RAM by a factor
            of 70 (from compression experiments). Based on experiements for a ~30 FPS system of ~400 x ~600 color
            frames, the equivalent uncompressed RAM usage is around 2GB per minute of video. The default is True.
        module_name: str, optional
            Name of the processing module to add the ImageSeries object to. Default behavior is to add as acquisition.
        module_description: str, optional
            If the processing module specified by module_name does not exist, it will be created with this description.
            The default description is the same as used by the conversion_tools.get_module function.
        compression: str, optional
            Compression strategy to use for HFDataIO. For full list of currently supported filters, see
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
        image_series_kwargs_list = metadata.get("Behavior", dict()).get(
            "Movies", self.get_metadata()["Behavior"]["Movies"]
        )
        assert len(image_series_kwargs_list) == len(self.source_data["file_paths"]), (
            "Mismatch in metadata dimensions "
            f"({len(image_series_kwargs_list)}) vs. file_paths ({len(self.source_data['file_paths'])})!"
        )

        def _check_duplicates(image_series_kwargs_list):
            image_series_kwargs_list_keys = [i["name"] for i in image_series_kwargs_list]
            if len(set(image_series_kwargs_list_keys)) < len(image_series_kwargs_list_keys):
                assert external_mode, "For multiple video files under the same ImageSeries name, use exernal_mode=True."
            keys_set = []
            image_series_kwargs_list_unique = []
            file_paths_list = []
            for n, image_series_kwargs in enumerate(image_series_kwargs_list):
                if image_series_kwargs["name"] not in keys_set:
                    keys_set.append(image_series_kwargs["name"])
                    file_paths_list.append([file_paths[n]])
                    image_series_kwargs_list_unique.append(dict(image_series_kwargs))
                else:
                    idx = keys_set.index(image_series_kwargs["name"])
                    file_paths_list[idx].append(file_paths[n])
            return image_series_kwargs_list_unique, file_paths_list

        image_series_kwargs_list_updated, file_paths_list = _check_duplicates(image_series_kwargs_list)
        if starting_times is not None:
            assert len(starting_times) == len(image_series_kwargs_list_updated), (
                "starting times list length must be equal number of unique ImageSeries " "containers to write to nwb"
            )
        else:
            if len(image_series_kwargs_list_updated) == 1:
                warn("starting_times not provided, setting to 0.0")
                starting_times = [0.0]
            else:
                raise ValueError("provide starting times as a list of len " f"{len(image_series_kwargs_list_updated)}")
        for j, (image_series_kwargs, file_list) in enumerate(zip(image_series_kwargs_list_updated, file_paths_list)):
            if external_mode:
                with VideoCaptureContext(str(file_list[0])) as vc:
                    fps = vc.get_movie_fps()
                image_series_kwargs.update(
                    starting_time=starting_times[j], rate=fps, format="external", external_file=file_list
                )
            else:
                file = file_list[0]
                uncompressed_estimate = Path(file).stat().st_size * 70
                available_memory = psutil.virtual_memory().available
                if not chunk_data and not stub_test and uncompressed_estimate >= available_memory:
                    warn(
                        f"Not enough memory (estimated {round(uncompressed_estimate/1e9, 2)} GB) to load movie file as "
                        f"array ({round(available_memory/1e9, 2)} GB available)! Forcing chunk_data to True."
                    )
                    chunk_data = True
                with VideoCaptureContext(str(file)) as video_capture_ob:
                    if stub_test:
                        video_capture_ob.frame_count = 10
                    total_frames = video_capture_ob.get_movie_frame_count()
                    frame_shape = video_capture_ob.get_frame_shape()
                    timestamps = starting_times[j] + video_capture_ob.get_movie_timestamps()
                    fps = video_capture_ob.get_movie_fps()
                maxshape = (total_frames, *frame_shape)
                best_gzip_chunk = (1, frame_shape[0], frame_shape[1], 3)
                tqdm_pos, tqdm_mininterval = (0, 10)
                if chunk_data:
                    video_capture_ob = VideoCaptureContext(str(file))
                    if stub_test:
                        video_capture_ob.frame_count = 10
                    iterable = DataChunkIterator(
                        data=tqdm(
                            iterable=video_capture_ob,
                            desc=f"Copying movie data for {Path(file).name}",
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
                            video_capture_ob.frame_count = 10
                        with tqdm(
                            desc=f"Reading movie data for {Path(file).name}",
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
                                desc=f"Writing movie data for {Path(file).name}",
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
                if check_regular_series(series=timestamps):
                    image_series_kwargs.update(starting_time=starting_times[j], rate=fps)
                else:
                    image_series_kwargs.update(timestamps=timestamps)
            if module_name is None:
                nwbfile.add_acquisition(ImageSeries(**image_series_kwargs))
            else:
                get_module(nwbfile=nwbfile, name=module_name, description=module_description).add(
                    ImageSeries(**image_series_kwargs)
                )
