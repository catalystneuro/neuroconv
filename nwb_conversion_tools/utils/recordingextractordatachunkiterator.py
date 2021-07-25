from typing import Tuple, Iterable
import numpy as np

from spikeextractors import RecordingExtractor

from .genericdatachunkiterator import GenericDataChunkIterator

class RecordingExtractorDataChunkIterator(GenericDataChunkIterator):

    def __init__(self, recording_extractor: RecordingExtractor, chunk_shape: tuple = (), buffer_mb: int = 20):
        self.recording_extractor = recording_extractor
        super().__init__(chunk_shape=chunk_shape, buffer_mb=buffer_mb)

    def _get_data(self, selection: Tuple[slice]) -> Iterable:
        return self.recording_extractor.get_traces(
            channel_ids=list(range(selection[1], selection[1] + self.chunk_shape[1])),
            start_frame=selection[0],
            end_frame=selection[0] + self.chunk_shape[0]
        )

    @property
    def dtype(self) -> np.dtype:
        return self._dtype

    @dtype.setter
    def dtype(self, value):
        self._dtype = self.recording_extractor.get_dtype(return_scaled=False)

    @property
    def maxshape(self) -> tuple:
        return self._maxshape

    @maxshape.setter
    def maxshape(self):
        self._maxshape = (self.recording_extractor.get_num_frames(), self.recording_extractor.get_num_channels())
