"""
Unit tests for `get_default_dataset_io_configurations` operating on already written files open in append mode.
Mostly testing that the right objects are skipped from identification as candidates for configuration.
"""

from pathlib import Path

import numpy as np
import pytest
from hdmf.common import VectorData
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, NWBFile
from pynwb.base import DynamicTable
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import (
    HDF5DatasetIOConfiguration,
    ZarrDatasetIOConfiguration,
    get_default_dataset_io_configurations,
)


def generate_nwbfile_with_existing_time_series() -> NWBFile:
    nwbfile = mock_NWBFile()
    array = np.array([[1, 2, 3], [4, 5, 6]])
    time_series = mock_TimeSeries(name="ExistingTimeSeries", data=array)
    nwbfile.add_acquisition(time_series)
    return nwbfile


@pytest.fixture(scope="session")
def hdf5_nwbfile_path(tmpdir_factory):
    nwbfile_path = tmpdir_factory.mktemp("data").join("test_default_dataset_configurations_hdf5_nwbfile_.nwb")
    if not Path(nwbfile_path).exists():
        nwbfile = generate_nwbfile_with_existing_time_series()
        with NWBHDF5IO(path=str(nwbfile_path), mode="w") as io:
            io.write(nwbfile)
    return str(nwbfile_path)


@pytest.fixture(scope="session")
def zarr_nwbfile_path(tmpdir_factory):
    nwbfile_path = tmpdir_factory.mktemp("data").join("test_default_dataset_configurations_zarr_nwbfile.nwb.zarr")
    if not Path(nwbfile_path).exists():
        nwbfile = generate_nwbfile_with_existing_time_series()
        with NWBZarrIO(path=str(nwbfile_path), mode="w") as io:
            io.write(nwbfile)
    return str(nwbfile_path)


def test_unwrapped_time_series_hdf5(hdf5_nwbfile_path):
    array = np.array([[1, 2, 3], [4, 5, 6]])

    with NWBHDF5IO(path=hdf5_nwbfile_path, mode="a") as io:
        nwbfile = io.read()
        new_time_series = mock_TimeSeries(name="NewTimeSeries", data=array)
        nwbfile.add_acquisition(new_time_series)
        dataset_configurations = list(get_default_dataset_io_configurations(nwbfile=nwbfile, backend="hdf5"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, HDF5DatasetIOConfiguration)
    assert dataset_configuration.object_id == new_time_series.object_id
    assert dataset_configuration.location_in_file == "acquisition/NewTimeSeries/data"
    assert dataset_configuration.full_shape == array.shape
    assert dataset_configuration.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None


def test_unwrapped_time_series_zarr(zarr_nwbfile_path):
    array = np.array([[1, 2, 3], [4, 5, 6]])

    with NWBZarrIO(path=zarr_nwbfile_path, mode="a") as io:
        nwbfile = io.read()
        new_time_series = mock_TimeSeries(name="NewTimeSeries", data=array)
        nwbfile.add_acquisition(new_time_series)
        dataset_configurations = list(get_default_dataset_io_configurations(nwbfile=nwbfile, backend="zarr"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, ZarrDatasetIOConfiguration)
    assert dataset_configuration.object_id == new_time_series.object_id
    assert dataset_configuration.location_in_file == "acquisition/NewTimeSeries/data"
    assert dataset_configuration.full_shape == array.shape
    assert dataset_configuration.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None
    assert dataset_configuration.filter_methods is None
    assert dataset_configuration.filter_options is None


def test_unwrapped_dynamic_table_hdf5(hdf5_nwbfile_path):
    array = np.array([0.1, 0.2, 0.3])

    with NWBHDF5IO(path=hdf5_nwbfile_path, mode="a") as io:
        nwbfile = io.read()
        column = VectorData(name="TestColumn", description="", data=array.squeeze())
        dynamic_table = DynamicTable(name="TestDynamicTable", description="", columns=[column])
        nwbfile.add_acquisition(dynamic_table)
        dataset_configurations = list(get_default_dataset_io_configurations(nwbfile=nwbfile, backend="hdf5"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, HDF5DatasetIOConfiguration)
    assert dataset_configuration.object_id == column.object_id
    assert dataset_configuration.location_in_file == "acquisition/TestDynamicTable/TestColumn/data"
    assert dataset_configuration.full_shape == array.shape
    assert dataset_configuration.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None


def test_unwrapped_dynamic_table_zarr(zarr_nwbfile_path):
    array = np.array([0.1, 0.2, 0.3])

    with NWBZarrIO(path=zarr_nwbfile_path, mode="a") as io:
        nwbfile = io.read()
        column = VectorData(name="TestColumn", description="", data=array.squeeze())
        dynamic_table = DynamicTable(name="TestDynamicTable", description="", columns=[column])
        nwbfile.add_acquisition(dynamic_table)
        dataset_configurations = list(get_default_dataset_io_configurations(nwbfile=nwbfile, backend="zarr"))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, ZarrDatasetIOConfiguration)
    assert dataset_configuration.object_id == column.object_id
    assert dataset_configuration.location_in_file == "acquisition/TestDynamicTable/TestColumn/data"
    assert dataset_configuration.full_shape == array.shape
    assert dataset_configuration.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None
    assert dataset_configuration.filter_methods is None
    assert dataset_configuration.filter_options is None
