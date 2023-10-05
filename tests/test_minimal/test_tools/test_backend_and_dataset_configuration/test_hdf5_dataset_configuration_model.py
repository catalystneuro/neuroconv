"""Unit tests for the DatasetInfo Pydantic model."""
from io import StringIO
from unittest.mock import patch

import pytest

from neuroconv.tools.nwb_helpers import (
    AVAILABLE_HDF5_COMPRESSION_METHODS,
    HDF5DatasetConfiguration,
)
from neuroconv.tools.testing import mock_DatasetInfo, mock_HDF5DatasetConfiguration


def test_hdf5_dataset_configuration_print():
    """Test the printout display of a HDF5DatasetConfiguration model looks nice."""
    hdf5_dataset_configuration = mock_HDF5DatasetConfiguration()

    with patch("sys.stdout", new=StringIO()) as out:
        print(hdf5_dataset_configuration)

    expected_print = """
acquisition/TestElectricalSeries/data
-------------------------------------
  dtype : int16
  full shape of source array : (1800000, 384)
  full size of source array : 1.38 GB

  buffer shape : (1250000, 384)
  maximum RAM usage per iteration : 0.96 GB

  chunk shape : (78125, 64)
  disk space usage per chunk : 10.00 MB

  compression method : gzip

"""
    assert out.getvalue() == expected_print


def test_hdf5_dataset_configuration_print_with_compression_options():
    """Test the printout display of a HDF5DatasetConfiguration model looks nice."""
    hdf5_dataset_configuration = mock_HDF5DatasetConfiguration(compression_options=dict(level=5))

    with patch("sys.stdout", new=StringIO()) as out:
        print(hdf5_dataset_configuration)

    expected_print = """
acquisition/TestElectricalSeries/data
-------------------------------------
  dtype : int16
  full shape of source array : (1800000, 384)
  full size of source array : 1.38 GB

  buffer shape : (1250000, 384)
  maximum RAM usage per iteration : 0.96 GB

  chunk shape : (78125, 64)
  disk space usage per chunk : 10.00 MB

  compression method : gzip
  compression options : {'level': 5}

"""
    assert out.getvalue() == expected_print


def test_hdf5_dataset_configuration_print_with_compression_disabled():
    """Test the printout display of a HDF5DatasetConfiguration model looks nice."""
    hdf5_dataset_configuration = mock_HDF5DatasetConfiguration(compression_method=None)

    with patch("sys.stdout", new=StringIO()) as out:
        print(hdf5_dataset_configuration)

    expected_print = """
acquisition/TestElectricalSeries/data
-------------------------------------
  dtype : int16
  full shape of source array : (1800000, 384)
  full size of source array : 1.38 GB

  buffer shape : (1250000, 384)
  maximum RAM usage per iteration : 0.96 GB

  chunk shape : (78125, 64)
  disk space usage per chunk : 10.00 MB

"""
    assert out.getvalue() == expected_print


def test_hdf5_dataset_configuration_repr():
    """Test the programmatic repr of a HDF5DatasetConfiguration model is more dataclass-like."""
    hdf5_dataset_configuration = mock_HDF5DatasetConfiguration()

    # Important to keep the `repr` unmodified for appearance inside iterables of DatasetInfo objects
    expected_repr = (
        "HDF5DatasetConfiguration(dataset_info=DatasetInfo(object_id='481a0860-3a0c-40ec-b931-df4a3e9b101f', "
        "location='acquisition/TestElectricalSeries/data', dataset_name='data', full_shape=(1800000, 384), "
        "dtype=dtype('int16')), chunk_shape=(78125, 64), buffer_shape=(1250000, 384), compression_method='gzip', "
        "compression_options=None)"
    )
    assert repr(hdf5_dataset_configuration) == expected_repr


def test_validator_chunk_length_consistency():
    with pytest.raises(ValueError) as error_info:
        HDF5DatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 64, 1),
            buffer_shape=(1_250_000, 384),
        )

    expected_error = (
        "len(chunk_shape)=3 does not match len(buffer_shape)=2 for dataset at location "
        "'acquisition/TestElectricalSeries/data'! (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_validator_chunk_and_buffer_length_consistency():
    with pytest.raises(ValueError) as error_info:
        HDF5DatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 64, 1),
            buffer_shape=(1_250_000, 384, 1),
        )

    expected_error = (
        "len(buffer_shape)=3 does not match len(full_shape)=2 for dataset at location "
        "'acquisition/TestElectricalSeries/data'! (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_validator_chunk_shape_nonpositive_elements():
    with pytest.raises(ValueError) as error_info:
        HDF5DatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(1, -2),
            buffer_shape=(1_250_000, 384),
        )

    expected_error = (
        "Some dimensions of the chunk_shape=(1, -2) are less than or equal to zero for dataset at "
        "location 'acquisition/TestElectricalSeries/data'! (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_validator_buffer_shape_nonpositive_elements():
    with pytest.raises(ValueError) as error_info:
        HDF5DatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 64),
            buffer_shape=(78_125, -2),
        )

    expected_error = (
        "Some dimensions of the buffer_shape=(78125, -2) are less than or equal to zero for dataset at "
        "location 'acquisition/TestElectricalSeries/data'! (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_validator_chunk_shape_exceeds_buffer_shape():
    with pytest.raises(ValueError) as error_info:
        HDF5DatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_126, 64),
            buffer_shape=(78_125, 384),
        )

    expected_error = (
        "Some dimensions of the chunk_shape=(78126, 64) exceed the buffer_shape=(78125, 384) for dataset at location "
        "'acquisition/TestElectricalSeries/data'! (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_validator_buffer_shape_exceeds_full_shape():
    with pytest.raises(ValueError) as error_info:
        HDF5DatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 385),
        )

    expected_error = (
        "Some dimensions of the buffer_shape=(1250000, 385) exceed the full_shape=(1800000, 384) for "
        "dataset at location 'acquisition/TestElectricalSeries/data'! (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_validator_chunk_dimensions_do_not_evenly_divide_buffer():
    with pytest.raises(ValueError) as error_info:
        HDF5DatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 7),
            buffer_shape=(1_250_000, 384),
        )

    expected_error = (
        "Some dimensions of the chunk_shape=(78125, 7) do not evenly divide the buffer_shape=(1250000, 384) for "
        "dataset at location 'acquisition/TestElectricalSeries/data'! (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_available_hdf5_compression_methods_not_empty():
    assert len(AVAILABLE_HDF5_COMPRESSION_METHODS) > 0


def test_default_compression_is_always_available():
    assert "gzip" in AVAILABLE_HDF5_COMPRESSION_METHODS


def test_mutation_validation():
    """
    Only testing on one dummy case to verify the root validator is triggered.

    Trust the rest should follow.
    """
    hdf5_dataset_configuration = mock_HDF5DatasetConfiguration()

    with pytest.raises(ValueError) as error_info:
        hdf5_dataset_configuration.chunk_shape = (1, -2)

    expected_error = (
        "Some dimensions of the chunk_shape=(1, -2) are less than or equal to zero for dataset at "
        "location 'acquisition/TestElectricalSeries/data'! (type=value_error)"
    )
    assert expected_error in str(error_info.value)


def test_get_data_io_keyword_arguments():
    hdf5_dataset_configuration = mock_HDF5DatasetConfiguration()

    assert hdf5_dataset_configuration.get_data_io_keyword_arguments() == dict(
        chunks=(78125, 64), compression="gzip", compression_opts=None
    )
