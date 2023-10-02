"""Unit tests for the DatasetInfo Pydantic model."""
from io import StringIO
from unittest.mock import patch

import pytest

from neuroconv.tools.nwb_helpers import (
    AVAILABLE_ZARR_COMPRESSION_METHODS,
    ZarrDatasetConfiguration,
)
from neuroconv.tools.testing import mock_DatasetInfo, mock_ZarrDatasetConfiguration


def test_zarr_dataset_configuration_print():
    """Test the printout display of a ZarrDatasetConfiguration model looks nice."""
    zarr_dataset_configuration = mock_ZarrDatasetConfiguration()

    with patch("sys.stdout", new=StringIO()) as out:
        print(zarr_dataset_configuration)

    expected_print = """
acquisition/TestElectricalSeries/data
-------------------------------------
  maxshape: (1800000, 384)
  dtype: int16

  chunk_shape: (78125, 64)
  buffer_shape: (1250000, 384)
  compression_method: gzip
"""
    assert out.getvalue() == expected_print


def test_zarr_dataset_configuration_print_with_compression_options():
    """Test the printout display of a ZarrDatasetConfiguration model looks nice."""
    zarr_dataset_configuration = mock_ZarrDatasetConfiguration(compression_options=dict(level=5))

    with patch("sys.stdout", new=StringIO()) as out:
        print(zarr_dataset_configuration)

    expected_print = """
acquisition/TestElectricalSeries/data
-------------------------------------
  maxshape: (1800000, 384)
  dtype: int16

  chunk_shape: (78125, 64)
  buffer_shape: (1250000, 384)
  compression_method: gzip
  compression_options: {'level': 5}
"""
    assert out.getvalue() == expected_print


def test_zarr_dataset_configuration_print_with_compression_disabled():
    """Test the printout display of a ZarrDatasetConfiguration model looks nice."""
    zarr_dataset_configuration = mock_ZarrDatasetConfiguration(compression_method=None)

    with patch("sys.stdout", new=StringIO()) as out:
        print(zarr_dataset_configuration)

    expected_print = """
acquisition/TestElectricalSeries/data
-------------------------------------
  maxshape: (1800000, 384)
  dtype: int16

  chunk_shape: (78125, 64)
  buffer_shape: (1250000, 384)
  compression_method: None
"""
    assert out.getvalue() == expected_print


def test_zarr_dataset_configuration_print_with_filter_methods():
    """Test the printout display of a ZarrDatasetConfiguration model looks nice."""
    zarr_dataset_configuration = mock_ZarrDatasetConfiguration(filter_methods=["delta"])

    with patch("sys.stdout", new=StringIO()) as out:
        print(zarr_dataset_configuration)

    expected_print = """
acquisition/TestElectricalSeries/data
-------------------------------------
  maxshape: (1800000, 384)
  dtype: int16

  chunk_shape: (78125, 64)
  buffer_shape: (1250000, 384)
  compression_method: gzip
  filter_methods: ['delta']
"""
    assert out.getvalue() == expected_print


def test_zarr_dataset_configuration_print_with_filter_options():
    """Test the printout display of a ZarrDatasetConfiguration model looks nice."""
    zarr_dataset_configuration = mock_ZarrDatasetConfiguration(
        filter_methods=["blosc"], filter_options=[dict(clevel=5)]
    )

    with patch("sys.stdout", new=StringIO()) as out:
        print(zarr_dataset_configuration)

    expected_print = """
acquisition/TestElectricalSeries/data
-------------------------------------
  maxshape: (1800000, 384)
  dtype: int16

  chunk_shape: (78125, 64)
  buffer_shape: (1250000, 384)
  compression_method: gzip
  filter_methods: ['blosc']
  filter_options: [{'clevel': 5}]
"""
    assert out.getvalue() == expected_print


def test_zarr_dataset_configuration_repr():
    """Test the programmatic repr of a ZarrDatasetConfiguration model is more dataclass-like."""
    zarr_dataset_configuration = mock_ZarrDatasetConfiguration()

    # Important to keep the `repr` unmodified for appearance inside iterables of DatasetInfo objects
    expected_repr = (
        "ZarrDatasetConfiguration(dataset_info=DatasetInfo(object_id='481a0860-3a0c-40ec-b931-df4a3e9b101f', "
        "location='acquisition/TestElectricalSeries/data', full_shape=(1800000, 384), dtype=dtype('int16')), "
        "chunk_shape=(78125, 64), buffer_shape=(1250000, 384), compression_method='gzip', compression_options=None, "
        "filter_methods=None, filter_options=None)"
    )
    assert repr(zarr_dataset_configuration) == expected_repr


