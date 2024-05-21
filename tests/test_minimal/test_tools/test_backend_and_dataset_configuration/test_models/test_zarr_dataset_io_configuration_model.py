"""Unit tests for the ZarrDatasetIOConfiguration Pydantic model."""

from io import StringIO
from unittest.mock import patch

import pytest
from numcodecs import GZip

from neuroconv.tools.nwb_helpers import (
    AVAILABLE_ZARR_COMPRESSION_METHODS,
    ZarrDatasetIOConfiguration,
)
from neuroconv.tools.testing import mock_ZarrDatasetIOConfiguration


def test_zarr_dataset_io_configuration_print():
    """Test the printout display of a ZarrDatasetIOConfiguration model looks nice."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration()

    with patch("sys.stdout", new=StringIO()) as out:
        print(zarr_dataset_configuration)

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


def test_zarr_dataset_configuration_print_with_compression_options():
    """Test the printout display of a ZarrDatasetIOConfiguration model looks nice."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(compression_options=dict(level=5))

    with patch("sys.stdout", new=StringIO()) as out:
        print(zarr_dataset_configuration)

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


def test_zarr_dataset_configuration_print_with_compression_disabled():
    """Test the printout display of a ZarrDatasetIOConfiguration model looks nice."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(compression_method=None)

    with patch("sys.stdout", new=StringIO()) as out:
        print(zarr_dataset_configuration)

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


def test_zarr_dataset_configuration_print_with_filter_methods():
    """Test the printout display of a ZarrDatasetIOConfiguration model looks nice."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(filter_methods=["delta"])

    with patch("sys.stdout", new=StringIO()) as out:
        print(zarr_dataset_configuration)

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

  filter methods : ['delta']

"""
    assert out.getvalue() == expected_print


def test_zarr_dataset_configuration_print_with_filter_options():
    """Test the printout display of a ZarrDatasetIOConfiguration model looks nice."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(
        filter_methods=["blosc"], filter_options=[dict(clevel=5)]
    )

    with patch("sys.stdout", new=StringIO()) as out:
        print(zarr_dataset_configuration)

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

  filter methods : ['blosc']
  filter options : [{'clevel': 5}]

"""
    assert out.getvalue() == expected_print


def test_zarr_dataset_configuration_repr():
    """Test the programmatic repr of a ZarrDatasetIOConfiguration model is more dataclass-like."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration()

    # Important to keep the `repr` unmodified for appearance inside iterables of DatasetInfo objects
    expected_repr = (
        "ZarrDatasetIOConfiguration(object_id='481a0860-3a0c-40ec-b931-df4a3e9b101f', "
        "location_in_file='acquisition/TestElectricalSeries/data', dataset_name='data', dtype=dtype('int16'), "
        "full_shape=(1800000, 384), chunk_shape=(78125, 64), buffer_shape=(1250000, 384), compression_method='gzip', "
        "compression_options=None, filter_methods=None, filter_options=None)"
    )
    assert repr(zarr_dataset_configuration) == expected_repr


def test_validator_filter_options_has_methods():
    with pytest.raises(ValueError) as error_info:
        mock_ZarrDatasetIOConfiguration(
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 384),
            filter_methods=None,
            filter_options=[dict(clevel=5)],
        )

    expected_error = (
        "`filter_methods` is `None` but `filter_options` is not `None` "
        "(received `filter_options=[{'clevel': 5}]`)! [type=value_error, "
    )
    assert expected_error in str(error_info.value)


def test_validator_filter_methods_length_match_options():
    with pytest.raises(ValueError) as error_info:
        mock_ZarrDatasetIOConfiguration(
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 384),
            filter_methods=["blosc", "delta"],
            filter_options=[dict(clevel=5)],  # Correction would be to add a second element `dict()` to avoid ambiguity
        )

    expected_error = (
        "Length mismatch between `filter_methods` (2 methods specified) and `filter_options` (1 options found)! "
        "`filter_methods` and `filter_options` should be the same length. [type=value_error, "
    )
    assert expected_error in str(error_info.value)


def test_available_zarr_compression_methods_not_empty():
    assert len(AVAILABLE_ZARR_COMPRESSION_METHODS) > 0


def test_default_compression_is_always_available():
    assert "gzip" in AVAILABLE_ZARR_COMPRESSION_METHODS


def test_get_data_io_kwargs():
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration()

    assert zarr_dataset_configuration.get_data_io_kwargs() == dict(
        chunks=(78125, 64), compressor=GZip(level=1), filters=None
    )


def test_zarr_dataset_io_configuration_schema():
    assert ZarrDatasetIOConfiguration.schema() is not None
    assert ZarrDatasetIOConfiguration.schema_json() is not None
    assert ZarrDatasetIOConfiguration.model_json_schema() is not None
