"""Unit tests for the DatasetConfiguration Pydantic model."""
import pytest

from neuroconv.tools.nwb_helpers._models._base_models import DatasetConfiguration
from neuroconv.tools.testing import mock_DatasetInfo


def test_get_data_io_kwargs_abstract_error():
    with pytest.raises(TypeError) as error_info:
        DatasetConfiguration(dataset_info=mock_DatasetInfo(), chunk_shape=(78_125, 64), buffer_shape=(1_250_000, 384))
    assert "Can't instantiate abstract class DatasetConfiguration with abstract" in str(error_info.value)


def test_get_data_io_kwargs_not_implemented():
    class TestDatasetConfiguration(DatasetConfiguration):
        def get_data_io_kwargs(self):
            super().get_data_io_kwargs()

    dataset_configuration = TestDatasetConfiguration(
        dataset_info=mock_DatasetInfo(),
        chunk_shape=(78_125, 64),
        buffer_shape=(1_250_000, 384),
    )

    with pytest.raises(NotImplementedError):
        dataset_configuration.get_data_io_kwargs()
