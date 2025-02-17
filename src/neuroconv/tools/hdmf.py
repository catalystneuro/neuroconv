"""Collection of modifications of HDMF functions that are to be tested/used on this repo until propagation upstream."""

import math
import warnings
from typing import Union

import numpy as np
from hdmf.build.builders import (
    BaseBuilder,
    LinkBuilder,
)
from hdmf.data_utils import GenericDataChunkIterator as HDMFGenericDataChunkIterator
from hdmf.utils import get_data_shape


class GenericDataChunkIterator(HDMFGenericDataChunkIterator):  # noqa: D101
    # TODO Should this be added to the API?

    def _get_default_buffer_shape(self, buffer_gb: float = 1.0) -> tuple[int]:
        return self.estimate_default_buffer_shape(
            buffer_gb=buffer_gb, chunk_shape=self.chunk_shape, maxshape=self.maxshape, dtype=self.dtype
        )

    # TODO: move this to the core iterator in HDMF so it can be easily swapped out as well as run on its own
    @staticmethod
    def estimate_default_chunk_shape(chunk_mb: float, maxshape: tuple[int, ...], dtype: np.dtype) -> tuple[int, ...]:
        """
        Select chunk shape with size in MB less than the threshold of chunk_mb.

        Keeps the dimensional ratios of the original data.
        """
        # Elevate any overflow warnings to trigger error.
        # This is usually an indicator of something going terribly wrong with the estimation calculations and should be
        # avoided at all costs.
        warnings.filterwarnings(action="error", message="overflow encountered *")

        assert chunk_mb > 0.0, f"chunk_mb ({chunk_mb}) must be greater than zero!"
        # Eventually, Pydantic validation can handle this validation for us

        n_dims = len(maxshape)
        itemsize = dtype.itemsize
        chunk_bytes = chunk_mb * 1e6

        min_maxshape = min(maxshape)
        v = tuple(math.floor(maxshape_axis / min_maxshape) for maxshape_axis in maxshape)
        prod_v = math.prod(v)
        while prod_v * itemsize > chunk_bytes and prod_v != 1:
            non_unit_min_v = min(x for x in v if x != 1)
            v = tuple(math.floor(x / non_unit_min_v) if x != 1 else x for x in v)
            prod_v = math.prod(v)
        k = math.floor((chunk_bytes / (prod_v * itemsize)) ** (1 / n_dims))
        return tuple([min(k * x, maxshape[dim]) for dim, x in enumerate(v)])

    # TODO: move this to the core iterator in HDMF so it can be easily swapped out as well as run on its own
    @staticmethod
    def estimate_default_buffer_shape(
        buffer_gb: float, chunk_shape: tuple[int, ...], maxshape: tuple[int, ...], dtype: np.dtype
    ) -> tuple[int, ...]:
        # TODO: Ad ddocstring to this once someone understands it better
        # Elevate any overflow warnings to trigger error.
        # This is usually an indicator of something going terribly wrong with the estimation calculations and should be
        # avoided at all costs.
        warnings.filterwarnings(action="error", message="overflow encountered *")

        num_axes = len(maxshape)
        chunk_bytes = math.prod(chunk_shape) * dtype.itemsize

        assert num_axes > 0, f"The number of axes ({num_axes}) is less than one!"
        assert buffer_gb > 0, f"buffer_gb ({buffer_gb}) must be greater than zero!"
        assert (
            buffer_gb >= chunk_bytes / 1e9
        ), f"buffer_gb ({buffer_gb}) must be greater than the chunk size ({chunk_bytes / 1e9})!"
        assert all(np.array(chunk_shape) > 0), f"Some dimensions of chunk_shape ({chunk_shape}) are less than zero!"

        # Early termination condition
        if math.prod(maxshape) * dtype.itemsize / 1e9 < buffer_gb:
            return tuple(maxshape)

        # Note: must occur after taking `math.prod` of it in line above; otherwise it triggers an overflow warning
        maxshape = np.array(maxshape)

        buffer_bytes = chunk_bytes
        axis_sizes_bytes = maxshape * dtype.itemsize
        target_buffer_bytes = buffer_gb * 1e9

        # Recording indices of shortest axes for later use
        if num_axes > 1:  # Only store two shortest if more than 1
            smallest_chunk_axis, second_smallest_chunk_axis, *_ = np.argsort(chunk_shape)
        elif num_axes == 1:
            smallest_chunk_axis = 0

        if min(axis_sizes_bytes) > target_buffer_bytes:
            if num_axes > 1:
                # If the smallest full axis does not fit within the buffer size, form a square along the smallest axes
                sub_square_buffer_shape = np.array(chunk_shape)
                if min(axis_sizes_bytes) > target_buffer_bytes:
                    k1 = math.floor((target_buffer_bytes / chunk_bytes) ** 0.5)
                    for axis in [smallest_chunk_axis, second_smallest_chunk_axis]:
                        sub_square_buffer_shape[axis] = k1 * sub_square_buffer_shape[axis]
                    return tuple(sub_square_buffer_shape)
            elif num_axes == 1:
                # Handle the case where the single axis is too large to fit in the buffer
                k1 = math.floor(target_buffer_bytes / chunk_bytes)
                return (k1 * chunk_shape[0],)

        # Original one-shot estimation has good performance for certain shapes
        chunk_to_buffer_ratio = buffer_gb * 1e9 / chunk_bytes
        chunk_scaling_factor = math.floor(chunk_to_buffer_ratio ** (1 / num_axes))
        unpadded_buffer_shape = tuple(
            int(np.clip(a=int(x), a_min=chunk_shape[j], a_max=maxshape[j]))
            for j, x in enumerate(chunk_scaling_factor * np.array(chunk_shape))
        )

        unpadded_buffer_bytes = math.prod(unpadded_buffer_shape) * dtype.itemsize

        # Method that starts by filling the smallest axis completely or calculates the best partial fill
        padded_buffer_shape = np.array(chunk_shape)
        chunks_per_axis = np.ceil(maxshape / chunk_shape)
        small_axis_fill_size = chunk_bytes * min(chunks_per_axis)
        full_axes_used = np.zeros(shape=num_axes, dtype=bool)
        if small_axis_fill_size <= target_buffer_bytes:
            buffer_bytes = small_axis_fill_size
            padded_buffer_shape[smallest_chunk_axis] = maxshape[smallest_chunk_axis]
            full_axes_used[smallest_chunk_axis] = True
        for axis, chunks_on_axis in enumerate(chunks_per_axis):
            if full_axes_used[axis]:  # If the smallest axis, skip since already used
                continue
            if chunks_on_axis * buffer_bytes <= target_buffer_bytes:  # If multiple axes can be used together
                buffer_bytes *= chunks_on_axis
                padded_buffer_shape[axis] = maxshape[axis]
            else:  # Found an axis that is too large to use with the rest of the buffer; calculate how much can be used
                k3 = math.floor(target_buffer_bytes / buffer_bytes)
                padded_buffer_shape[axis] *= k3
                break
        padded_buffer_shape = tuple(int(value) for value in padded_buffer_shape)  # To avoid overflow from math.prod

        padded_buffer_bytes = math.prod(padded_buffer_shape) * dtype.itemsize

        if padded_buffer_bytes >= unpadded_buffer_bytes:
            return padded_buffer_shape
        else:
            return unpadded_buffer_shape


