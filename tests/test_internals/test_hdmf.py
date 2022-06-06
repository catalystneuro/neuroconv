import numpy as np
from hdmf.testing import TestCase

from nwb_conversion_tools.tools.hdmf import SliceableDataChunkIterator


class TestIteratorAssertions(TestCase):
    def test_buffer_bigger_than_chunk_assertion(self):
        with self.assertRaisesWith(
            AssertionError, exc_msg="buffer_gb (5e-06) must be greater than the chunk size (0.000996872)!"
        ):
            SliceableDataChunkIterator(data=np.random.random(size=(10 ** 3, 10 ** 3)), buffer_gb=0.000005)


def test_early_exit():
    iterator = SliceableDataChunkIterator(data=np.random.random(size=(10 ** 6, 200)), buffer_gb=2.0)
    assert iterator.maxshape == iterator.buffer_shape


def test_buffer_padding_long_shape():
    iterator = SliceableDataChunkIterator(data=np.random.random(size=(10 ** 6, 200)))
    assert iterator.buffer_shape == (625000, 200)


def test_buffer_padding_mixed_shape():
    iterator = SliceableDataChunkIterator(data=np.random.random(size=(20, 40, 7 ** 4)))
    assert iterator.buffer_shape == (20, 40, 2401)


def test_min_axis_too_large():
    iterator = SliceableDataChunkIterator(data=np.random.random(size=(10 ** 3, 10 ** 3)), chunk_mb=1e-3, buffer_gb=5e-6)
    assert iterator.buffer_shape == (22, 22)
