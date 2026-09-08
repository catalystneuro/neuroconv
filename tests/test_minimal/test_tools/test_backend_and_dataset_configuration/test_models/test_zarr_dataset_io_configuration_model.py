"""Unit tests for the ZarrDatasetIOConfiguration Pydantic model."""

import numpy as np
import pytest
from numcodecs import Delta, GZip, Shuffle
from pydantic import ValidationError

from neuroconv.tools.nwb_helpers import (
    AVAILABLE_ZARR_COMPRESSION_METHODS,
    ZarrDatasetIOConfiguration,
)
from neuroconv.tools.testing import mock_ZarrDatasetIOConfiguration


def test_validator_filter_options_has_methods():
    with pytest.raises(ValueError) as error_info:
        mock_ZarrDatasetIOConfiguration(
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 384),
            filters=None,
            filter_options=[dict(clevel=5)],
        )

    expected_error = (
        "`filters` is `None` but `filter_options` is not `None` "
        "(received `filter_options=[{'clevel': 5}]`)! [type=value_error, "
    )
    assert expected_error in str(error_info.value)


def test_validator_filters_length_match_options():
    with pytest.raises(ValueError) as error_info:
        mock_ZarrDatasetIOConfiguration(
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 384),
            filters=["blosc", "delta"],
            filter_options=[dict(clevel=5)],  # Correction would be to add a second element `dict()` to avoid ambiguity
        )

    expected_error = (
        "Length mismatch between `filters` (2 specified) and `filter_options` (1 options found)! "
        "`filters` and `filter_options` should be the same length. [type=value_error, "
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


def test_get_data_io_kwargs_with_shuffle():
    """Zarr v2 has a single compressor slot, so every entry of `compressors` but the last rides in `filters`."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(compressors=["shuffle", "gzip"])

    assert zarr_dataset_configuration.get_data_io_kwargs() == dict(
        chunks=(78125, 64), compressor=GZip(level=1), filters=[Shuffle(elementsize=2)]
    )


def test_get_data_io_kwargs_with_shuffle_and_a_filter_method():
    """An array-to-array filter method stays ahead of the entries moved out of `compressors`."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(
        compressors=["shuffle", "gzip"], filters=["delta"], filter_options=[dict(dtype="int16")]
    )

    assert zarr_dataset_configuration.get_data_io_kwargs() == dict(
        chunks=(78125, 64), compressor=GZip(level=1), filters=[Delta(dtype="int16"), Shuffle(elementsize=2)]
    )


def test_compressor_options_length_mismatch_raises():
    with pytest.raises(ValidationError, match="Length mismatch between `compressors`"):
        mock_ZarrDatasetIOConfiguration(compressors=["shuffle", "gzip"], compressor_options=[None])


def test_deprecated_compression_method_property():
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(compressors=["shuffle", "gzip"])

    with pytest.warns(FutureWarning, match="removed in v0.12.0"):
        assert zarr_dataset_configuration.compression_method == "gzip"

    with pytest.warns(FutureWarning, match="removed in v0.12.0"):
        zarr_dataset_configuration.compression_method = "zstd"

    assert zarr_dataset_configuration.compressors == ["shuffle", "zstd"]


def test_shuffle_elementsize_follows_the_dtype():
    """`numcodecs.Shuffle` defaults `elementsize` to 4, which is wrong for anything else."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(
        compressors=["shuffle", "gzip"], dtype=np.dtype("float64")
    )

    assert zarr_dataset_configuration.get_data_io_kwargs()["filters"] == [Shuffle(elementsize=8)]


def test_shuffle_elementsize_follows_the_dtype_on_the_deprecated_path():
    """The deprecated `filters` spelling instantiates through the same helper."""
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(filters=["shuffle"], dtype=np.dtype("float64"))

    assert zarr_dataset_configuration.get_data_io_kwargs()["filters"] == [Shuffle(elementsize=8)]


def test_shuffle_elementsize_is_not_overridden_when_stated():
    zarr_dataset_configuration = mock_ZarrDatasetIOConfiguration(
        compressors=["shuffle", "gzip"], compressor_options=[dict(elementsize=2), None], dtype=np.dtype("float64")
    )

    assert zarr_dataset_configuration.get_data_io_kwargs()["filters"] == [Shuffle(elementsize=2)]
