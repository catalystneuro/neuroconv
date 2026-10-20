"""Gzip defaults agree across backends without overriding caller settings."""

import pytest
import zarr
from packaging.version import Version

from neuroconv.tools.testing import mock_HDF5DatasetIOConfiguration, mock_ZarrDatasetIOConfiguration

# The Zarr backend requires zarr 3, which only installs on Python 3.14 and newer.
requires_zarr_3 = pytest.mark.skipif(Version(zarr.__version__).major < 3, reason="The Zarr backend requires zarr 3")


@pytest.mark.parametrize(
    "options,expected_level", [(None, 4), ({}, 4), ({"level": 0}, 0), ({"level": 1}, 1), ({"level": 9}, 9)]
)
@pytest.mark.parametrize("with_shuffle", [False, True])
@requires_zarr_3
def test_gzip_level_agrees_across_backends(options, expected_level, with_shuffle):
    compressors = ["shuffle", "gzip"] if with_shuffle else ["gzip"]
    compressor_options = [None, options] if with_shuffle else [options]
    hdf5 = mock_HDF5DatasetIOConfiguration(compressors=compressors, compressor_options=compressor_options)
    zarr = mock_ZarrDatasetIOConfiguration(compressors=compressors, compressor_options=compressor_options)

    assert hdf5.get_data_io_kwargs()["compression_opts"] == expected_level
    assert zarr.get_data_io_kwargs()["compressors"][-1].level == expected_level
    assert hdf5.compressor_options == compressor_options
    assert zarr.compressor_options == compressor_options


@requires_zarr_3
def test_gzip_instance_is_preserved():
    from zarr.codecs import GzipCodec

    compressor = GzipCodec(level=1)
    configuration = mock_ZarrDatasetIOConfiguration(compressors=[compressor])
    assert configuration.get_data_io_kwargs()["compressors"][0] is compressor


def test_hdf5_existing_gzip_options_are_preserved():
    configuration = mock_HDF5DatasetIOConfiguration(compressor_options=[{"compression_opts": 0}])
    assert configuration.get_data_io_kwargs()["compression_opts"] == 0


def test_other_hdf5_compression_does_not_receive_gzip_level():
    configuration = mock_HDF5DatasetIOConfiguration(compressors=["lzf"])
    assert configuration.get_data_io_kwargs()["compression_opts"] is None
