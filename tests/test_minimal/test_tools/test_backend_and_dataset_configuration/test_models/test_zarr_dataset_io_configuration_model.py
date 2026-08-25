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
    """The compression options line renders only when options are set."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(compression_options=dict(level=5))

    printout = str(zarr_dataset_configuration)

    assert "  compression method : gzip" in printout
    assert "  compression options : {'level': 5}" in printout


def test_zarr_dataset_configuration_print_with_compression_disabled():
    """Neither compression line renders when compression is disabled."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(compression_method=None)

    printout = str(zarr_dataset_configuration)

    assert "compression method" not in printout
    assert "compression options" not in printout


def test_zarr_dataset_configuration_print_with_filter_methods():
    """The filter methods line renders only when filters are set."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(filter_methods=["delta", "blosc"])

    printout = str(zarr_dataset_configuration)

    assert "  filter methods : ['delta', 'blosc']" in printout
    assert "filter options" not in printout


def test_zarr_dataset_configuration_print_with_filter_options():
    """The filter options line renders alongside the filter methods line."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(
        filter_methods=["blosc"], filter_options=[dict(clevel=6)]
    )

    printout = str(zarr_dataset_configuration)

    assert "  filter methods : ['blosc']" in printout
    assert "  filter options : [{'clevel': 6}]" in printout


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
