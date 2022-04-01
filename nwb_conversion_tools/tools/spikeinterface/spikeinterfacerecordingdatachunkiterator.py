"""Authors: Cody Baker and Saksham Sharda."""
from typing import Tuple, Iterable, Optional, Union

from spikeinterface.core.old_api_utils import OldToNewRecording
from spikeextractors import RecordingExtractor
from hdmf.data_utils import GenericDataChunkIterator
from spikeinterface import BaseRecording

SpikeInterfaceRecording = Union[BaseRecording, RecordingExtractor]


class SpikeInterfaceRecordingDataChunkIterator(GenericDataChunkIterator):
    """DataChunkIterator specifically for use on RecordingExtractor objects."""

    def __init__(
        self,
        recording: SpikeInterfaceRecording,
        segment_index: int = 0,
        return_scaled: bool = False,
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
        if isinstance(recording, RecordingExtractor):
            self.recording = OldToNewRecording(oldapi_recording_extractor=recording)
        else:
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
            progress_bar_options=progress_bar_options,
        )

    def _get_data(self, selection: Tuple[slice]) -> Iterable:
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
