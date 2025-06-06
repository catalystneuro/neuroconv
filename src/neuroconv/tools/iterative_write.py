import math

import numpy as np


def get_image_series_chunk_shape(
    *,
    num_samples: int,
    sample_shape: tuple[int, int, int] | tuple[int, int, int, int],
    dtype: np.dtype,
    chunk_mb: float = 10.0,
) -> tuple[int, int]:
    """
    Estimate good chunk shape for a ImageSeries dataset.

    This function gives good estimates for cloud access patterns.

    Parameters
    ----------
    num_samples : int
        The number of frames in the ImageSeries dataset.
    sample_shape : tuple[int, int, int] | tuple[int, int, int, int]
        The shape of a single sample for the ImageSeries.
        For TwoPhotonSeries, this might be (num_columns, num_rows) or (num_columns, num_rows, num_planes).
        For ImageSeries, this might be (num_columns, num_rows, num_channels).
    dtype : np.dtype
        The data type of the ImageSeries dataset.
    chunk_mb : float, optional
        The upper bound on size in megabytes (MB) of the internal chunk for the HDF5 dataset.
        The default is 10MB, as recommended by the HDF5 group.

    Returns
    -------
    tuple[int, int, int] | tuple[int, int, int, int]
        The chunk shape for the TwoPhotonSeries dataset.
    """
    assert chunk_mb > 0, f"chunk_mb ({chunk_mb}) must be greater than zero!"

    num_rows = int(sample_shape[0])
    num_columns = int(sample_shape[1])
    frame_size_bytes = num_rows * num_columns * dtype.itemsize

    chunk_size_bytes = chunk_mb * 1e6
    num_samples_per_chunk = int(chunk_size_bytes / frame_size_bytes)

    # Clip the number of frames between 1 and num_samples
    num_samples_per_chunk = min(num_samples_per_chunk, num_samples)
    num_samples_per_chunk = max(num_samples_per_chunk, 1)

    chunk_shape = (num_samples_per_chunk, num_rows, num_columns)

    if len(sample_shape) == 3:
        chunk_shape = chunk_shape + (1,)

    return chunk_shape


def get_image_series_buffer_shape(
    *,
    chunk_shape: tuple[int, int, int] | tuple[int, int, int, int],
    sample_shape: tuple[int, int, int] | tuple[int, int, int, int],
    series_shape: tuple[int, int, int] | tuple[int, int, int, int],
    dtype: np.dtype,
    buffer_gb: float = 1.0,
) -> tuple[int, int, int] | tuple[int, int, int, int]:
    """
    Estimate good buffer shape for a ImageSeries dataset.

    This function gives good estimates for cloud access patterns.

    Parameters
    ----------
    chunk_shape : tuple[int, int, int] | tuple[int, int, int, int]
        The shape of the chunk for the ImageSeries dataset.
    sample_shape : tuple[int, int, int] | tuple[int, int, int, int]
        The shape of a single sample for the ImageSeries.
        For TwoPhotonSeries, this might be (num_columns, num_rows) or (num_columns, num_rows, num_planes).
        For ImageSeries, this might be (num_columns, num_rows, num_channels).
    series_shape : tuple[int, int, int] | tuple[int, int, int, int]
        The shape of the full ImageSeries dataset.
    dtype : np.dtype
        The data type of the ImageSeries dataset.
    buffer_gb : float
        The upper bound on size in gigabytes (GB) of the internal chunk for the HDF5 dataset.

    Returns
    -------
    tuple[int, int] | tuple[int, int, int]
        The buffer shape for the TwoPhotonSeries dataset.
    """
    assert buffer_gb > 0, f"buffer_gb ({buffer_gb}) must be greater than zero!"

    # First we determined a minimal buffer shape, this is a chunk shape but we included
    # the full last dimension (note that chunk_shape last dimension is 1 or omitted)
    num_frames_in_chunk = int(chunk_shape[0])
    sample_shape = tuple(int(dim) for dim in sample_shape)
    min_buffer_shape = (num_frames_in_chunk,) + sample_shape

    # The smallest the buffer could be is the size of a chunk
    bytes_per_element = dtype.itemsize
    minimal_buffer_size_in_bytes = math.prod(min_buffer_shape) * bytes_per_element

    desired_buffer_size_in_bytes = buffer_gb * 1e9
    scaling_factor = desired_buffer_size_in_bytes // minimal_buffer_size_in_bytes
    num_frames_in_buffer = num_frames_in_chunk * scaling_factor

    # This is the largest buffer that still fits within the buffer_gb
    max_buffer_shape = tuple([num_frames_in_buffer]) + sample_shape

    corrected_buffer_shape = []

    # We need to clip every element to be between the minimal and maximal values
    minimal_values = min_buffer_shape
    maximal_values = series_shape
    for dimension_index, dimension_length in enumerate(max_buffer_shape):
        min_size = minimal_values[dimension_index]
        max_size = maximal_values[dimension_index]
        scaled_size = max(int(dimension_length), min_size)
        scaled_size = min(scaled_size, max_size)
        corrected_buffer_shape.append(scaled_size)

    return tuple(corrected_buffer_shape)


def get_electrical_series_chunk_shape(
    *,
    number_of_channels: int,
    number_of_frames: int,
    dtype: np.dtype,
    chunk_mb: float = 10.0,
) -> tuple[int, int]:
    """
    Estimate good chunk shape for an ElectricalSeries dataset.

    This function gives good estimates for cloud access patterns.

    Parameters
    ----------
    number_of_channels : int
        The number of channels in the ElectricalSeries dataset.
    number_of_frames : int
        The number of frames in the ElectricalSeries dataset.
    dtype : np.dtype
        The data type of the ElectricalSeries dataset.
    chunk_mb : float, optional
        The upper bound on size in megabytes (MB) of the internal chunk for the HDF5 dataset.
        The chunk_shape will be set implicitly by this argument.

    Returns
    -------
    tuple[int, int]
        The chunk shape for the ElectricalSeries dataset.
    """
    assert chunk_mb > 0, f"chunk_mb ({chunk_mb}) must be greater than zero!"

    # We use 64 channels as that gives enough time for common sampling rates when chunk_mb == 10.0
    # See # from https://github.com/flatironinstitute/neurosift/issues/52#issuecomment-1671405249
    chunk_channels = min(64, number_of_channels)

    size_of_chunk_channels_bytes = chunk_channels * dtype.itemsize
    total_chunk_space_bytes = chunk_mb * 1e6

    # We allocate as many frames as possible with the remaining space of the chunk
    chunk_frames = total_chunk_space_bytes // size_of_chunk_channels_bytes

    # We clip by the number of frames if the samples are too small
    chunk_frames = min(chunk_frames, number_of_frames)

    return (chunk_frames, chunk_channels)
