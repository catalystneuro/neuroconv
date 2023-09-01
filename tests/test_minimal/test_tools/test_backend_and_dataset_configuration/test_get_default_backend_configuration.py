"""Unit tests for `get_default_backend_configuration`."""
from pathlib import Path

import numpy as np
import pytest
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, NWBFile
from pynwb.base import DynamicTable
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import (
    ConfigurableDataset,
    HDF5BackendConfiguration,
    HDF5DatasetConfiguration,
    ZarrBackendConfiguration,
    ZarrDatasetConfiguration,
    get_default_backend_configuration,
)


def generate_1d_array() -> NWBFile:
    array = np.array([[0.1, 0.2, 0.3]])
    return array


def generate_2d_array() -> NWBFile:
    array = np.array([[1, 2, 3], [4, 5, 6]])
    return array


def generate_nwbfile_with_ConfigurableDatasets() -> NWBFile:
    nwbfile = mock_NWBFile()
    array = generate_2d_array()
    time_series = mock_TimeSeries(data=array)
    nwbfile.add_acquisition(time_series)
    return nwbfile


@pytest.fixture(scope="session")
def hdf5_nwbfile_path(tmpdir_factory):
    nwbfile_path = tmpdir_factory.mktemp("data").join("test_hdf5_nwbfile_with_configurable_datasets.nwb.h5")
    if not Path(nwbfile_path).exists():
        nwbfile = generate_nwbfile_with_ConfigurableDatasets()
        with NWBHDF5IO(path=str(nwbfile_path), mode="w") as io:
            io.write(nwbfile)
    return str(nwbfile_path)


@pytest.fixture(scope="session")
def zarr_nwbfile_path(tmpdir_factory):
    nwbfile_path = tmpdir_factory.mktemp("data").join("test_zarr_nwbfile_with_configurable_datasets.nwb.zarr")
    if not Path(nwbfile_path).exists():
        nwbfile = generate_nwbfile_with_ConfigurableDatasets()
        with NWBZarrIO(path=str(nwbfile_path), mode="w") as io:
            io.write(nwbfile)
    return str(nwbfile_path)


def test_simple_time_series_hdf5_backend():
    array = generate_2d_array()

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(
        name="TimeSeries", data=SliceableDataChunkIterator(data=array, chunk_shape=(1, 2), buffer_shape=(1, 3))
    )
    nwbfile.add_acquisition(time_series)

    default_backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend_type="hdf5")

    assert isinstance(default_backend_configuration, HDF5BackendConfiguration)
    assert len(default_backend_configuration.dataset_configurations) == 1

    default_configurable_dataset, default_dataset_configuration = next(
        iter(default_backend_configuration.dataset_configurations.items())
    )
    assert isinstance(default_configurable_dataset, ConfigurableDataset)
    assert default_configurable_dataset.object_name == "TimeSeries"
    assert default_configurable_dataset.parent == "root"
    assert default_configurable_dataset.field == "data"
    assert default_configurable_dataset.maxshape == (2, 3)
    assert default_configurable_dataset.dtype == "int32"

    assert isinstance(default_dataset_configuration, HDF5DatasetConfiguration)
    assert default_dataset_configuration.object_name == "TimeSeries"
    assert default_dataset_configuration.parent == "root"
    assert default_dataset_configuration.field == "data"
    assert default_dataset_configuration.chunk_shape == (1, 2)
    assert default_dataset_configuration.buffer_shape == (1, 3)
    assert default_dataset_configuration.maxshape == (2, 3)
    assert default_dataset_configuration.dtype == "int32"
    assert default_dataset_configuration.compression_method == "gzip"
    assert default_dataset_configuration.compression_options is None