class SliceableDataChunkIterator(GenericDataChunkIterator):
    """
    Generic data chunk iterator that works for any memory mapped array, such as a np.memmap or h5py.Dataset object.
    """

    def __init__(self, data, **kwargs):
        self.data = data
        super().__init__(**kwargs)

    def _get_dtype(self) -> np.dtype:
        return self.data.dtype

    def _get_maxshape(self) -> tuple:
        return self.data.shape

    def _get_data(self, selection: tuple[slice]) -> np.ndarray:
        return self.data[selection]


def get_full_data_shape(
    dataset: Union[GenericDataChunkIterator, np.ndarray, list],
    location_in_file: str,
    builder: Union[BaseBuilder, None] = None,
):
    """Get the full shape of the dataset at the given location in the file.

    Parameters
    ----------
    dataset : hdmf.data_utils.GenericDataChunkIterator | np.ndarray | list
        The dataset to get the shape of.
    location_in_file : str
        The location of the dataset within the NWBFile, e.g. 'acquisition/ElectricalSeries/data'.
    builder : hdmf.build.builders.BaseBuilder | None
        The builder object that would be used to construct the NWBFile object. If None, the dataset is assumed to NOT
        have a compound dtype.

    Notes
    -----
    This function is used instead of hdmf.utils.get_data_shape() to handle datasets with compound dtypes. Currently, if
    a dataset has a compound dtype in NWB, the builder will write it as (len(dataset,), but hdmf.utils.get_data_shape()
    will return the shape of the dataset as if it were a regular single-dtype array (ex. (N, M) instead of (N,)).
    """
    if builder is not None and has_compound_dtype(builder=builder, location_in_file=location_in_file):
        return (len(dataset),)
    return get_data_shape(data=dataset)


