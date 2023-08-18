"""Collection of modifications of HDMF functions that are to be tested/used on this repo until propagation upstream."""
from typing import Tuple
from typing import Dict

import numpy as np
from hdmf.data_utils import GenericDataChunkIterator as HDMFGenericDataChunkIterator


class GenericDataChunkIterator(HDMFGenericDataChunkIterator):
    def _get_default_buffer_shape(self, buffer_gb: float = 1.0) -> Tuple[int]:
        num_axes = len(self.maxshape)
        chunk_bytes = np.prod(self.chunk_shape) * self.dtype.itemsize
        assert buffer_gb > 0, f"buffer_gb ({buffer_gb}) must be greater than zero!"
        assert (
            buffer_gb >= chunk_bytes / 1e9
        ), f"buffer_gb ({buffer_gb}) must be greater than the chunk size ({chunk_bytes / 1e9})!"
        assert all(
            np.array(self.chunk_shape) > 0
        ), f"Some dimensions of chunk_shape ({self.chunk_shape}) are less than zero!"

        maxshape = np.array(self.maxshape)

        # Early termination condition
        if np.prod(maxshape) * self.dtype.itemsize / 1e9 < buffer_gb:
            return tuple(self.maxshape)

        buffer_bytes = chunk_bytes
        axis_sizes_bytes = maxshape * self.dtype.itemsize
        smallest_chunk_axis, second_smallest_chunk_axis, *_ = np.argsort(self.chunk_shape)
        target_buffer_bytes = buffer_gb * 1e9

        # If the smallest full axis does not fit within the buffer size, form a square along the two smallest axes
        sub_square_buffer_shape = np.array(self.chunk_shape)
        if min(axis_sizes_bytes) > target_buffer_bytes:
            k1 = np.floor((target_buffer_bytes / chunk_bytes) ** 0.5)
            for axis in [smallest_chunk_axis, second_smallest_chunk_axis]:
                sub_square_buffer_shape[axis] = k1 * sub_square_buffer_shape[axis]
            return tuple(sub_square_buffer_shape)

        # Original one-shot estimation has good performance for certain shapes
        chunk_to_buffer_ratio = buffer_gb * 1e9 / chunk_bytes
        chunk_scaling_factor = np.floor(chunk_to_buffer_ratio ** (1 / num_axes))
        unpadded_buffer_shape = [
            np.clip(a=int(x), a_min=self.chunk_shape[j], a_max=self.maxshape[j])
            for j, x in enumerate(chunk_scaling_factor * np.array(self.chunk_shape))
        ]

        unpadded_buffer_bytes = np.prod(unpadded_buffer_shape) * self.dtype.itemsize

        # Method that starts by filling the smallest axis completely or calculates best partial fill
        padded_buffer_shape = np.array(self.chunk_shape)
        chunks_per_axis = np.ceil(maxshape / self.chunk_shape)
        small_axis_fill_size = chunk_bytes * min(chunks_per_axis)
        full_axes_used = np.zeros(shape=num_axes, dtype=bool)
        if small_axis_fill_size <= target_buffer_bytes:
            buffer_bytes = small_axis_fill_size
            padded_buffer_shape[smallest_chunk_axis] = self.maxshape[smallest_chunk_axis]
            full_axes_used[smallest_chunk_axis] = True
        for axis, chunks_on_axis in enumerate(chunks_per_axis):
            if full_axes_used[axis]:  # If the smallest axis, skip since already used
                continue
            if chunks_on_axis * buffer_bytes <= target_buffer_bytes:  # If multiple axes can be used together
                buffer_bytes *= chunks_on_axis
                padded_buffer_shape[axis] = self.maxshape[axis]
            else:  # Found an axis that is too large to use with the rest of the buffer; calculate how much can be used
                k3 = np.floor(target_buffer_bytes / buffer_bytes)
                padded_buffer_shape[axis] *= k3
                break
        padded_buffer_bytes = np.prod(padded_buffer_shape) * self.dtype.itemsize

        if padded_buffer_bytes >= unpadded_buffer_bytes:
            return tuple(padded_buffer_shape)
        else:
            return tuple(unpadded_buffer_shape)


class SliceableDataChunkIterator(GenericDataChunkIterator):
    """
    Generic data chunk iterator that works for any memory mapped array, such as a np.memmap or an h5py.Dataset
    """
    
    def __init__(self, data, **base_kwargs):
        self.data = data
        
        self._base_kwargs = base_kwargs
        super().__init__(**base_kwargs)

    def _get_dtype(self) -> np.dtype:
        return self.data.dtype

    def _get_maxshape(self) -> tuple:
        return self.data.shape

    def _get_data(self, selection: Tuple[slice]) -> np.ndarray:
        return self.data[selection]

    def is_pickleable(self) -> bool:
        if isinstance(self.data, (np.memmap, np.array)):
            return True
        return False

    def __reduce__(self):
        instance_constructor = self._from_dict
        initialization_args = (self._to_dict(),)
        return (instance_constructor, initialization_args)
    
    def _to_dict(self) -> Dict:
        dictionary = dict()
        if isinstance(self.data, np.memmap):
            dictionary["source_type"] = "memmap"
            dictionary["base_kwargs"] = self._base_kwargs
            dictionary["load_kwargs"] = dict(
                filename=str(self.data.filename),  # TODO: check if can be relative
                dtype=str(self.data.dtype),
                shape=tuple(self.data.shape),
            )
            # TODO: if relative, need base path as well to make an absolute at time of pickling
            # (not for persistence or sharing but for sending over ProcessPool)
        else:
            raise ValueError(f"Source type ({source_type}) is not yet supported!")

        return dictionary

    @staticmethod
    def _from_dict(dictionary: dict) -> GenericDataChunkIterator: # TODO: need to investigate the need of base path
        source_type = dictionary["source_type"]

        if source_type == "memmap":
            data = np.memmap(**dictionary["load_kwargs"])
        else:
            raise ValueError(f"Source type ({source_type}) is not yet supported!")

        iterator = SliceableDataChunkIterator(data=data, **dictionary["base_kwargs"])
        return iterator
