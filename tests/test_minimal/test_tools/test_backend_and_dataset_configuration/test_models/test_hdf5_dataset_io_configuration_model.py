"""Unit tests for the HDF5DatasetIOConfiguration Pydantic model."""

import pytest

from neuroconv.tools.nwb_helpers import (
    AVAILABLE_HDF5_COMPRESSION_METHODS,
    HDF5DatasetIOConfiguration,
)
from neuroconv.tools.testing import mock_HDF5DatasetIOConfiguration


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


def test_get_data_io_kwargs_disables_compression_the_same_way_either_side_of_the_plugin_branch():
    """Whether `hdf5plugin` is installed is not something a configuration should be able to notice."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compression_method=None)

    assert hdf5_dataset_configuration.get_data_io_kwargs() == dict(chunks=(78125, 64), compression=False)


def test_compression_options_are_read_by_value_not_by_name():
    """A base HDF5 filter takes one value, and the key it arrives under varies by who wrote it."""
    from_a_caller = mock_HDF5DatasetIOConfiguration(compression_options=dict(level=9))
    from_a_file = mock_HDF5DatasetIOConfiguration(compression_options=dict(compression_opts=9))

    assert from_a_caller.get_data_io_kwargs()["compression_opts"] == 9
    assert from_a_file.get_data_io_kwargs()["compression_opts"] == 9


def test_more_than_one_compression_option_raises():
    """Silently dropping the second option is worse than saying it cannot be applied."""
    hdf5_dataset_configuration = mock_HDF5DatasetIOConfiguration(compression_options=dict(level=9, extra=1))

    with pytest.raises(ValueError, match="takes a single option"):
        hdf5_dataset_configuration.get_data_io_kwargs()
