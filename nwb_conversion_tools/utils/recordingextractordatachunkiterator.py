"""Authors: Cody Baker, Saksham Sharda."""
from typing import Tuple, Iterable
import numpy as np

from spikeextractors import RecordingExtractor

from .genericdatachunkiterator import GenericDataChunkIterator


class RecordingExtractorDataChunkIterator(GenericDataChunkIterator):

    def __init__(self, recording_extractor: RecordingExtractor, chunk_shape: tuple = (), buffer_mb: int = 20):
        self.recording_extractor = recording_extractor
        self.channel_ids = recording_extractor.get_channel_ids()
        super().__init__(chunk_shape=chunk_shape, buffer_mb=buffer_mb)

    def _get_data(self, selection: Tuple[slice]) -> Iterable:
        return self.recording_extractor.get_traces(
            channel_ids=self.channel_ids[selection[1]],
            start_frame=selection[0].start,
            end_frame=selection[0].stop
        ).T

    def _get_dtype(self):
        return self.recording_extractor.get_dtype(return_scaled=False)

    def _get_maxshape(self):
        return (self.recording_extractor.get_num_frames(), self.recording_extractor.get_num_channels())
