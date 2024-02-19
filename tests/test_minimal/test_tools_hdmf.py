import numpy as np
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal

from neuroconv.tools.hdmf import SliceableDataChunkIterator


class TestIteratorAssertions(TestCase):
    def test_buffer_bigger_than_chunk_assertion(self):
        with self.assertRaisesWith(
            AssertionError, exc_msg="buffer_gb (5e-06) must be greater than the chunk size (0.008)!"
        ):
            SliceableDataChunkIterator(data=np.empty(shape=(1000, 1000)), buffer_gb=0.000005)


def test_early_exit():
    """Uses a 32 byte array with 1 GB buffer size (default) and 1 MB chunk size (default)."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(2, 2)))
    assert iterator.maxshape == iterator.buffer_shape


def test_buffer_padding_long_shape():
    """Uses ~8 MB array with 11 MB buffer size and 1 MB chunk size (default)."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(10**7, 20)), buffer_gb=1.1e-2)
    assert iterator.buffer_shape == (1000000, 1)


def test_buffer_padding_mixed_shape():
    """Uses ~15 MB array with 11 MB buffer size and 1 MB chunk size (default)."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(20, 40, 2401)), buffer_gb=1.1e-2)
    assert iterator.buffer_shape == (17, 34, 2040)


def test_min_axis_too_large():
    """Uses ~8 MB array with each contiguous axis at around ~8 KB with 5 KB buffer_size and 1 KB chunk size."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(1000, 1000)), chunk_mb=1e-3, buffer_gb=5e-6)
    assert iterator.buffer_shape == (22, 22)


def test_sliceable_data_chunk_iterator():
    data = np.arange(100).reshape(10, 10)

    iterator = SliceableDataChunkIterator(data=data, buffer_shape=(5, 5), chunk_shape=(5, 5))

    data_chunk = next(iterator)

    assert data_chunk.selection == (slice(0, 5, None), slice(0, 5, None))

    assert_array_equal(
        data_chunk.data,
        [[0, 1, 2, 3, 4], [10, 11, 12, 13, 14], [20, 21, 22, 23, 24], [30, 31, 32, 33, 34], [40, 41, 42, 43, 44]],
    )


def test_sliceable_data_chunk_iterator_edge_case_1():
    """Caused in error prior to https://github.com/catalystneuro/neuroconv/pull/735."""
    shape = (3600, 304, 608)
    buffer_gb = 0.5

    random_number_generator = np.random.default_rng(seed=0)
    dtype = "uint16"

    low = np.iinfo(dtype).min
    high = np.iinfo(dtype).max
    integer_array = random_number_generator.integers(low=low, high=high, size=shape, dtype=dtype)

    iterator = SliceableDataChunkIterator(data=integer_array, buffer_gb=buffer_gb)

    assert iterator.buffer_shape == (2013, 183, 366)
    assert iterator.chunk_shape == (671, 61, 122)
