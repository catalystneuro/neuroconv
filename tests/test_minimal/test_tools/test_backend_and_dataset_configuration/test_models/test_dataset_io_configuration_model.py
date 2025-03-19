"""Unit tests for the DatasetConfiguration Pydantic model."""

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

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


# TODO: Add support for compound objects with non-string elements
# def test_from_neurodata_object_dtype_object():
#     class TestDatasetIOConfiguration(DatasetIOConfiguration):
#         def get_data_io_kwargs(self):
#             super().get_data_io_kwargs()

#     nwbfile = mock_NWBFile()
#     nwbfile.add_trial(start_time=0.0, stop_time=1.0)
#     nwbfile.add_trial(start_time=1.0, stop_time=2.0)
#     nwbfile.add_trial(start_time=2.0, stop_time=3.0)
#     data = np.array(["test", 5, False], dtype=object)
#     nwbfile.add_trial_column(name="test", description="test column with object dtype", data=data)
#     neurodata_object = nwbfile.trials.columns[2]

#     dataset_io_configuration = TestDatasetIOConfiguration.from_neurodata_object(neurodata_object, dataset_name="data")

#     assert dataset_io_configuration.chunk_shape == (3,)
#     assert dataset_io_configuration.buffer_shape == (3,)
#     assert dataset_io_configuration.compression_method is None


def test_from_neurodata_object_dtype_object_all_strings():
    class TestDatasetIOConfiguration(DatasetIOConfiguration):
        def get_data_io_kwargs(self):
            super().get_data_io_kwargs()

    nwbfile = mock_NWBFile()
    nwbfile.add_trial(start_time=0.0, stop_time=1.0)
    nwbfile.add_trial(start_time=1.0, stop_time=2.0)
    nwbfile.add_trial(start_time=2.0, stop_time=3.0)
    data = np.array(["test", "string", "abc"], dtype=object)
    nwbfile.add_trial_column(name="test", description="test column with object dtype but all strings", data=data)
    neurodata_object = nwbfile.trials.columns[2]

    dataset_io_configuration = TestDatasetIOConfiguration.from_neurodata_object(neurodata_object, dataset_name="data")

    assert dataset_io_configuration.chunk_shape == (3,)
    assert dataset_io_configuration.buffer_shape == (3,)
    assert dataset_io_configuration.compression_method == "gzip"
