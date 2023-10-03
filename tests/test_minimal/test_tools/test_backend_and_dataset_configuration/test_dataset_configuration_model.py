"""Unit tests for the DatasetConfiguration Pydantic model."""
import pytest

from neuroconv.tools.nwb_helpers._models._base_dataset_models import (
    DatasetConfiguration,
)
from neuroconv.tools.testing import mock_DatasetInfo


def test_get_data_io_keyword_arguments_abstract_error():
    with pytest.raises(TypeError) as exc:
        dataset_configuration = DatasetConfiguration(
            dataset_info=mock_DatasetInfo(),
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 384),
        )
    assert (
        "Can't instantiate abstract class DatasetConfiguration with abstract methods get_data_io_keyword_arguments"
        == str(exc.info)
    )


def test_get_data_io_keyword_arguments_not_implemented():
    class TestDatasetConfiguration(DatasetConfiguration):
        def get_data_io_keyword_arguments(self):
            super().get_data_io_keyword_arguments()

    dataset_configuration = TestDatasetConfiguration(
        dataset_info=mock_DatasetInfo(),
        chunk_shape=(78_125, 64),
        buffer_shape=(1_250_000, 384),
    )

    with pytest.raises(NotImplementedError):
        dataset_configuration.get_data_io_keyword_arguments()
