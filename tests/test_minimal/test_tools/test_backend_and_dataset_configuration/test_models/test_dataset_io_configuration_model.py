"""Unit tests for the DatasetConfiguration Pydantic model."""

import pytest

from neuroconv.tools.nwb_helpers import DatasetIOConfiguration
from neuroconv.tools.testing import mock_DatasetInfo


def test_get_data_io_kwargs_abstract_error():
    with pytest.raises(TypeError) as error_info:
        DatasetIOConfiguration(dataset_info=mock_DatasetInfo(), chunk_shape=(78_125, 64), buffer_shape=(1_250_000, 384))
    assert "Can't instantiate abstract class DatasetIOConfiguration" in str(error_info.value)


def test_get_data_io_kwargs_not_implemented():
    class TestDatasetIOConfiguration(DatasetIOConfiguration):
        def get_data_io_kwargs(self):
            super().get_data_io_kwargs()

    dataset_io_configuration = TestDatasetIOConfiguration(
        dataset_info=mock_DatasetInfo(),
        chunk_shape=(78_125, 64),
        buffer_shape=(1_250_000, 384),
    )

    with pytest.raises(NotImplementedError):
        dataset_io_configuration.get_data_io_kwargs()
