from typing import Tuple

import numpy as np
from hdmf.data_utils import GenericDataChunkIterator as HDMFGenericDataChunkIterator


class GenericDataChunkIterator(HDMFGenericDataChunkIterator):
    def _get_default_buffer_shape(self, buffer_gb: float = 1.0) -> Tuple[int]:
        chunk_size = np.prod(self.chunk_shape) * self.dtype.itemsize
        assert buffer_gb > 0, f"buffer_gb ({buffer_gb}) must be greater than zero!"
        assert (
            buffer_gb >= chunk_size / 1e9
        ), f"buffer_gb ({buffer_gb}) must be greater than the chunk size ({chunk_size / 1e9})!"
        assert all(
            np.array(self.chunk_shape) > 0
        ), f"Some dimensions of chunk_shape ({self.chunk_shape}) are less than zero!"

        maxshape = np.array(self.maxshape)

        # Early termination condition
        if np.prod(maxshape) * self.dtype.itemsize / 1e9 < buffer_gb:
            return tuple(self.maxshape)

        chunks_per_axis = np.ceil(maxshape / self.chunk_shape)
        buffer_shape = np.array(self.chunk_shape)
        axis_sizes_gb = maxshape * self.dtype.itemsize / 1e9
        chunk_size_order = np.argsort(self.chunk_shape)
        target_buffer_bytes = buffer_gb * 1e9

        # If the smallest full axis does not fit within the buffer size, form a square along the two smallest axes
        if min(axis_sizes_gb) > buffer_gb:
            k1 = np.floor((target_buffer_bytes / chunk_size) ** 0.5)
            for idx in [0, 1]:
                buffer_shape[chunk_size_order[idx]] = k1 * buffer_shape[chunk_size_order[idx]]
            return tuple(buffer_shape)

        # Otherwise, start by filling the smallest axis completely
        buffer_size = chunk_size * min(chunks_per_axis)
        buffer_shape[chunk_size_order[0]] = self.maxshape[chunk_size_order[0]]
        full_axes_used = np.zeros(shape=len(self.maxshape), dtype=bool)
        full_axes_used[chunk_size_order[0]] = True
        for axis, chunks_on_axis in enumerate(chunks_per_axis):
            if full_axes_used[axis]:  # If the smallest axis, skip since already used
                continue
            if chunks_on_axis * buffer_size <= target_buffer_bytes:  # If multiple axes can be used together
                buffer_size *= chunks_on_axis
                buffer_shape[axis] = self.maxshape[axis]
            else:  # Found an axis that is too large to use with the rest of the buffer; calculate how much can be used
                k2 = np.floor(target_buffer_bytes / buffer_size)
                buffer_shape[axis] *= k2
                break
        return tuple(buffer_shape)


class SliceableDataChunkIterator(GenericDataChunkIterator):
    """
    Generic data chunk iterator that works for any memory mapped array, such as a np.memmap or an h5py.Dataset
    """

    def __init__(self, data, **kwargs):
        self.data = data
        super().__init__(**kwargs)

    def _get_dtype(self) -> np.dtype:
        return self.data.dtype

    def _get_maxshape(self) -> tuple:
        return self.data.shape

    def _get_data(self, selection: Tuple[slice]) -> np.ndarray:
        return self.data[selection]