def test_validator_chunk_length_consistency():
    with pytest.raises(ValueError) as error_info:
        ZarrDatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 64, 1),
            buffer_shape=(1_250_000, 384),
        )

    expected_error = "len(chunk_shape)=3 does not match len(buffer_shape)=2! (type=value_error)"
    assert expected_error in str(error_info.value)


def test_validator_chunk_and_buffer_length_consistency():
    with pytest.raises(ValueError) as error_info:
        ZarrDatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 64, 1),
            buffer_shape=(1_250_000, 384, 1),
        )

    expected_error = "len(buffer_shape)=3 does not match len(full_shape)=2! (type=value_error)"
    assert expected_error in str(error_info.value)


def test_validator_chunk_shape_nonpositive_elements():
    with pytest.raises(ValueError) as error_info:
        ZarrDatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(1, -2),
            buffer_shape=(1_250_000, 384),
        )

    expected_error = "Some dimensions of the chunk_shape=(1, -2) are less than or equal to zero! (type=value_error)"
    assert expected_error in str(error_info.value)


def test_validator_buffer_shape_nonpositive_elements():
    with pytest.raises(ValueError) as error_info:
        ZarrDatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 64),
            buffer_shape=(78_125, -2),
        )

    expected_error = (
        "Some dimensions of the buffer_shape=(78125, -2) are less than or equal to zero! (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_validator_chunk_shape_exceeds_buffer_shape():
    with pytest.raises(ValueError) as error_info:
        ZarrDatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_126, 64),
            buffer_shape=(78_125, 384),
        )

    expected_error = (
        "Some dimensions of the chunk_shape=(78126, 64) exceed the buffer_shape=(78125, 384))! (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_validator_buffer_shape_exceeds_full_shape():
    with pytest.raises(ValueError) as error_info:
        ZarrDatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 385),
        )

    expected_error = (
        "Some dimensions of the buffer_shape=(1250000, 385) exceed the full_shape=(1800000, 384)! (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_validator_chunk_dimensions_do_not_evenly_divide_buffer():
    with pytest.raises(ValueError) as error_info:
        ZarrDatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 7),
            buffer_shape=(1_250_000, 384),
        )

    expected_error = (
        "Some dimensions of the chunk_shape=(78125, 7) do not evenly divide the buffer_shape=(1250000, 384))! "
        "(type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_validator_filter_options_has_methods():
    with pytest.raises(ValueError) as error_info:
        ZarrDatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 384),
            filter_methods=None,
            filter_options=[dict(clevel=5)],
        )

    expected_error = (
        "`filter_methods` is `None` but `filter_options` is not (received [{'clevel': 5}])! (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_validator_filter_methods_length_match_options():
    with pytest.raises(ValueError) as error_info:
        ZarrDatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 384),
            filter_methods=["blosc", "delta"],
            filter_options=[dict(clevel=5)],  # Correction would be to add a second element `dict()` to avoid ambiguity
        )

    expected_error = (
        "Length mismatch between `filter_methods` (2 methods specified) and `filter_options` (1 options found)! "
        "`filter_methods` and `filter_options` should be the same length. (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_available_hdf5_compression_methods_not_empty():
    assert len(AVAILABLE_ZARR_COMPRESSION_METHODS) > 0


def test_default_compression_is_always_available():
    assert "gzip" in AVAILABLE_ZARR_COMPRESSION_METHODS


def test_mutation_validation():
    """
    Only testing on one dummy case to verify the root validator is triggered.

    Trust the rest should follow.
    """
    zarr_dataset_configuration = mock_ZarrDatasetConfiguration()

    with pytest.raises(ValueError) as error_info:
        zarr_dataset_configuration.chunk_shape = (1, -2)

    expected_error = "Some dimensions of the chunk_shape=(1, -2) are less than or equal to zero! (type=value_error)"
    assert expected_error in str(error_info.value)
