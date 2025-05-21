"""General purpose iterator for all ImagingExtractor data."""

import numpy as np
from roiextractors import ImagingExtractor
from tqdm import tqdm

from neuroconv.tools.hdmf import GenericDataChunkIterator
from neuroconv.tools.iterative_write import (
    get_image_series_buffer_shape,
    get_image_series_chunk_shape,
)


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

    def _get_sample_shape(self) -> tuple:
        """This translate the sample shape in roiextractors to the nwb convention by transposing the frame shape."""

        roi_extractors_frame_shape = self.imaging_extractor.get_frame_shape()
        height, width = roi_extractors_frame_shape[0], roi_extractors_frame_shape[1]
        nwb_frame_shape = (width, height)

        if self.imaging_extractor.is_volumetric:
            num_planes = self.imaging_extractor.get_num_planes()
            sample_shape = nwb_frame_shape + (num_planes,)
        else:
            sample_shape = nwb_frame_shape

        return sample_shape

    def _get_default_chunk_shape(self, chunk_mb: float) -> tuple:
        """Select the chunk_shape less than the threshold of chunk_mb while keeping the original image size."""
        assert chunk_mb > 0, f"chunk_mb ({chunk_mb}) must be greater than zero!"

        num_samples = self.imaging_extractor.get_num_samples()
        sample_shape = self._get_sample_shape()
        dtype = self.imaging_extractor.get_dtype()

        chunk_shape = get_image_series_chunk_shape(
            num_samples=num_samples,
            sample_shape=sample_shape,
            dtype=dtype,
            chunk_mb=chunk_mb,
        )

        return chunk_shape

    def _get_scaled_buffer_shape(self, buffer_gb: float, chunk_shape: tuple) -> tuple:
        """Select the buffer_shape less than the threshold of buffer_gb that is also a multiple of the chunk_shape."""
        assert buffer_gb > 0, f"buffer_gb ({buffer_gb}) must be greater than zero!"
        assert all(np.array(chunk_shape) > 0), f"Some dimensions of chunk_shape ({chunk_shape}) are less than zero!"

        sample_shape = self._get_sample_shape()
        series_shape = self._get_maxshape()
        dtype = self._get_dtype()

        buffer_shape = get_image_series_buffer_shape(
            chunk_shape=chunk_shape,
            sample_shape=sample_shape,
            series_shape=series_shape,
            dtype=dtype,
            buffer_gb=buffer_gb,
        )

        return buffer_shape

    def _get_dtype(self) -> np.dtype:
        return self.imaging_extractor.get_dtype()

    def _get_maxshape(self) -> tuple:

        num_frames = self.imaging_extractor.get_num_samples()
        sample_shape = self._get_sample_shape()

        max_shape = (num_frames,) + sample_shape
        return max_shape

    def _get_data(self, selection: tuple[slice]) -> np.ndarray:
        data = self.imaging_extractor.get_series(
            start_sample=selection[0].start,
            end_sample=selection[0].stop,
        )
        tranpose_axes = (0, 2, 1) if len(data.shape) == 3 else (0, 2, 1, 3)
        sliced_selection = (slice(0, self.buffer_shape[0]),) + selection[1:]

        return data.transpose(tranpose_axes)[sliced_selection]
