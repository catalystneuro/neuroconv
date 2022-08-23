"""General purpose iterator for all ImagingExtractor data."""
from typing import Tuple, Optional

import numpy as np
from hdmf.data_utils import GenericDataChunkIterator
from roiextractors import ImagingExtractor


class ImagingExtractorDataChunkIterator(GenericDataChunkIterator):
    """DataChunkIterator for ImagingExtractor objects primarily used when writing imaging data to an NWB file."""

    def __init__(
        self,
        imaging_extractor: ImagingExtractor,
        buffer_gb: Optional[float] = None,
        buffer_shape: Optional[tuple] = None,
        chunk_mb: Optional[float] = None,
        chunk_shape: Optional[tuple] = None,
        display_progress: bool = False,
        progress_bar_options: Optional[dict] = None,
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
            The default is 1MB, as recommended by the HDF5 group. For more details, see
            https://support.hdfgroup.org/HDF5/doc/TechNotes/TechNote-HDF5-ImprovingIOPerformanceCompressedDatasets.pdf
        chunk_shape : tuple, optional
            Manual specification of the internal chunk shape for the HDF5 dataset.
            Cannot be set if `chunk_mb` is also specified.
            The default is None.
        display_progress : bool, optional
            Display a progress bar with iteration rate and estimated completion time.
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
            chunk_mb = 1.0

        self._maxshape = self._get_maxshape()
        self._dtype = self._get_dtype()
        if chunk_shape is None:
            chunk_shape = super()._get_default_chunk_shape(chunk_mb=chunk_mb)

        if buffer_gb is None and buffer_shape is None:
            buffer_gb = 1.0

        if buffer_shape is None:
            buffer_shape = self._get_scaled_buffer_shape(buffer_gb=buffer_gb, chunk_shape=chunk_shape)

        super().__init__(
            buffer_shape=buffer_shape,
            chunk_shape=chunk_shape,
            display_progress=display_progress,
            progress_bar_options=progress_bar_options,
        )

    def _get_scaled_buffer_shape(self, buffer_gb: float, chunk_shape: tuple) -> tuple:
        """Select the buffer_shape less than the threshold of buffer_gb that is also a multiple of the chunk_shape."""
        assert buffer_gb > 0, f"buffer_gb ({buffer_gb}) must be greater than zero!"
        assert all(np.array(chunk_shape) > 0), f"Some dimensions of chunk_shape ({chunk_shape}) are less than zero!"

        image_size = self._get_maxshape()[1:]
        min_buffer_shape = tuple([chunk_shape[0]]) + image_size
        scaling_factor = np.floor((buffer_gb * 1e9 / (np.prod(min_buffer_shape) * self._get_dtype().itemsize)))
        max_buffer_shape = tuple([int(scaling_factor * min_buffer_shape[0])]) + image_size
        scaled_buffer_shape = tuple(
            [
                min(max(int(dimension_length), chunk_shape[dimension_index]), self._get_maxshape()[dimension_index])
                for dimension_index, dimension_length in enumerate(max_buffer_shape)
            ]
        )
        return scaled_buffer_shape

    def _get_dtype(self) -> np.dtype:
        return self.imaging_extractor.get_dtype()

    def _get_maxshape(self) -> tuple:
        video_shape = (self.imaging_extractor.get_num_frames(),)
        image_shape = self.imaging_extractor.get_image_size()
        width, height = image_shape[1], image_shape[0]  # ROIExtractors convention is flipped
        video_shape += (width, height)
        if len(image_shape) == 3:
            depth = image_shape[2]
            video_shape += (depth,)
        return video_shape

    def _get_data(self, selection: Tuple[slice]) -> np.ndarray:
        data = self.imaging_extractor.get_video(
            start_frame=selection[0].start,
            end_frame=selection[0].stop,
        )
        tranpose_axes = (0, 2, 1) if len(data.shape) == 3 else (0, 2, 1, 3)
        return data.transpose(tranpose_axes)[(slice(0, self.buffer_shape[0]),) + selection[1:]]
