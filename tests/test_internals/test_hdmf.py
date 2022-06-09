import numpy as np
from hdmf.testing import TestCase

from nwb_conversion_tools.tools.hdmf import SliceableDataChunkIterator


class TestIteratorAssertions(TestCase):
    def test_buffer_bigger_than_chunk_assertion(self):
        with self.assertRaisesWith(
            AssertionError, exc_msg="buffer_gb (5e-06) must be greater than the chunk size (0.000996872)!"
        ):
<<<<<<< HEAD
            SliceableDataChunkIterator(data=np.empty(shape=(1000, 1000)), buffer_gb=0.000005)
=======
            SliceableDataChunkIterator(data=np.random.random(size=(10**3, 10**3)), buffer_gb=0.000005)
>>>>>>> 483ae8ecf15245acbb4705313c6932c6833c62eb


def test_early_exit():
    """Uses a 32 byte array with 1 GB buffer size (default) and 1 MB chunk size (default)."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(2, 2)))
    assert iterator.maxshape == iterator.buffer_shape


def test_buffer_padding_long_shape():
    """Uses ~8 MB array with 11 MB buffer size and 1 MB chunk size (default)."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(160000, 20)), buffer_gb=1.1e-2)
    assert iterator.buffer_shape == (48000, 20)


def test_buffer_padding_mixed_shape():
    """Uses ~15 MB array with 11 MB buffer size and 1 MB chunk size (default)."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(20, 40, 2401)), buffer_gb=1.1e-2)
    assert iterator.buffer_shape == (20, 40, 960)


def test_min_axis_too_large():
    """uses ~8 MB array with each contiguous axis at around ~8 KB with 5 KB buffer_size and 1 KB chunk size."""
<<<<<<< HEAD
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(10 ** 3, 10 ** 3)), chunk_mb=1e-3, buffer_gb=5e-6)
=======
    iterator = SliceableDataChunkIterator(data=np.zeros(shape=(10**3, 10**3)), chunk_mb=1e-3, buffer_gb=5e-6)
>>>>>>> 483ae8ecf15245acbb4705313c6932c6833c62eb
    assert iterator.buffer_shape == (22, 22)
