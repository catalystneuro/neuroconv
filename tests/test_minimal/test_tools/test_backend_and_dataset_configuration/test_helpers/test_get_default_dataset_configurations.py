"""Unit tests for `get_default_dataset_configurations`."""
import numpy as np
import pytest
from hdmf.common import VectorData
from hdmf.data_utils import DataChunkIterator
from pynwb.base import DynamicTable
from pynwb.image import ImageSeries
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import (
    HDF5DatasetConfiguration,
    ZarrDatasetConfiguration,
    get_default_dataset_configurations,
)


@pytest.mark.parametrize("iterator", [lambda x: x, SliceableDataChunkIterator, DataChunkIterator])
def test_unwrapped_time_series_hdf5(iterator: callable):
    array = np.array([[1, 2, 3], [4, 5, 6]])
    data = iterator(array)

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=data)
    nwbfile.add_acquisition(time_series)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="hdf5"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, HDF5DatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == time_series.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestTimeSeries/data"
    assert dataset_configuration.dataset_info.full_shape == array.shape
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None


@pytest.mark.parametrize("iterator", [lambda x: x, SliceableDataChunkIterator, DataChunkIterator])
def test_unwrapped_time_series_zarr(iterator: callable):
    array = np.array([[1, 2, 3], [4, 5, 6]])
    data = iterator(array)

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=data)
    nwbfile.add_acquisition(time_series)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="zarr"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, ZarrDatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == time_series.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestTimeSeries/data"
    assert dataset_configuration.dataset_info.full_shape == array.shape
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None
    assert dataset_configuration.filter_methods is None
    assert dataset_configuration.filter_options is None


def test_external_image_series_hdf5():
    nwbfile = mock_NWBFile()
    image_series = ImageSeries(name="TestImageSeries", external_file=[""], rate=1.0)
    nwbfile.add_acquisition(image_series)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="hdf5"))

    assert len(dataset_configurations) == 0


def test_external_image_series_zarr():
    nwbfile = mock_NWBFile()
    image_series = ImageSeries(name="TestImageSeries", external_file=[""], rate=1.0)
    nwbfile.add_acquisition(image_series)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="zarr"))

    assert len(dataset_configurations) == 0


@pytest.mark.parametrize("iterator", [lambda x: x, SliceableDataChunkIterator, DataChunkIterator])
def test_unwrapped_dynamic_table_hdf5(iterator: callable):
    array = np.array([0.1, 0.2, 0.3])
    data = iterator(array.squeeze())

    nwbfile = mock_NWBFile()
    column = VectorData(name="TestColumn", description="", data=data)
    dynamic_table = DynamicTable(name="TestDynamicTable", description="", columns=[column])
    nwbfile.add_acquisition(dynamic_table)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="hdf5"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, HDF5DatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == column.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestDynamicTable/TestColumn/data"
    assert dataset_configuration.dataset_info.full_shape == array.shape
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None


@pytest.mark.parametrize("iterator", [lambda x: x, SliceableDataChunkIterator, DataChunkIterator])
def test_unwrapped_dynamic_table_zarr(iterator: callable):
    array = np.array([0.1, 0.2, 0.3])
    data = iterator(array.squeeze())

    nwbfile = mock_NWBFile()
    column = VectorData(name="TestColumn", description="", data=data)
    dynamic_table = DynamicTable(name="TestDynamicTable", description="", columns=[column])
    nwbfile.add_acquisition(dynamic_table)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="zarr"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, ZarrDatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == column.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestDynamicTable/TestColumn/data"
    assert dataset_configuration.dataset_info.full_shape == array.shape
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None
    assert dataset_configuration.filter_methods is None
    assert dataset_configuration.filter_options is None
