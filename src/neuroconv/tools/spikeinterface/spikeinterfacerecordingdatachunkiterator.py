from typing import Iterable, Optional

import numpy as np
from spikeinterface import BaseRecording
from tqdm import tqdm

from neuroconv.tools.hdmf import GenericDataChunkIterator


class SpikeInterfaceRecordingDataChunkIterator(GenericDataChunkIterator):
    """DataChunkIterator specifically for use on RecordingExtractor objects."""

    def __init__(
        self,
        recording: BaseRecording,
        segment_index: int = 0,
        return_scaled: bool = False,
        buffer_gb: Optional[float] = None,
        buffer_shape: Optional[tuple] = None,
        chunk_mb: Optional[float] = None,
        chunk_shape: Optional[tuple] = None,
        display_progress: bool = False,
        progress_bar_class: Optional[tqdm] = None,
        progress_bar_options: Optional[dict] = None,
    ):
        """
        Initialize an Iterable object which returns DataChunks with data and their selections on each iteration.

        Parameters
        ----------
        recording : SpikeInterfaceRecording
            The SpikeInterfaceRecording object (RecordingExtractor or BaseRecording) which handles the data access.
        segment_index : int, optional
            The recording segment to iterate on.
            Defaults to 0.
        return_scaled : bool, optional
            Whether to return the trace data in scaled units (uV, if True) or in the raw data type (if False).
            Defaults to False.
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
        display_progress : bool, optional
            Display a progress bar with iteration rate and estimated completion time.
        progress_bar_class : dict, optional
            The progress bar class to use.
            Defaults to tqdm.tqdm if the TQDM package is installed.
        progress_bar_options : dict, optional
            Dictionary of keyword arguments to be passed directly to tqdm.
            See https://github.com/tqdm/tqdm#parameters for options.
        """
        self.recording = recording
        self.segment_index = segment_index
        self.return_scaled = return_scaled
        self.channel_ids = recording.get_channel_ids()
        super().__init__(
            buffer_gb=buffer_gb,
            buffer_shape=buffer_shape,
            chunk_mb=chunk_mb,
            chunk_shape=chunk_shape,
            display_progress=display_progress,
            progress_bar_class=progress_bar_class,
            progress_bar_options=progress_bar_options,
        )

    def _get_default_chunk_shape(self, chunk_mb: float = 10.0) -> tuple[int, int]:
        assert chunk_mb > 0, f"chunk_mb ({chunk_mb}) must be greater than zero!"

        number_of_channels = self.recording.get_num_channels()
        number_of_frames = self.recording.get_num_frames(segment_index=self.segment_index)
        dtype = self.recording.get_dtype()

        chunk_shape = get_electrical_series_chunk_shape(
            number_of_channels=number_of_channels, number_of_frames=number_of_frames, dtype=dtype, chunk_mb=chunk_mb
        )

        return chunk_shape

    def _get_data(self, selection: tuple[slice]) -> Iterable:
        return self.recording.get_traces(
            segment_index=self.segment_index,
            channel_ids=self.channel_ids[selection[1]],
            start_frame=selection[0].start,
            end_frame=selection[0].stop,
            return_scaled=self.return_scaled,
        )

    def _get_dtype(self):
        return self.recording.get_dtype()

    def _get_maxshape(self):
        return (self.recording.get_num_samples(segment_index=self.segment_index), self.recording.get_num_channels())


def get_electrical_series_chunk_shape(
    number_of_channels: int, number_of_frames: int, dtype: np.dtype, chunk_mb: float = 10.0
) -> tuple[int, int]:
    """
    Estimate good chunk shape for an ElectricalSeries dataset.

    This function gives good estimates for cloud access patterns.

    Parameters
    ----------
    number_of_channels : int
        The number of channels in the ElectricalSeries dataset.
    number_of_frames : int
        The number of frames in the ElectricalSeries dataset.
    dtype : np.dtype
        The data type of the ElectricalSeries dataset.
    chunk_mb : float, optional
        The upper bound on size in megabytes (MB) of the internal chunk for the HDF5 dataset.
        The chunk_shape will be set implicitly by this argument.

    Returns
    -------
    tuple[int, int]
        The chunk shape for the ElectricalSeries dataset.
    """
    assert chunk_mb > 0, f"chunk_mb ({chunk_mb}) must be greater than zero!"

    # We use 64 channels as that gives enough time for common sampling rates when chunk_mb == 10.0
    # See # from https://github.com/flatironinstitute/neurosift/issues/52#issuecomment-1671405249
    chunk_channels = min(64, number_of_channels)

    size_of_chunk_channels_bytes = chunk_channels * dtype.itemsize
    total_chunk_space_bytes = chunk_mb * 1e6

    # We allocate as many frames as possible with the remaining space of the chunk
    chunk_frames = total_chunk_space_bytes // size_of_chunk_channels_bytes

    # We clip by the number of frames if the samples are too small
    chunk_frames = min(chunk_frames, number_of_frames)

    return (chunk_frames, chunk_channels)
