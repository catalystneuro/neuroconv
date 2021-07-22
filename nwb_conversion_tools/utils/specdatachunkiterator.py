"""Authors: Cody Baker, Oliver Ruebel."""
from typing import Iterable
import numpy as np

from hdmf.data_utils import AbstractDataChunkIterator, DataChunk


class SpecDataChunkIterator(AbstractDataChunkIterator):
    """DataChunkIterator that lets the user specify chunk shapes."""

    def __init__(self, data: Iterable, full_shape: tuple, chunk_shape: tuple):
        self.data = data
        self.full_shape = full_shape
        self.chunk_shape = chunk_shape
        self.__dtype = data.dtype
        self.__curr_timestep = 0
        self.__curr_channel_idx = 0

    def __iter__(self):
        """Return the iterator object"""
        return self

    def __read_block(self, start_time_idx, stop_time_idx, start_ch_idx, stop_ch_idx):
        arr = self.data[start_time_idx:stop_time_idx, start_ch_idx:stop_ch_idx]
        return arr

    def __next__(self):
        """
        Return the next data chunk or raise a StopIteration exception if all chunks have been retrieved.
        :returns: DataChunk object with the data and selection of the current chunk
        :rtype: DataChunk
        """
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
        data = self.__read_block(self.__curr_timestep, end_timestep, self.__curr_channel_idx, end_channel_idx)
        self.__curr_channel_idx = end_channel_idx

        return DataChunk(data=data, selection=selection)

    def recommended_data_shape(self):
        """
        Recommend the initial shape for the data array.
        This is useful in particular to avoid repeated resized of the target array when reading from
        this data iterator. This should typically be either the final size of the array or the known
        minimal shape of the array.
        :return: NumPy-style shape tuple indicating the recommended initial shape for the target array.
                 This may or may not be the final full shape of the array, i.e., the array is allowed
                 to grow. This should not be None.
        """
        return (self.full_shape[0], self.full_shape[1])

    @property
    def dtype(self):
        return self.__dtype

    @property
    def maxshape(self):
        return self.full_shape

    def recommended_chunk_shape(self):
        return None
