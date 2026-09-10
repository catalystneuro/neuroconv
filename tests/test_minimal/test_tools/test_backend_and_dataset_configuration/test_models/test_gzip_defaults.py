"""Gzip defaults agree across backends without overriding caller settings."""

import pytest
from numcodecs import GZip

from neuroconv.tools.testing import mock_HDF5DatasetIOConfiguration, mock_ZarrDatasetIOConfiguration


@pytest.mark.parametrize(
    "options,expected_level", [(None, 4), ({}, 4), ({"level": 0}, 0), ({"level": 1}, 1), ({"level": 9}, 9)]
)
@pytest.mark.parametrize("with_shuffle", [False, True])
def test_gzip_level_agrees_across_backends(options, expected_level, with_shuffle):
    compressors = ["shuffle", "gzip"] if with_shuffle else ["gzip"]
    compressor_options = [None, options] if with_shuffle else [options]
    hdf5 = mock_HDF5DatasetIOConfiguration(compressors=compressors, compressor_options=compressor_options)
    zarr = mock_ZarrDatasetIOConfiguration(compressors=compressors, compressor_options=compressor_options)

    assert hdf5.get_data_io_kwargs()["compression_opts"] == expected_level
    assert zarr.get_data_io_kwargs()["compressor"].level == expected_level
    assert hdf5.compressor_options == compressor_options
    assert zarr.compressor_options == compressor_options


def test_gzip_instance_is_preserved():
    compressor = GZip(level=1)
    configuration = mock_ZarrDatasetIOConfiguration(compressors=[compressor])
    assert configuration.get_data_io_kwargs()["compressor"] is compressor


def test_hdf5_existing_gzip_options_are_preserved():
    configuration = mock_HDF5DatasetIOConfiguration(compressor_options=[{"compression_opts": 0}])
    assert configuration.get_data_io_kwargs()["compression_opts"] == 0


def test_other_hdf5_compression_does_not_receive_gzip_level():
    configuration = mock_HDF5DatasetIOConfiguration(compressors=["lzf"])
    assert configuration.get_data_io_kwargs()["compression_opts"] is None
