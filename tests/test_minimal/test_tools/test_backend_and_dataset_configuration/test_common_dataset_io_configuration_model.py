"""Unit tests for the all common Pydantic validations shared across DatasetConfigurations children."""

import pytest

from neuroconv.tools.nwb_helpers import DatasetIOConfiguration
from neuroconv.tools.testing import (
    mock_HDF5DatasetIOConfiguration,
    mock_ZarrDatasetIOConfiguration,
)


@pytest.mark.parametrize(
    argnames="dataset_configuration_class", argvalues=[mock_HDF5DatasetIOConfiguration, mock_ZarrDatasetIOConfiguration]
)
def test_validator_chunk_length_consistency(dataset_configuration_class: DatasetIOConfiguration):
    with pytest.raises(ValueError) as error_info:
        dataset_configuration_class(chunk_shape=(78_125, 64, 1), buffer_shape=(1_250_000, 384))

    expected_error = (
        "len(chunk_shape)=3 does not match len(buffer_shape)=2 for dataset at location "
        "'acquisition/TestElectricalSeries/data'! [type=value_error, "
    )
    assert expected_error in str(error_info.value)


@pytest.mark.parametrize(
    argnames="dataset_configuration_class", argvalues=[mock_HDF5DatasetIOConfiguration, mock_ZarrDatasetIOConfiguration]
)
def test_validator_chunk_and_buffer_length_consistency(dataset_configuration_class: DatasetIOConfiguration):
    with pytest.raises(ValueError) as error_info:
        dataset_configuration_class(chunk_shape=(78_125, 64, 1), buffer_shape=(1_250_000, 384, 1))

    expected_error = (
        "len(buffer_shape)=3 does not match len(full_shape)=2 for dataset at location "
        "'acquisition/TestElectricalSeries/data'! [type=value_error, "
    )
    assert expected_error in str(error_info.value)


@pytest.mark.parametrize(
    argnames="dataset_configuration_class", argvalues=[mock_HDF5DatasetIOConfiguration, mock_ZarrDatasetIOConfiguration]
)
def test_validator_chunk_shape_nonpositive_elements(dataset_configuration_class: DatasetIOConfiguration):
    with pytest.raises(ValueError) as error_info:
        dataset_configuration_class(chunk_shape=(1, -2), buffer_shape=(1_250_000, 384))

    expected_error = (
        "Some dimensions of the chunk_shape=(1, -2) are less than or equal to zero for dataset at "
        "location 'acquisition/TestElectricalSeries/data'! [type=value_error, "
    )
    assert expected_error in str(error_info.value)


@pytest.mark.parametrize(
    argnames="dataset_configuration_class", argvalues=[mock_HDF5DatasetIOConfiguration, mock_ZarrDatasetIOConfiguration]
)
def test_validator_buffer_shape_nonpositive_elements(dataset_configuration_class: DatasetIOConfiguration):
    with pytest.raises(ValueError) as error_info:
        dataset_configuration_class(chunk_shape=(78_125, 64), buffer_shape=(78_125, -2))

    expected_error = (
        "Some dimensions of the buffer_shape=(78125, -2) are less than or equal to zero for dataset at "
        "location 'acquisition/TestElectricalSeries/data'! [type=value_error, "
    )
    assert expected_error in str(error_info.value)


@pytest.mark.parametrize(
    argnames="dataset_configuration_class", argvalues=[mock_HDF5DatasetIOConfiguration, mock_ZarrDatasetIOConfiguration]
)
def test_validator_chunk_shape_exceeds_buffer_shape(dataset_configuration_class: DatasetIOConfiguration):
    with pytest.raises(ValueError) as error_info:
        dataset_configuration_class(chunk_shape=(78_126, 64), buffer_shape=(78_125, 384))

    expected_error = (
        "Some dimensions of the chunk_shape=(78126, 64) exceed the buffer_shape=(78125, 384) for dataset at location "
        "'acquisition/TestElectricalSeries/data'! [type=value_error, "
    )
    assert expected_error in str(error_info.value)


@pytest.mark.parametrize(
    argnames="dataset_configuration_class", argvalues=[mock_HDF5DatasetIOConfiguration, mock_ZarrDatasetIOConfiguration]
)
def test_validator_buffer_shape_exceeds_full_shape(dataset_configuration_class: DatasetIOConfiguration):
    with pytest.raises(ValueError) as error_info:
        dataset_configuration_class(chunk_shape=(78_125, 64), buffer_shape=(1_250_000, 385))

    expected_error = (
        "Some dimensions of the buffer_shape=(1250000, 385) exceed the full_shape=(1800000, 384) for "
        "dataset at location 'acquisition/TestElectricalSeries/data'! [type=value_error, "
    )
    assert expected_error in str(error_info.value)


@pytest.mark.parametrize(
    argnames="dataset_configuration_class", argvalues=[mock_HDF5DatasetIOConfiguration, mock_ZarrDatasetIOConfiguration]
)
def test_validator_chunk_dimensions_do_not_evenly_divide_buffer(dataset_configuration_class: DatasetIOConfiguration):
    with pytest.raises(ValueError) as error_info:
        dataset_configuration_class(
            chunk_shape=(78_125, 7),
            buffer_shape=(1_250_000, 383),  # Different trigger condition when not the full shape for an axis
        )

    expected_error = (
        "Some dimensions of the chunk_shape=(78125, 7) do not evenly divide the buffer_shape=(1250000, 383) for "
        "dataset at location 'acquisition/TestElectricalSeries/data'! [type=value_error, "
    )
    assert expected_error in str(error_info.value)


@pytest.mark.parametrize(
    argnames="dataset_configuration_class", argvalues=[mock_HDF5DatasetIOConfiguration, mock_ZarrDatasetIOConfiguration]
)
def test_validator_chunk_dimensions_do_not_evenly_divide_buffer_skip_full_shape(
    dataset_configuration_class: DatasetIOConfiguration,
):
    """Any divisibility is allowed when the buffer shape is capped at the full length of an axis."""
    dataset_configuration_class(chunk_shape=(78_125, 7), buffer_shape=(1_250_000, 384))