def has_compound_dtype(builder: BaseBuilder, location_in_file: str) -> bool:
    """
    Determine if the dataset at the given location in the file has a compound dtype.

    Parameters
    ----------
    builder : hdmf.build.builders.BaseBuilder
        The builder object that would be used to construct the NWBFile object.
    location_in_file : str
        The location of the dataset within the NWBFile, e.g. 'acquisition/ElectricalSeries/data'.

    Returns
    -------
    bool
        Whether the dataset has a compound dtype.
    """
    dataset_builder = get_dataset_builder(builder, location_in_file)
    return isinstance(dataset_builder.dtype, list)


def get_dataset_builder(builder: BaseBuilder, location_in_file: str) -> BaseBuilder:
    """Find the appropriate sub-builder for the dataset at the given location in the file.

    This function will traverse the groups in the location_in_file until it reaches a DatasetBuilder,
    and then return that builder.

    Parameters
    ----------
    builder : hdmf.build.builders.BaseBuilder
        The builder object that would be used to construct the NWBFile object.
    location_in_file : str
        The location of the dataset within the NWBFile, e.g. 'acquisition/ElectricalSeries/data'.

    Returns
    -------
    hdmf.build.builders.BaseBuilder
        The builder object for the dataset at the given location.

    Raises
    ------
    ValueError
        If the location_in_file is not found in the builder.

    Notes
    -----
    Items in defined top-level places like electrodes may not be in the groups of the nwbfile-level builder,
    but rather in hidden locations like general/extracellular_ephys/electrodes.
    Also, some items in these top-level locations may interrupt the order of the location_in_file.
    For example, when location_in_file is 'stimulus/AcousticWaveformSeries/data', the builder for that dataset is
    located at 'stimulus/presentation/AcousticWaveformSeries/data'.
    For this reason, we recursively search for the appropriate sub-builder for each name in the location_in_file.
    Also, the first name in location_in_file is inherently suspect due to the way that the location is determined
    in _find_location_in_memory_nwbfile(), and may not be present in the builder. For example, when location_in_file is
    'lab_meta_data/fiber_photometry/fiber_photometry_table/location/data', the builder for that dataset is located at
    'general/fiber_photometry/fiber_photometry_table/location/data'.
    """
    split_location = iter(location_in_file.split("/"))
    name = next(split_location)

    if _find_sub_builder(builder, name) is None:
        name = next(split_location)

    while name not in builder.datasets and name not in builder.links:
        builder = _find_sub_builder(builder, name)
        if builder is None:
            raise ValueError(f"Could not find location '{location_in_file}' in builder ({name} is missing).")
        try:
            name = next(split_location)
        except StopIteration:
            raise ValueError(f"Could not find location '{location_in_file}' in builder ({name} is not a dataset).")
    builder = builder[name]
    if isinstance(builder, LinkBuilder):
        builder = builder.builder
    return builder


def _find_sub_builder(builder: BaseBuilder, name: str) -> BaseBuilder:
    """Search breadth-first for a sub-builder by name in a builder object.

    Parameters
    ----------
    builder : hdmf.build.builders.BaseBuilder
        The builder object to search for the sub-builder in.
    name : str
        The name of the sub-builder to search for.

    Returns
    -------
    hdmf.build.builders.BaseBuilder
        The sub-builder with the given name, or None if it could not be found.
    """
    sub_builders = list(builder.groups.values())
    return _recursively_search_sub_builders(sub_builders=sub_builders, name=name)


def _recursively_search_sub_builders(sub_builders: list[BaseBuilder], name: str) -> BaseBuilder:
    """Recursively search for a sub-builder by name in a list of sub-builders.

    Parameters
    ----------
    sub_builders : list[hdmf.build.builders.BaseBuilder]
        The list of sub-builders to search for the sub-builder in.
    name : str
        The name of the sub-builder to search for.

    Returns
    -------
    hdmf.build.builders.BaseBuilder
        The sub-builder with the given name, or None if it could not be found.
    """
    sub_sub_builders = []
    for sub_builder in sub_builders:
        if sub_builder.name == name:
            return sub_builder
        sub_sub_builders.extend(list(sub_builder.groups.values()))
    if len(sub_sub_builders) == 0:
        return None
    return _recursively_search_sub_builders(sub_builders=sub_sub_builders, name=name)
