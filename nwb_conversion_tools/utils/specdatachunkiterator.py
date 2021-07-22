"""Authors: Cody Baker, Oliver Ruebel."""
from typing import Iterable
import numpy as np
import psutil

from hdmf.data_utils import AbstractDataChunkIterator, DataChunk


class SpecDataChunkIterator(AbstractDataChunkIterator):
    """DataChunkIterator that lets the user specify chunk shapes."""

    def __init__(self, data: Iterable, buffer_mb: int):
        assert buffer_mb < psutil.virtual_memory().available / 1e6, \
            f"Not enough memory in system handle buffer_mb of {buffer_mb}!"
        self.data = data
        self.full_shape = data.shape
        self.__dtype = data.dtype
        self.__curr_timestep = 0
        self.__curr_channel_idx = 0

        def get_chunksize_mb(chunk_shape, typesize):
            return np.product(chunk_shape) * typesize / 1e6

        def set_chunk_shape(chunk_shape, typesize, buffer_mb):
            n_dim = len(chunk_shape)
            iter_idx = 0
            while (get_chunksize_mb(chunk_shape, typesize) > buffer_mb) and np.product(chunk_shape) > 2:
                dim = iter_idx % n_dim
                chunk_shape[dim] = np.ceil(chunk_shape[dim] / 2.0)
                iter_idx += 1
            return tuple(int(x) for x in chunk_shape)

        self.chunk_shape = set_chunk_shape(
            chunk_shape=list(self.full_shape),
            typesize=self.__dtype.itemsize,
            buffer_mb=buffer_mb
        )

    def __iter__(self):
        """Return the iterator object."""
        return self

    def __next__(self):
        """Return the next data chunk or raise a StopIteration exception if all chunks have been retrieved."""
        end_timestep = self.__curr_timestep + self.chunk_shape[0]
        if self.__curr_channel_idx >= self.full_shape[1]:
            self.__curr_channel_idx = 0
            self.__curr_timestep = end_timestep
            end_timestep = self.__curr_timestep + self.chunk_shape[0]

            if self.__curr_timestep >= self.full_shape[0]:
                raise StopIteration

        end_channel_idx = self.__curr_channel_idx + self.chunk_shape[1]
        if end_timestep > self.full_shape[0]:
            end_timestep = self.full_shape[0]
        if end_channel_idx > self.full_shape[1]:
            end_channel_idx = self.full_shape[1]

        selection = np.s_[self.__curr_timestep:end_timestep, self.__curr_channel_idx:end_channel_idx]
        data = self.data[selection]

        self.__curr_channel_idx = end_channel_idx
        return DataChunk(data=data, selection=selection)

    def recommended_data_shape(self):
        """Recommend the initial shape for the data array."""
        return (self.full_shape[0], self.full_shape[1])

    @property
    def dtype(self):
        return self.__dtype

    @property
    def maxshape(self):
        return self.full_shape

    def recommended_chunk_shape(self):
        return self.chunk_shape
