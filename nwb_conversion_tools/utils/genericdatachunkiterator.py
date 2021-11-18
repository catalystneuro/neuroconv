"""Authors: Cody Baker, Saksham Sharda, and Oliver Ruebel."""
from typing import Iterable, Tuple, Optional
import numpy as np
import psutil
from abc import abstractmethod
from itertools import product, chain

from hdmf.data_utils import AbstractDataChunkIterator, DataChunk


class GenericDataChunkIterator(AbstractDataChunkIterator):
    """DataChunkIterator that lets the user specify chunk and buffer shapes."""

    def _get_default_chunk_shape(self, chunk_mb):
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
        return tuple([min(int(x), self.maxshape[dim]) for dim, x in enumerate(k * v)])

    def _get_default_buffer_shape(self, buffer_gb):
        """
        Select buffer size less than the threshold of buffer_gb, keeping the dimensional ratios of the original data.

        Assumes the chunk_shape has already been set.

        Parameters
        ----------
        buffer_gb : float
            The maximum amount of RAM to use to buffer the chunks.
        """
        k = np.floor(
            (buffer_gb * 1e9 / (np.prod(self.chunk_shape) * self.dtype.itemsize)) ** (1 / len(self.chunk_shape))
        )
        return tuple([min(int(x), self.maxshape[j]) for j, x in enumerate(k * np.array(self.chunk_shape))])

    def __init__(
        self,
        buffer_gb: Optional[float] = None,
        buffer_shape: Optional[tuple] = None,
        chunk_mb: Optional[float] = None,
        chunk_shape: Optional[tuple] = None,
    ):
        """
        Break a dataset into buffers containing multiple chunks to be written into an HDF5 dataset.

        Basic users should set the buffer_gb argument to as much free RAM space as can be safely allocated.
        Advanced users are offered full control over the shape paramters for the buffer and the chunks; however,
        the chunk shape must perfectly divide the buffer shape along each axis.

        HDF5 also recommends not setting chunk_mb greater than 1 MB for optimal caching speeds.
        See https://support.hdfgroup.org/HDF5/doc/TechNotes/TechNote-HDF5-ImprovingIOPerformanceCompressedDatasets.pdf
        for more details.

        Parameters
        ----------
        buffer_gb : float, optional
            If buffer_shape is not specified, it will be inferred as the smallest chunk below the buffer_gb threshold.
            Defaults to 1 GB.
        buffer_shape : tuple, optional
            Manually defined shape of the buffer. Defaults to None.
        chunk_mb : float, optional
            If chunk_shape is not specified, it will be inferred as the smallest chunk below the chunk_mb threshold.
            Defaults to 1 MB.
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
            self.chunk_shape = self._get_default_chunk_shape(chunk_mb=chunk_mb)
        else:
            self.chunk_shape = chunk_shape
        if buffer_shape is None:
            self.buffer_shape = self._get_default_buffer_shape(buffer_gb=buffer_gb)
        else:
            self.buffer_shape = buffer_shape
            buffer_gb = np.prod(self.buffer_shape) * np.dtype(self._dtype).itemsize / 1e9

        array_chunk_shape = np.array(self.chunk_shape)
        array_buffer_shape = np.array(self.buffer_shape)
        array_maxshape = np.array(self.maxshape)
        assert buffer_gb > 0, f"buffer_gb ({buffer_gb}) must be greater than zero!"
        assert (
            buffer_gb < psutil.virtual_memory().available / 1e9
        ), f"Not enough memory in system handle buffer_gb of {buffer_gb}!"
        assert all(array_chunk_shape > 0), f"Some dimensions of chunk_shape ({self.chunk_shape}) are less than zero!"
        assert all(array_buffer_shape > 0), f"Some dimensions of buffer_shape ({self.buffer_shape}) are less than zero!"
        assert all(
            array_buffer_shape <= array_maxshape
        ), f"Some dimensions of buffer_shape ({self.buffer_shape}) exceed the data dimensions ({self.maxshape})!"
        assert all(
            array_chunk_shape <= array_buffer_shape
        ), f"Some dimensions of chunk_shape ({self.chunk_shape}) exceed the manual buffer shape ({self.buffer_shape})!"
        assert all((array_buffer_shape % array_chunk_shape == 0)[array_buffer_shape != array_maxshape]), (
            f"Some dimensions of chunk_shape ({self.chunk_shape}) do not "
            f"evenly divide the buffer shape ({self.buffer_shape})!"
        )

        self.buffer_selection_generator = (
            tuple([slice(lower_bound, upper_bound) for lower_bound, upper_bound in zip(lower_bounds, upper_bounds)])
            for lower_bounds, upper_bounds in zip(
                product(
                    *[
                        range(0, max_shape_axis, buffer_shape_axis)
                        for max_shape_axis, buffer_shape_axis in zip(self.maxshape, self.buffer_shape)
                    ]
                ),
                product(
                    *[
                        chain(range(buffer_shape_axis, max_shape_axis, buffer_shape_axis), [max_shape_axis])
                        for max_shape_axis, buffer_shape_axis in zip(self.maxshape, self.buffer_shape)
                    ]
                ),
            )
        )

    def recommended_chunk_shape(self) -> tuple:
        return self.chunk_shape

    def recommended_data_shape(self) -> tuple:
        return self.maxshape

    def __iter__(self):
        return self

    def __next__(self) -> DataChunk:
        """Retrieve the next DataChunk object from the buffer, refilling the buffer if necessary."""
        buffer_selection = next(self.buffer_selection_generator)
        return DataChunk(data=self._get_data(selection=buffer_selection), selection=buffer_selection)

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
