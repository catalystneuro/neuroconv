"""Unit tests for the DatasetConfiguration Pydantic model."""

import numpy as np
import pytest

from neuroconv.tools.nwb_helpers import DatasetIOConfiguration


def test_get_data_io_kwargs_abstract_error():
    with pytest.raises(TypeError) as error_info:
        DatasetIOConfiguration(
            object_id="481a0860-3a0c-40ec-b931-df4a3e9b101f",
            location_in_file="acquisition/TestElectricalSeries/data",
            dataset_name="data",
            full_shape=(60 * 30_000, 384),  # ~1 minute of v1 NeuroPixels probe
            dtype=np.dtype("int16"),
            chunk_shape=(78_125, 64),
            buffer_shape=(1_250_000, 384),
            compression_method="gzip",
        )
    assert "Can't instantiate abstract class DatasetIOConfiguration" in str(error_info.value)


def test_get_data_io_kwargs_not_implemented():
    class TestDatasetIOConfiguration(DatasetIOConfiguration):
        def get_data_io_kwargs(self):
            super().get_data_io_kwargs()

    dataset_io_configuration = TestDatasetIOConfiguration(
        object_id="481a0860-3a0c-40ec-b931-df4a3e9b101f",
        location_in_file="acquisition/TestElectricalSeries/data",
        dataset_name="data",
        full_shape=(60 * 30_000, 384),  # ~1 minute of v1 NeuroPixels probe
        dtype=np.dtype("int16"),
        chunk_shape=(78_125, 64),
        buffer_shape=(1_250_000, 384),
        compression_method="gzip",
    )

    with pytest.raises(NotImplementedError):
        dataset_io_configuration.get_data_io_kwargs()


def test_model_json_schema_mode_assertion():
    with pytest.raises(AssertionError) as error_info:
        DatasetIOConfiguration.model_json_schema(mode="anything")

    assert "The 'mode' of this method is fixed to be 'validation' and cannot be changed." == str(error_info.value)


def test_model_json_schema_generator_assertion():
    with pytest.raises(AssertionError) as error_info:
        DatasetIOConfiguration.model_json_schema(schema_generator="anything")

    assert "The 'schema_generator' of this method cannot be changed." == str(error_info.value)
