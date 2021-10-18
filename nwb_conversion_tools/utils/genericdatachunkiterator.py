"""Authors: Cody Baker, Saksham Sharda, and Oliver Ruebel."""
from typing import Iterable, Tuple, Optional
import numpy as np
import psutil
from abc import abstractmethod
from itertools import product

from hdmf.data_utils import AbstractDataChunkIterator, DataChunk


class GenericDataChunkIterator(AbstractDataChunkIterator):
    """DataChunkIterator that lets the user specify chunk and buffer shapes."""

    def _set_chunk_shape(self, chunk_mb):
        """
        Select chunk size less than the threshold of chunk_mb, keeping the dimensional ratios of the original data.

        Parameters
        ----------
        chunk_mb : float
            H5 reccomends setting this to around 1 MB for optimal performance.
        """
        n_dims = len(self.maxshape)
        itemsize = self.dtype.itemsize
        chunk_bytes = chunk_mb * 1e6
        v = np.floor(np.array(self.maxshape) / np.min(self.maxshape))
        prod_v = np.prod(v)
        while prod_v * itemsize > chunk_bytes and prod_v != 1:
            v_ind = v != 1
            next_v = v[v_ind]
            v[v_ind] = np.floor(next_v / np.min(next_v))
            prod_v = np.prod(v)
        k = np.floor((chunk_bytes / (prod_v * itemsize)) ** (1 / n_dims))
        self.chunk_shape = tuple([min(int(x), self.maxshape[dim]) for dim, x in enumerate(k * v)])

    def _set_buffer_shape(self, buffer_gb):
        """
        Select buffer size less than the threshold of buffer_gb, keeping the dimensional ratios of the original data.

        Parameters
        ----------
        buffer_gb : float
            The maximum amount of RAM to use to buffer the chunks.
        """
        assert (
            buffer_gb > 0 and buffer_gb < psutil.virtual_memory().available / 1e9
        ), f"Not enough memory in system handle buffer_gb of {buffer_gb}!"
        k = np.floor(
            (buffer_gb * 1e9 / (np.prod(self.chunk_shape) * self.dtype.itemsize)) ** (1 / len(self.chunk_shape))
        )
        self.buffer_shape = tuple([min(int(x), self.maxshape[j]) for j, x in enumerate(k * np.array(self.chunk_shape))])

    def __init__(
        self,
        buffer_gb: Optional[float] = None,
        buffer_shape: Optional[tuple] = None,
        chunk_mb: Optional[float] = None,
        chunk_shape: Optional[tuple] = None,
    ):
        """
        Break a dataset into buffers containing chunks, with the chunk as they are written into the H5 dataset.

        Basic users should set the buffer_gb argument to as much free RAM space as can be safely allowed.
        Advanced users are offered full control over the shape paramters for the buffer and the chunks.

        Parameters
        ----------
        buffer_gb : float, optional
            If buffer_shape is not specified, it will be inferred as the smallest chunk below the buffer_gb threshold.
            Defaults to 1 GB.
        buffer_shape : tuple, optional
            Manually defined shape of the buffer. Defaults to None.
        chunk_mb : float, optional
            If chunk_shape is not specified, it will be inferred as the smallest chunk below the chunk_mb threshold.
            H5 reccomends setting this to around 1 MB (our default) for optimal performance.
        chunk_shape : tuple, optional
            Manually defined shape of the chunks. Defaults to None.
        """
        if buffer_gb is None and buffer_shape is None:
            buffer_gb = 1.0
        if chunk_mb is None and chunk_shape is None:
            chunk_mb = 1.0
        assert (buffer_gb is not None) != (
            buffer_shape is not None
        ), "Only one of 'buffer_gb' or 'buffer_shape' can be specified!"
        assert (chunk_mb is not None) != (
            chunk_shape is not None
        ), "Only one of 'chunk_mb' or 'chunk_shape' can be specified!"

        self._maxshape = self._get_maxshape()
        self._dtype = self._get_dtype()
        if chunk_shape is None:
            self._set_chunk_shape(chunk_mb=chunk_mb)
        else:
            assert all(
                np.array(chunk_shape) <= self.maxshape
            ), f"Some dimensions of chunk_shape ({self.chunk_shape}) exceed the data dimensions ({self.maxshape})!"
            self.chunk_shape = chunk_shape
        if buffer_shape is None:
            self._set_buffer_shape(buffer_gb=buffer_gb)
        else:
            array_buffer_shape = np.array(buffer_shape)
            assert all(
                array_buffer_shape <= self.maxshape
            ), f"Some dimensions of buffer_shape ({self.buffer_shape}) exceed the data dimensions ({self.maxshape})!"
            assert all(
                array_buffer_shape >= self.chunk_shape
            ), f"Some dimensions of chunk_shape ({self.chunk_shape}) exceed the manual buffer shape ({buffer_shape})!"
            assert all(array_buffer_shape % self.chunk_shape == 0), (
                f"Some dimensions of chunk_shape ({self.chunk_shape}) do not "
                f"evenly divide the manual buffer shape ({buffer_shape})!"
            )
            self.buffer_shape = buffer_shape

        self.num_buffers = np.ceil(np.array(self.maxshape) / self.buffer_shape).astype(int)
        self.buffer_index_generator = product(*[range(x) for x in self.num_buffers])
        self.chunk_selection_in_buffer_generator = iter(())  # So first call to next() fills buffer

    def recommended_chunk_shape(self) -> tuple:
        return self.chunk_shape

    def recommended_data_shape(self) -> tuple:
        return self.maxshape

    def __iter__(self):
        return self

    def _buffer_map(self, buffer_index: tuple) -> Iterable[slice]:
        """Map the buffer_index (permutations starting with all axes zero) to the slice selection of the full shape."""
        return tuple(
            [
                slice(n * self.buffer_shape[j], min((n + 1) * self.buffer_shape[j], self.maxshape[j]))
                for j, n in enumerate(buffer_index)
            ]
        )

    def _chunk_map(
        self, chunk_selection_in_buffer: Iterable[slice], buffer_selection: Iterable[slice]
    ) -> Iterable[slice]:
        """Map the chunk selection within the buffer to the full shape by shifting by the current buffer selection."""
        return tuple(
            [
                slice(buffer_axis.start + chunk_axis.start, buffer_axis.start + chunk_axis.stop)
                for chunk_axis, buffer_axis in zip(chunk_selection_in_buffer, buffer_selection)
            ]
        )

    def _fill_buffer(self):
        """Fill the data into the buffer using _get_data."""
        buffer_index = next(self.buffer_index_generator)
        self.buffer_selection = self._buffer_map(buffer_index=buffer_index)
        self.buffer_data = np.array(self._get_data(selection=self.buffer_selection))
        if any(np.array(buffer_index) + 1 == self.num_buffers):
            this_buffer_shape = [buffer_axis.stop - buffer_axis.start for buffer_axis in self.buffer_selection]
            self.chunk_selection_in_buffer_generator = (
                tuple(
                    [
                        slice(start_axis, min(start_axis + chunk_axis, buffer_axis))
                        for start_axis, buffer_axis, chunk_axis in zip(
                            slice_starts, this_buffer_shape, self.chunk_shape
                        )
                    ]
                )
                for slice_starts in product(
                    *[
                        range(0, buffer_axis, chunk_axis)
                        for buffer_axis, chunk_axis in zip(this_buffer_shape, self.chunk_shape)
                    ]
                )
            )
            # TODO - technically, even this reduction of the min call can be improved by using itertools.chain
            # to couple an efficient generator similar to below for all chunks not on the boundary with
            # another generator just for the edges. Wouldn't even need calls to min in that case.
            # Also, the same logic applies to how we generate buffer selections of interior vs. boundary buffers.
            # If buffer_shape is fairly small, then the repeated operations of min in _buffer_map and above boundary
            # checking logical could be a slowdown. Would be faster to pre-compute with chains and zip together.
        else:
            self.chunk_selection_in_buffer_generator = (
                tuple(
                    [
                        slice(start_axis, start_axis + chunk_axis)
                        for start_axis, chunk_axis in zip(slice_starts, self.chunk_shape)
                    ]
                )
                for slice_starts in product(
                    *[
                        range(0, buffer_axis, chunk_axis)
                        for buffer_axis, chunk_axis in zip(self.buffer_shape, self.chunk_shape)
                    ]
                )
            )

    def _get_chunk_from_buffer(self) -> (np.ndarray, tuple):
        """Retrieve the data and selection from a chunk within the buffer."""
        try:
            chunk_selection_in_buffer = next(self.chunk_selection_in_buffer_generator)
        except StopIteration:
            try:
                self._fill_buffer()
                chunk_selection_in_buffer = next(self.chunk_selection_in_buffer_generator)
            except StopIteration:
                self.buffer_data = None
                self.buffer_selection = None
                raise StopIteration
        return self.buffer_data[chunk_selection_in_buffer], chunk_selection_in_buffer

    def __next__(self) -> DataChunk:
        """Retrieve the next DataChunk object from the buffer, refilling the buffer if necessary."""
        chunk_data, chunk_selection_in_buffer = self._get_chunk_from_buffer()
        chunk_selection = self._chunk_map(
            chunk_selection_in_buffer=chunk_selection_in_buffer, buffer_selection=self.buffer_selection
        )
        data_chunk = DataChunk(data=chunk_data, selection=chunk_selection)
        return data_chunk

    @abstractmethod
    def _get_data(self, selection: Tuple[slice]) -> np.ndarray:
        """
        Retrieve the data specified by the selection using minimal I/O.

        The developer of a new implementation of the GenericDataChunkIterator must ensure the data is actually
        loaded into memory, and not simply mapped.

        Parameters
        ----------
        selection : tuple of slices
            Each axis of tuple is a slice of the full shape from which to pull data into the buffer.
        """
        raise NotImplementedError("The data fetching method has not been built for this DataChunkIterator!")

    @property
    def dtype(self):
        return self._dtype

    @abstractmethod
    def _get_dtype(self) -> np.dtype:
        """Retrieve the dtype of the data using minimal I/O."""
        raise NotImplementedError("The setter for the internal dtype has not been built for this DataChunkIterator!")

    @property
    def maxshape(self):
        return self._maxshape

    @abstractmethod
    def _get_maxshape(self) -> tuple:
        """Retrieve the maximum bounds of the data shape using minimal I/O."""
        raise NotImplementedError("The setter for the maxshape property has not been built for this DataChunkIterator!")
