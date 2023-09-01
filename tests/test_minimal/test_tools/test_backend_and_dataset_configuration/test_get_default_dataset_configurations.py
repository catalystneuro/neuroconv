"""Unit tests for `get_default_dataset_configurations`."""
import numpy as np
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


def test_unwrapped_time_series_hdf5():
    array = np.array([[1, 2, 3], [4, 5, 6]])

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=array)
    nwbfile.add_acquisition(time_series)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="hdf5"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, HDF5DatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == time_series.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestTimeSeries/data"
    assert dataset_configuration.dataset_info.maxshape == array.shape
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None


def test_unwrapped_time_series_zarr():
    array = np.array([[1, 2, 3], [4, 5, 6]])

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=array)
    nwbfile.add_acquisition(time_series)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="zarr"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, ZarrDatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == time_series.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestTimeSeries/data"
    assert dataset_configuration.dataset_info.maxshape == array.shape
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None
    assert dataset_configuration.filter_methods is None
    assert dataset_configuration.filter_options is None


def test_generic_iterator_wrapped_time_series_hdf5():
    array = np.array([[1, 2, 3], [4, 5, 6]])

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=SliceableDataChunkIterator(data=array))
    nwbfile.add_acquisition(time_series)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="hdf5"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, HDF5DatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == time_series.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestTimeSeries/data"
    assert dataset_configuration.dataset_info.maxshape == array.shape
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None


def test_classic_iterator_wrapped_simple_time_series_zarr():
    array = np.array([[1, 2, 3], [4, 5, 6]])

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=DataChunkIterator(data=array))
    nwbfile.add_acquisition(time_series)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="zarr"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, ZarrDatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == time_series.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestTimeSeries/data"
    assert dataset_configuration.dataset_info.maxshape == array.shape
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None
    assert dataset_configuration.filter_methods is None
    assert dataset_configuration.filter_options is None


def test_classic_iterator_wrapped_time_series_hdf5():
    array = np.array([[1, 2, 3], [4, 5, 6]])

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=DataChunkIterator(data=array))
    nwbfile.add_acquisition(time_series)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="hdf5"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, HDF5DatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == time_series.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestTimeSeries/data"
    assert dataset_configuration.dataset_info.maxshape == array.shape
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None


def test_generic_iterator_wrapped_simple_time_series_zarr():
    array = np.array([[1, 2, 3], [4, 5, 6]])

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=SliceableDataChunkIterator(data=array))
    nwbfile.add_acquisition(time_series)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="zarr"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, ZarrDatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == time_series.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestTimeSeries/data"
    assert dataset_configuration.dataset_info.maxshape == array.shape
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


def test_unwrapped_dynamic_table_hdf5():
    array = np.array([0.1, 0.2, 0.3])

    nwbfile = mock_NWBFile()
    column = VectorData(name="TestColumn", description="", data=array.squeeze())
    dynamic_table = DynamicTable(name="TestDynamicTable", description="", columns=[column])
    nwbfile.add_acquisition(dynamic_table)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="hdf5"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, HDF5DatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == column.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestDynamicTable/TestColumn/data"
    assert dataset_configuration.dataset_info.maxshape == array.shape
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None


def test_unwrapped_dynamic_table_zarr():
    array = np.array([0.1, 0.2, 0.3])

    nwbfile = mock_NWBFile()
    column = VectorData(name="TestColumn", description="", data=array.squeeze())
    dynamic_table = DynamicTable(name="TestDynamicTable", description="", columns=[column])
    nwbfile.add_acquisition(dynamic_table)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="zarr"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, ZarrDatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == column.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestDynamicTable/TestColumn/data"
    assert dataset_configuration.dataset_info.maxshape == array.shape
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None
    assert dataset_configuration.filter_methods is None
    assert dataset_configuration.filter_options is None


def test_generic_iterator_wrapped_dynamic_table_hdf5():
    array = np.array([0.1, 0.2, 0.3])

    nwbfile = mock_NWBFile()
    column = VectorData(name="TestColumn", description="", data=SliceableDataChunkIterator(data=array.squeeze()))
    dynamic_table = DynamicTable(
        name="TestDynamicTable",
        description="",
        id=list(range(array.shape[0])),  # Need to include ID since the data of the column is not wrapped in an IO
        columns=[column],
    )
    nwbfile.add_acquisition(dynamic_table)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="hdf5"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, HDF5DatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == column.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestDynamicTable/TestColumn/data"
    assert dataset_configuration.dataset_info.maxshape == (array.shape[0],)
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None


def test_generic_iterator_wrapped_dynamic_table_zarr():
    array = np.array([0.1, 0.2, 0.3])

    nwbfile = mock_NWBFile()
    column = VectorData(name="TestColumn", description="", data=SliceableDataChunkIterator(data=array.squeeze()))
    dynamic_table = DynamicTable(
        name="TestDynamicTable",
        description="",
        id=list(range(array.shape[0])),  # Need to include ID since the data of the column is not wrapped in an IO
        columns=[column],
    )
    nwbfile.add_acquisition(dynamic_table)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="zarr"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, ZarrDatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == column.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestDynamicTable/TestColumn/data"
    assert dataset_configuration.dataset_info.maxshape == (array.shape[0],)
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None
    assert dataset_configuration.filter_methods is None
    assert dataset_configuration.filter_options is None


def test_classic_iterator_wrapped_dynamic_table_hdf5():
    array = np.array([0.1, 0.2, 0.3])

    nwbfile = mock_NWBFile()
    column = VectorData(name="TestColumn", description="", data=DataChunkIterator(data=array.squeeze()))
    dynamic_table = DynamicTable(
        name="TestDynamicTable",
        description="",
        id=list(range(array.shape[0])),  # Need to include ID since the data of the column is not wrapped in an IO
        columns=[column],
    )
    nwbfile.add_acquisition(dynamic_table)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="hdf5"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, HDF5DatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == column.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestDynamicTable/TestColumn/data"
    assert dataset_configuration.dataset_info.maxshape == (array.shape[0],)
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None


def test_classic_iterator_wrapped_dynamic_table_zarr():
    array = np.array([0.1, 0.2, 0.3])

    nwbfile = mock_NWBFile()
    column = VectorData(name="TestColumn", description="", data=DataChunkIterator(data=array.squeeze()))
    dynamic_table = DynamicTable(
        name="TestDynamicTable",
        description="",
        id=list(range(array.shape[0])),  # Need to include ID since the data of the column is not wrapped in an IO
        columns=[column],
    )
    nwbfile.add_acquisition(dynamic_table)

    dataset_configurations = list(get_default_dataset_configurations(nwbfile=nwbfile, backend="zarr"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, ZarrDatasetConfiguration)
    assert dataset_configuration.dataset_info.object_id == column.object_id
    assert dataset_configuration.dataset_info.location == "acquisition/TestDynamicTable/TestColumn/data"
    assert dataset_configuration.dataset_info.maxshape == (array.shape[0],)
    assert dataset_configuration.dataset_info.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None
    assert dataset_configuration.filter_methods is None
    assert dataset_configuration.filter_options is None