def test_simple_time_series_zarr_backend():
    array = generate_2d_array()

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(
        name="TimeSeries", data=SliceableDataChunkIterator(data=array, chunk_shape=(1, 2), buffer_shape=(1, 3))
    )
    nwbfile.add_acquisition(time_series)

    default_backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend_type="zarr")

    assert isinstance(default_backend_configuration, ZarrBackendConfiguration)
    assert default_backend_configuration.number_of_jobs == -2
    assert len(default_backend_configuration.dataset_configurations) == 1

    default_configurable_dataset, default_dataset_configuration = next(
        iter(default_backend_configuration.dataset_configurations.items())
    )
    assert isinstance(default_configurable_dataset, ConfigurableDataset)
    assert default_configurable_dataset.object_name == "TimeSeries"
    assert default_configurable_dataset.parent == "root"
    assert default_configurable_dataset.field == "data"
    assert default_configurable_dataset.maxshape == (2, 3)
    assert default_configurable_dataset.dtype == "int32"

    assert isinstance(default_dataset_configuration, ZarrDatasetConfiguration)
    assert default_dataset_configuration.object_name == "TimeSeries"
    assert default_dataset_configuration.parent == "root"
    assert default_dataset_configuration.field == "data"
    assert default_dataset_configuration.chunk_shape == (1, 2)
    assert default_dataset_configuration.buffer_shape == (1, 3)
    assert default_dataset_configuration.maxshape == (2, 3)
    assert default_dataset_configuration.dtype == "int32"
    assert default_dataset_configuration.compression_method == "gzip"
    assert default_dataset_configuration.compression_options is None
    assert default_dataset_configuration.filter_methods is None
    assert default_dataset_configuration.filter_options is None


def test_simple_dynamic_table():
    array = generate_1d_array()

    nwbfile = mock_NWBFile()
    column_length = array.shape[1]
    dynamic_table = DynamicTable(
        name="DynamicTable",
        description="",
        id=list(range(column_length)),  # Need to include ID since the data of the column is not wrapped in an IO
    )
    dynamic_table.add_column(name="TestColumn", description="", data=array.squeeze())
    nwbfile.add_acquisition(dynamic_table)

    results = list(get_default_backend_configuration(nwbfile=nwbfile))

    assert len(results) == 1

    result = results[0]
    assert isinstance(result, ConfigurableDataset)
    assert result.object_name == "TestColumn"
    assert result.field == "data"
    assert result.maxshape == (column_length,)
    assert result.dtype == str(array.dtype)


def test_simple_on_appended_hdf5_file(hdf5_nwbfile_path):
    array = generate_2d_array()

    with NWBHDF5IO(path=hdf5_nwbfile_path, mode="a") as io:
        nwbfile = io.read()
        array = generate_2d_array()
        new_time_series = mock_TimeSeries(name="NewTimeSeries", data=array)
        nwbfile.add_acquisition(new_time_series)

        results = list(get_default_backend_configuration(nwbfile=nwbfile))

    assert len(results) == 1

    result = results[0]
    assert isinstance(result, ConfigurableDataset)
    assert result.object_name == "NewTimeSeries"
    assert result.field == "data"
    assert result.maxshape == array.shape
    assert result.dtype == str(array.dtype)  # TODO: add tests for if source specification was np.dtype et al.


def test_simple_on_appended_zarr_file(zarr_nwbfile_path):
    array = generate_2d_array()

    with NWBZarrIO(path=zarr_nwbfile_path, mode="a") as io:
        nwbfile = io.read()
        array = generate_2d_array()
        new_time_series = mock_TimeSeries(name="NewTimeSeries", data=array)
        nwbfile.add_acquisition(new_time_series)

        results = list(get_default_backend_configuration(nwbfile=nwbfile))

    assert len(results) == 1

    result = results[0]
    assert isinstance(result, ConfigurableDataset)
    assert result.object_name == "NewTimeSeries"
    assert result.field == "data"
    assert result.maxshape == array.shape
    assert result.dtype == str(array.dtype)  # TODO: add tests for if source specification was np.dtype et al.
