"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
import numpy as np
from typing import Optional
from tqdm import tqdm
from warnings import warn

import psutil
from pynwb import NWBFile
from pynwb.image import ImageSeries
from hdmf.backends.hdf5.h5_utils import H5DataIO
from hdmf.data_utils import DataChunkIterator

from .movie_utils import get_movie_timestamps, get_movie_fps, get_frame_shape
from ....basedatainterface import BaseDataInterface
from ....utils.conversion_tools import check_regular_timestamps, get_module
from ....utils.json_schema import get_schema_from_hdmf_class, get_base_schema


try:
    import cv2

    HAVE_OPENCV = True
except ImportError:
    HAVE_OPENCV = False
INSTALL_MESSAGE = "Please install opencv to use this interface! (pip install opencv-python)"


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
        assert HAVE_OPENCV, INSTALL_MESSAGE
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
        """
        file_paths = self.source_data["file_paths"]

        if stub_test:
            count_max = 10
        else:
            count_max = np.inf
        if starting_times is not None:
            assert (
                isinstance(starting_times, list)
                and all([isinstance(x, float) for x in starting_times])
                and len(starting_times) == len(file_paths)
            ), "Argument 'starting_times' must be a list of floats in one-to-one correspondence with 'file_paths'!"
        else:
            starting_times = [0.0]

        image_series_kwargs_list = metadata.get("Behavior", dict()).get(
            "Movies", self.get_metadata()["Behavior"]["Movies"]
        )
        assert len(image_series_kwargs_list) == len(self.source_data["file_paths"]), (
            "Mismatch in metadata dimensions "
            f"({len(image_series_kwargs_list)}) vs. file_paths ({len(self.source_data['file_paths'])})!"
        )

        for j, file in enumerate(file_paths):
            timestamps = starting_times[j] + get_movie_timestamps(movie_file=file)

            if len(starting_times) != len(file_paths):
                starting_times.append(timestamps[-1])

            image_series_kwargs = dict(image_series_kwargs_list[j])
            if check_regular_timestamps(ts=timestamps):
                fps = get_movie_fps(movie_file=file)
                image_series_kwargs.update(starting_time=starting_times[j], rate=fps)
            else:
                image_series_kwargs.update(timestamps=H5DataIO(timestamps, compression="gzip"))

            if external_mode:
                image_series_kwargs.update(format="external", external_file=[file])
            else:
                uncompressed_estimate = Path(file).stat().st_size * 70
                available_memory = psutil.virtual_memory().available
                if not chunk_data and uncompressed_estimate >= available_memory:
                    warn(
                        f"Not enough memory (estimated {round(uncompressed_estimate/1e9, 2)} GB) to load movie file as "
                        f"array ({round(available_memory/1e9, 2)} GB available)! Forcing chunk_data to True."
                    )
                    chunk_data = True

                total_frames = len(timestamps)
                frame_shape = get_frame_shape(movie_file=file)
                maxshape = [total_frames]
                maxshape.extend(frame_shape)
                best_gzip_chunk = (1, frame_shape[0], frame_shape[1], 3)
                tqdm_pos, tqdm_mininterval = (0, 10)
                if chunk_data:

                    def data_generator(file, count_max):
                        cap = cv2.VideoCapture(str(file))
                        for _ in range(min(count_max, total_frames)):
                            success, frame = cap.read()
                            yield frame
                        cap.release()

                    mov = DataChunkIterator(
                        data=tqdm(
                            iterable=data_generator(file=file, count_max=count_max),
                            desc=f"Copying movie data for {Path(file).name}",
                            position=tqdm_pos,
                            total=total_frames,
                            mininterval=tqdm_mininterval,
                        ),
                        iter_axis=0,  # nwb standard is time as zero axis
                        maxshape=tuple(maxshape),
                    )
                    image_series_kwargs.update(data=H5DataIO(mov, compression="gzip", chunks=best_gzip_chunk))
                else:
                    cap = cv2.VideoCapture(str(file))
                    mov = []
                    with tqdm(
                        desc=f"Reading movie data for {Path(file).name}",
                        position=tqdm_pos,
                        total=total_frames,
                        mininterval=tqdm_mininterval,
                    ) as pbar:
                        for _ in range(min(count_max, total_frames)):
                            success, frame = cap.read()
                            mov.append(frame)
                            pbar.update(1)
                    cap.release()
                    image_series_kwargs.update(
                        data=H5DataIO(
                            DataChunkIterator(
                                tqdm(
                                    iterable=np.array(mov),
                                    desc=f"Writing movie data for {Path(file).name}",
                                    position=tqdm_pos,
                                    mininterval=tqdm_mininterval,
                                ),
                                iter_axis=0,  # nwb standard is time as zero axis
                                maxshape=tuple(maxshape),
                            ),
                            compression="gzip",
                            chunks=best_gzip_chunk,
                        )
                    )
            if module_name is None:
                nwbfile.add_acquisition(ImageSeries(**image_series_kwargs))
            else:
                get_module(nwbfile=nwbfile, name=module_name, description=module_description).add(
                    ImageSeries(**image_series_kwargs)
                )
