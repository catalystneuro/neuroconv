"""General purpose iterator for all ImagingExtractor data."""

import math

import numpy as np
from roiextractors import ImagingExtractor
from tqdm import tqdm

from neuroconv.tools.hdmf import GenericDataChunkIterator


class ImagingExtractorDataChunkIterator(GenericDataChunkIterator):
    """DataChunkIterator for ImagingExtractor objects primarily used when writing imaging data to an NWB file."""

    def __init__(
        self,
        imaging_extractor: ImagingExtractor,
        buffer_gb: float | None = None,
        buffer_shape: tuple | None = None,
        chunk_mb: float | None = None,
        chunk_shape: tuple | None = None,
        display_progress: bool = False,
        progress_bar_class: tqdm | None = None,
        progress_bar_options: dict | None = None,
    ):
        """
        Initialize an Iterable object which returns DataChunks with data and their selections on each iteration.

        Parameters
        ----------
        imaging_extractor : ImagingExtractor
            The ImagingExtractor object which handles the data access.
        buffer_gb : float, optional
            The upper bound on size in gigabytes (GB) of each selection from the iteration.
            The buffer_shape will be set implicitly by this argument.
            Cannot be set if `buffer_shape` is also specified.
            The default is 1GB.
        buffer_shape : tuple, optional
            Manual specification of buffer shape to return on each iteration.
            Must be a multiple of chunk_shape along each axis.
            Cannot be set if `buffer_gb` is also specified.
            The default is None.
        chunk_mb : float, optional
            The upper bound on size in megabytes (MB) of the internal chunk for the HDF5 dataset.
            The chunk_shape will be set implicitly by this argument.
            Cannot be set if `chunk_shape` is also specified.
            The default is 10MB, as recommended by the HDF5 group.
            For more details, search the hdf5 documentation for "Improving IO Performance Compressed Datasets".
        chunk_shape : tuple, optional
            Manual specification of the internal chunk shape for the HDF5 dataset.
            Cannot be set if `chunk_mb` is also specified.
            The default is None.
        display_progress : bool, default=False
            Display a progress bar with iteration rate and estimated completion time.
        progress_bar_class : dict, optional
            The progress bar class to use.
            Defaults to tqdm.tqdm if the TQDM package is installed.
        progress_bar_options : dict, optional
            Dictionary of keyword arguments to be passed directly to tqdm.
            See https://github.com/tqdm/tqdm#parameters for options.
        """
        self.imaging_extractor = imaging_extractor

        assert not (buffer_gb and buffer_shape), "Only one of 'buffer_gb' or 'buffer_shape' can be specified!"
        assert not (chunk_mb and chunk_shape), "Only one of 'chunk_mb' or 'chunk_shape' can be specified!"

        if chunk_mb and buffer_gb:
            assert chunk_mb * 1e6 <= buffer_gb * 1e9, "chunk_mb must be less than or equal to buffer_gb!"

        if chunk_mb is None and chunk_shape is None:
            chunk_mb = 10.0

        self._maxshape = self._get_maxshape()
        self._dtype = self._get_dtype()
        if chunk_shape is None:
            chunk_shape = self._get_default_chunk_shape(chunk_mb=chunk_mb)

        if buffer_gb is None and buffer_shape is None:
            buffer_gb = 1.0

        if buffer_shape is None:
            buffer_shape = self._get_scaled_buffer_shape(buffer_gb=buffer_gb, chunk_shape=chunk_shape)

        super().__init__(
            buffer_shape=buffer_shape,
            chunk_shape=chunk_shape,
            display_progress=display_progress,
            progress_bar_class=progress_bar_class,
            progress_bar_options=progress_bar_options,
        )

    def _get_default_chunk_shape(self, chunk_mb: float) -> tuple:
        """Select the chunk_shape less than the threshold of chunk_mb while keeping the original image size."""
        assert chunk_mb > 0, f"chunk_mb ({chunk_mb}) must be greater than zero!"

        num_frames = self._maxshape[0]
        width = int(self._maxshape[1])
        height = int(self._maxshape[2])
        if len(self._maxshape) == 4:
            num_planes = int(self._maxshape[3])
        else:
            num_planes = None

        chunk_shape = get_two_photon_series_chunk_shape(
            num_frames=num_frames,
            width=width,
            height=height,
            dtype=self._dtype,
            num_planes=num_planes,
            chunk_mb=chunk_mb,
        )

        return chunk_shape

    def _get_scaled_buffer_shape(self, buffer_gb: float, chunk_shape: tuple) -> tuple:
        """Select the buffer_shape less than the threshold of buffer_gb that is also a multiple of the chunk_shape."""
        assert buffer_gb > 0, f"buffer_gb ({buffer_gb}) must be greater than zero!"
        assert all(np.array(chunk_shape) > 0), f"Some dimensions of chunk_shape ({chunk_shape}) are less than zero!"

        series_max_shape = self._get_maxshape()[1:]
        min_buffer_shape = tuple([chunk_shape[0]]) + series_max_shape

        # Calculate scaling factor based on buffer size and data type
        bytes_per_element = self._get_dtype().itemsize
        min_buffer_size = math.prod(min_buffer_shape) * bytes_per_element
        scaling_factor = math.floor((buffer_gb * 1e9) / min_buffer_size)

        # Determine maximum buffer shape with scaling factor
        max_buffer_shape = tuple([int(scaling_factor * min_buffer_shape[0])]) + series_max_shape

        scaled_buffer_shape = []
        maxshape = self._get_maxshape()

        for dimension_index, dimension_length in enumerate(max_buffer_shape):
            min_size = chunk_shape[dimension_index]
            max_size = maxshape[dimension_index]
            scaled_size = max(int(dimension_length), min_size)
            scaled_size = min(scaled_size, max_size)
            scaled_buffer_shape.append(scaled_size)

        return tuple(scaled_buffer_shape)

    def _get_dtype(self) -> np.dtype:
        return self.imaging_extractor.get_dtype()

    def _get_maxshape(self) -> tuple:

        max_series_shape = self.imaging_extractor.get_sample_shape()

        num_samples = self.imaging_extractor.get_num_samples()
        height = max_series_shape.shape[1]
        width = max_series_shape.shape[2]

        if len(max_series_shape.shape) == 3:
            sample_shape = (num_samples, width, height)
        else:
            num_planes = max_series_shape.shape[3]
            sample_shape = (num_samples, width, height, num_planes)

        return sample_shape

    def _get_data(self, selection: tuple[slice]) -> np.ndarray:
        data = self.imaging_extractor.get_series(
            start_sample=selection[0].start,
            end_sample=selection[0].stop,
        )
        tranpose_axes = (0, 2, 1) if len(data.shape) == 3 else (0, 2, 1, 3)
        sliced_selection = (slice(0, self.buffer_shape[0]),) + selection[1:]

        return data.transpose(tranpose_axes)[sliced_selection]


