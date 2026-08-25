"""Unit tests for the HDF5DatasetIOConfiguration Pydantic model."""

from io import StringIO
from unittest.mock import patch

from neuroconv.tools.nwb_helpers import (
    AVAILABLE_HDF5_COMPRESSION_METHODS,
    HDF5DatasetIOConfiguration,
)
from neuroconv.tools.testing import mock_HDF5DatasetIOConfiguration


def test_hdf5_dataset_configuration_print():
    """Test the printout display of a HDF5DatasetIOConfiguration model looks nice."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration()

    with patch("sys.stdout", new=StringIO()) as out:
        print(hdf5_dataset_configuration)

    expected_print = """
acquisition/TestElectricalSeries/data
-------------------------------------
  dtype : int16
  full shape of source array : (1800000, 384)
  full size of source array : 1.38 GB

  buffer shape : (1250000, 384)
  expected RAM usage : 960.00 MB

  chunk shape : (78125, 64)
  disk space usage per chunk : 10.00 MB

  compression method : gzip

"""
    assert out.getvalue() == expected_print


def test_hdf5_dataset_configuration_print_with_compression_options():
    """The compression options line renders only when options are set."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compression_options=dict(level=5))

    printout = str(hdf5_dataset_configuration)

    assert "  compression method : gzip" in printout
    assert "  compression options : {'level': 5}" in printout


def test_hdf5_dataset_configuration_print_with_compression_disabled():
    """Neither compression line renders when compression is disabled."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compression_method=None)

    printout = str(hdf5_dataset_configuration)

    assert "compression method" not in printout
    assert "compression options" not in printout


def test_available_hdf5_compression_methods_not_empty():
    assert len(AVAILABLE_HDF5_COMPRESSION_METHODS) > 0


def test_default_compression_is_always_available():
    assert "gzip" in AVAILABLE_HDF5_COMPRESSION_METHODS


def test_get_data_io_kwargs():
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration()

    assert hdf5_dataset_configuration.get_data_io_kwargs() == dict(
        chunks=(78125, 64), compression="gzip", compression_opts=None
    )


def test_hdf5_dataset_io_configuration_schema():
    assert HDF5DatasetIOConfiguration.schema() is not None
    assert HDF5DatasetIOConfiguration.schema_json() is not None
    assert HDF5DatasetIOConfiguration.model_json_schema() is not None
