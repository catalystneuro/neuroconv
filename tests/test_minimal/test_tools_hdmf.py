import numpy as np
from numpy.testing import assert_array_equal
from hdmf.testing import TestCase

from neuroconv.tools.hdmf import SliceableDataChunkIterator


class TestIteratorAssertions(TestCase):
    def test_buffer_bigger_than_chunk_assertion(self):
        with self.assertRaisesWith(
            AssertionError, exc_msg="buffer_gb (5e-06) must be greater than the chunk size (0.000996872)!"
        ):
            SliceableDataChunkIterator(data=np.empty(shape=(1000, 1000)), buffer_gb=0.000005)


def test_early_exit():
    """Uses a 32 byte array with 1 GB buffer size (default) and 1 MB chunk size (default)."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(2, 2)))
    assert iterator.maxshape == iterator.buffer_shape


def test_buffer_padding_long_shape():
    """Uses ~8 MB array with 11 MB buffer size and 1 MB chunk size (default)."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(10**7, 20)), buffer_gb=1.1e-2)
    assert iterator.buffer_shape == (68482, 20)


def test_buffer_padding_mixed_shape():
    """Uses ~15 MB array with 11 MB buffer size and 1 MB chunk size (default)."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(20, 40, 2401)), buffer_gb=1.1e-2)
    assert iterator.buffer_shape == (16, 32, 1920)


def test_min_axis_too_large():
    """uses ~8 MB array with each contiguous axis at around ~8 KB with 5 KB buffer_size and 1 KB chunk size."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(1000, 1000)), chunk_mb=1e-3, buffer_gb=5e-6)
    assert iterator.buffer_shape == (22, 22)


def test_sliceable_data_chunk_iterator():

    data = np.arange(100).reshape(10, 10)

    dci = SliceableDataChunkIterator(data=data, buffer_shape=(5, 5), chunk_shape=(5, 5))

    data_chunk = next(dci)

    assert data_chunk.selection == (slice(0, 5, None), slice(0, 5, None))

    assert_array_equal(
        data_chunk.data,
        [[0, 1, 2, 3, 4], [10, 11, 12, 13, 14], [20, 21, 22, 23, 24], [30, 31, 32, 33, 34], [40, 41, 42, 43, 44]],
    )
