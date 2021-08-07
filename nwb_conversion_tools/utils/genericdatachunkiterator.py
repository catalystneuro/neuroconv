"""Authors: Cody Baker, Saksham Sharda, and Oliver Ruebel."""
from typing import Iterable, Tuple
import numpy as np
import psutil
from abc import abstractmethod
from hdmf.data_utils import AbstractDataChunkIterator, DataChunk
from itertools import product


class GenericDataChunkIterator(AbstractDataChunkIterator):
    """DataChunkIterator that lets the user specify chunk shapes."""

    def _set_chunk_shape(self, chunk_mb: float):
        min_shape = np.min(self.maxshape)
        v = np.array([np.floor(x / min_shape) for x in self.maxshape])
        k = np.floor((chunk_mb * 1e6 / (np.prod(v) * self.dtype.itemsize)) ** (1 / len(self.maxshape)))
        self.chunk_shape = tuple(k * v)

    def _set_buffer_shape(self, buffer_gb: float):
        pass

    def __init__(
        self, buffer_gb: float = 2.0, buffer_shape: tuple = None, chunk_mb: float = 1.0, chunk_shape: tuple = None
    ):
        """
        Break a dataset into buffers containing chunks, with the chunk as they are written into the H5 dataset.

        Basic users should set the buffer_gb argument to as much free RAM space as can be safely allowed.
        Advanced users are offered full control over the shape paramters for the buffer and the chunks.

        buffer_gb : float, optional
            If buffer_shape is not specified, it will be inferred as the smallest chunk below the buffer_gb threshold.
            Defaults to 2 GB.
        buffer_shape : tuple, optional
            Manually defined shape of the buffer. Defaults to None.
        chunk_mb : float, optional
            If chunk_shape is not specified, it will be inferred as the smallest chunk below the chunk_mb threshold.
            H5 reccomends setting this to around 1 MB (our default) for optimal performance.
        chunk_shape : tuple, optional
            Manually defined shape of the chunks. Defaults to None.
        """
        assert (
            buffer_gb > 0 and buffer_gb < psutil.virtual_memory().available / 1e9
        ), f"Not enough memory in system handle buffer_gb of {buffer_gb}!"
        self._maxshape = self._get_maxshape()
        self._dtype = self._get_dtype()
        if chunk_shape is not None:
            self.chunk_shape = self._set_chunk_shape(
                start_shape=self.maxshape, typesize=self.dtype.itemsize, buffer_gb=buffer_gb
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
