"""Authors: Cody Baker and Saksham Sharda."""
from typing import Tuple, Iterable

from spikeextractors import RecordingExtractor

from .genericdatachunkiterator import GenericDataChunkIterator


class RecordingExtractorDataChunkIterator(GenericDataChunkIterator):
    """DataChunkIterator specifically for use on RecordingExtractor objects."""

    def __init__(
        self,
        recording_extractor: RecordingExtractor,
        buffer_gb: float = 2.0,
        buffer_shape: tuple = None,
        chunk_mb: float = 1.0,
        chunk_shape: tuple = None
    ):
        self.recording_extractor = recording_extractor
        self.channel_ids = recording_extractor.get_channel_ids()
        super().__init__(buffer_gb=buffer_gb, buffer_shape=buffer_shape, chunk_mb=chunk_mb, chunk_shape=chunk_shape)

    def _get_data(self, selection: Tuple[slice]) -> Iterable:
        return self.recording_extractor.get_traces(
            channel_ids=self.channel_ids[selection[1]], start_frame=selection[0].start, end_frame=selection[0].stop
        ).T

    def _get_dtype(self):
        return self.recording_extractor.get_dtype(return_scaled=False)

    def _get_maxshape(self):
        return (self.recording_extractor.get_num_frames(), self.recording_extractor.get_num_channels())
