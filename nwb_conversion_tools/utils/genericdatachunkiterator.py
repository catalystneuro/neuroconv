"""Authors: Cody Baker, Saksham Sharda, Oliver Ruebel."""
from typing import Iterable, Tuple
import numpy as np
import psutil
from abc import abstractmethod
from hdmf.data_utils import AbstractDataChunkIterator, DataChunk
from itertools import product


class GenericDataChunkIterator(AbstractDataChunkIterator):
    """DataChunkIterator that lets the user specify chunk shapes."""

    def _get_chunksize_mb(self, chunk_shape: Iterable, typesize: int) -> float:
        return np.product(chunk_shape) * typesize / 1e6

    def _set_chunk_shape(self, start_shape: Iterable, typesize: int, buffer_mb: float) -> tuple:
        chunk_shape = list(start_shape)
        n_dim = len(chunk_shape)
        iter_idx = 0
        while (self._get_chunksize_mb(chunk_shape, typesize) > buffer_mb) and np.product(chunk_shape) > 2:
            dim = iter_idx % n_dim
            chunk_shape[dim] = np.ceil(chunk_shape[dim] / 2.0)
            iter_idx += 1
        return tuple(int(x) for x in chunk_shape)

    def __init__(self, chunk_shape: tuple = None, buffer_mb: float = 20.):
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
        self._maxshape = self._get_maxshape()
        self._dtype = self._get_dtype()
        if chunk_shape is not None:
            self.chunk_shape = self._set_chunk_shape(
                start_shape=self.maxshape,
                typesize=self.dtype.itemsize,
                buffer_mb=buffer_mb
            )
        else:
            assert np.all(chunk_shape <= self.maxshape), "Some specified chunk shapes exceed the data dimensions!"
            self.chunk_shape = chunk_shape

        self.num_chunks = tuple(
            [int(np.ceil(self.maxshape[j] / self.chunk_shape[j])) for j in range(len(self.maxshape))]
        )
        self.chunk_idx_generator = product(*[range(x) for x in self.num_chunks])

    def recommended_chunk_shape(self) -> tuple:
        return self.chunk_shape

    def recommended_data_shape(self) -> tuple:
        return self.maxshape

    def __iter__(self):
        return self

    def _chunk_map(self, chunk_idx: tuple) -> tuple:
        return tuple([slice(n * self.chunk_shape[j], (n + 1) * self.chunk_shape[j]) for j, n in enumerate(chunk_idx)])

    def __next__(self) -> DataChunk:
        """Return the next data chunk or raise a StopIteration exception if all chunks have been retrieved."""
        selection = self._chunk_map(chunk_idx=next(self.chunk_idx_generator))
        data = self._get_data(selection=selection)
        return DataChunk(data=data, selection=selection)

    @abstractmethod
    def _get_data(self, selection: Tuple[slice]) -> Iterable:
        """Retrieve the data specified by the selection using absolute minimal I/O."""
        raise NotImplementedError("The data fetching method has not been built for this DataChunkIterator!")

    @property
    def dtype(self):
        return self._dtype

    @abstractmethod
    def _get_dtype(self) -> np.dtype:
        """Retrieve the dtype of the data using absolute minimal I/O."""
        raise NotImplementedError("The setter for the internal dtype has not been built for this DataChunkIterator!")

    @property
    def maxshape(self):
        return self._maxshape

    @abstractmethod
    def _get_maxshape(self) -> tuple:
        """Retrieve the maximum bounds of the data shape using absolute minimal I/O."""
        raise NotImplementedError("The setter for the maxshape property has not been built for this DataChunkIterator!")
