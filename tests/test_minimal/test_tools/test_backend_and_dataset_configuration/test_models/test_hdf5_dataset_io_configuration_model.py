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
    """Test the printout display of a HDF5DatasetIOConfiguration model looks nice."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compression_options=dict(level=5))

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
  compression options : {'level': 5}

"""
    assert out.getvalue() == expected_print


def test_hdf5_dataset_configuration_print_with_compression_disabled():
    """Test the printout display of a HDF5DatasetIOConfiguration model looks nice."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compression_method=None)

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

"""
    assert out.getvalue() == expected_print


def test_hdf5_dataset_configuration_repr():
    """Test the programmatic repr of a HDF5DatasetIOConfiguration model is more dataclass-like."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration()

    # Important to keep the `repr` unmodified for appearance inside iterables of DatasetInfo objects
    expected_repr = (
        "HDF5DatasetIOConfiguration(object_id='481a0860-3a0c-40ec-b931-df4a3e9b101f', "
        "location_in_file='acquisition/TestElectricalSeries/data', dataset_name='data', dtype=dtype('int16'), "
        "full_shape=(1800000, 384), chunk_shape=(78125, 64), buffer_shape=(1250000, 384), compression_method='gzip', "
        "compression_options=None)"
    )
    assert repr(hdf5_dataset_configuration) == expected_repr


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
