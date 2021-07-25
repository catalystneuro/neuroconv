"""Authors: Cody Baker, Oliver Ruebel."""
from typing import Iterable
import numpy as np
import psutil
from abc import abstractmethod
from hdmf.data_utils import AbstractDataChunkIterator, DataChunk


class SpecDataChunkIterator(AbstractDataChunkIterator):
    """DataChunkIterator that lets the user specify chunk shapes."""

    def __init__(self, chunk_shape: tuple = (), buffer_mb: int = 20):
        """
        Initialize the SpecDataChunkIterator object with specified chunk parameters.

        data : Iterable
            The data to be chunked. Recommended to be a np.memmap at this point in time.
        chunk_shape : tuple, optional
            The desired shape of the chunks. Defaults to empty.
        buffer_mb : int, optional
            If chunk_shape is not specified, it will be inferred as the smallest chunk below the buffer_mb threshold.
            Defaults to 20 MB.
        """
        assert buffer_mb > 0 and buffer_mb < psutil.virtual_memory().available / 1e6, \
            f"Not enough memory in system handle buffer_mb of {buffer_mb}!"
        self.data = self._get_data()
        self.full_shape = self._get_shape()
        self.__dtype = self._get_dtype()
        if chunk_shape == ():
            self.chunk_shape = self._set_chunk_shape(
                chunk_shape=list(self.full_shape),
                typesize=self.__dtype.itemsize,
                buffer_mb=buffer_mb
            )
        else:
            assert all([self.full_shape[i]%chunk_shape[i]==0
                         for i in range(len(self.full_shape))]), \
                'incorrect chunk shape provided'
            self.chunk_shape = chunk_shape

        self.iterator = self._data_generator()

    def _data_generator(self):
        for curr_timestep in range(0, self.full_shape[0], self.chunk_shape[0]):
            for curr_channel_idx in range(0, self.full_shape[1], self.chunk_shape[1]):
                selection = np.s_[
                            curr_timestep:(curr_timestep + self.chunk_shape[0]),
                            curr_channel_idx:(curr_channel_idx + self.chunk_shape[1])
                            ]
                yield DataChunk(data=self.data[selection], selection=selection)

    @abstractmethod
    def _get_data(self):
        pass

    @abstractmethod
    def _get_shape(self):
        pass

    @abstractmethod
    def _get_dtype(self):
        pass

    def _get_chunksize_mb(self,chunk_shape, typesize):
        return np.product(chunk_shape) * typesize / 1e6

    def _set_chunk_shape(self, chunk_shape, typesize, buffer_mb):
        n_dim = len(chunk_shape)
        iter_idx = 0
        while (self._get_chunksize_mb(chunk_shape, typesize) > buffer_mb) and np.product(chunk_shape) > 2:
            dim = iter_idx % n_dim
            chunk_shape[dim] = np.ceil(chunk_shape[dim] / 2.0)
            iter_idx += 1
        return tuple(int(x) for x in chunk_shape)

    def __iter__(self):
        return self

    def __next__(self):
        """Return the next data chunk or raise a StopIteration exception if all chunks have been retrieved."""
        return next(self.iterator)

    def recommended_data_shape(self):
        """Recommend the initial shape for the data array."""
        return tuple(self.full_shape)

    @property
    def dtype(self):
        return self.__dtype

    @property
    def maxshape(self):
        return tuple(self.full_shape)

    def recommended_chunk_shape(self):
        return self.chunk_shape


class IterableSpecDataChunkIterator(SpecDataChunkIterator):

    def __init__(self, data: Iterable, chunk_shape: tuple = (), buffer_mb: int = 20):
        self._data_object = np.array(data)
        super().__init__(chunk_shape, buffer_mb)

    def _get_data(self):
        return self._data_object

    def _get_shape(self):
        return self._data_object.shape

    def _get_dtype(self):
        return self._data_object.dtype


class RecordingExtractorsSpecDataChunkIterator(SpecDataChunkIterator):

    def __init__(self, extractor , chunk_shape: tuple = (), buffer_mb: int = 20):
        self._data_object = extractor
        super().__init__(chunk_shape, buffer_mb)

    def _get_data(self):
        return self._data_object

    def _get_shape(self):
        return (self._data_object.get_num_frames(),
                self._data_object.get_num_channels())

    def _get_dtype(self):
        return self._data_object.get_dype

    def _data_generator(self):
        for curr_timestep in range(0, self.full_shape[0], self.chunk_shape[0]):
            for curr_channel_idx in range(0, self.full_shape[1], self.chunk_shape[1]):
                out_trace_chunk = self._data_object.get_traces(
                    channel_ids=list(range(curr_channel_idx,curr_channel_idx + self.chunk_shape[1])),
                    start_frame=curr_timestep,
                    end_frame=curr_timestep+self.chunk_shape[0]
                )
                yield out_trace_chunk