def get_two_photon_series_chunk_shape(
    num_frames: int,
    width: int,
    height: int,
    dtype: np.dtype,
    num_planes: int | None = None,
    chunk_mb: float = 10.0,
) -> tuple[int, int]:
    """
    Estimate good chunk shape for a TwoPhotonSeries dataset.

    This function gives good estimates for cloud access patterns.

    Parameters
    ----------
    num_frames : int
        The number of frames in the TwoPhotonSeries dataset.
    width : int
        The width of the TwoPhotonSeries dataset.
    height : int
        The height of the TwoPhotonSeries dataset.
    dtype : np.dtype
        The data type of the TwoPhotonSeries dataset.
    num_planes : int,
        The number of planes in the TwoPhotonSeries dataset.
        The default is None.
    chunk_mb : float, optional
        The upper bound on size in megabytes (MB) of the internal chunk for the HDF5 dataset.
        The default is 10MB, as recommended by the HDF5 group.

    Returns
    -------
    tuple[int, int, int] | tuple[int, int, int, int]
        The chunk shape for the TwoPhotonSeries dataset.
    """
    assert chunk_mb > 0, f"chunk_mb ({chunk_mb}) must be greater than zero!"

    frame_size_bytes = width * height * dtype.itemsize
    chunk_size_bytes = chunk_mb * 1e6
    num_frames_per_chunk = int(chunk_size_bytes / frame_size_bytes)

    # Ensure that the frames per chunk is less than the total number of frames and greater than 1
    num_frames_per_chunk = min(num_frames_per_chunk, num_frames)
    num_frames_per_chunk = max(num_frames_per_chunk, 1)

    if num_planes is None:
        chunk_shape = (num_frames_per_chunk, width, height)
    else:
        # TODO: review the policy of chunking the data with only one volume
        chunk_shape = (num_frames_per_chunk, width, height, 1)

    return chunk_shape
