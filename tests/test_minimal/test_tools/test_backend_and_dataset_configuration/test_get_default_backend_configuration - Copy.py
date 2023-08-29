from io import StringIO
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, NWBFile
from pynwb.base import DynamicTable
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import Dataset, get_io_datasets

# MEMMAP_SHAPE = (30_000, 16)
# MEMMAP_DTYPE = "int16"


# @pytest.fixture(scope="session")
# def memmap_file(tmpdir_factory):
#     memmap_file_path = str(tmpdir_factory.mktemp("data").join("test_memmap.dat"))  # All calls to np.memmap expect str
#     if not Path(memmap_file_path).exists():
#         np.memmap(filename=memmap_file_path, mode="w+", shape=MEMMAP_SHAPE, dtype=MEMMAP_DTYPE)
#     return memmap_file_path


def generate_1d_array() -> NWBFile:
    array = np.array([[0.1, 0.2, 0.3]])
    return array


def generate_2d_array() -> NWBFile:
    array = np.array([[1, 2, 3], [4, 5, 6]])
    return array


def generate_nwbfile_with_datasets() -> NWBFile:
    nwbfile = mock_NWBFile()
    array = generate_2d_array()
    time_series = mock_TimeSeries(data=array)
    nwbfile.add_acquisition(time_series)
    return nwbfile


@pytest.fixture(scope="session")
def hdf5_nwbfile_path(tmpdir_factory):
    nwbfile_path = tmpdir_factory.mktemp("data").join("test_hdf5_nwbfile_with_datasets.nwb")
    if not Path(nwbfile_path).exists():
        nwbfile = generate_nwbfile_with_datasets()
        with NWBHDF5IO(path=str(nwbfile_path), mode="w") as io:
            io.write(nwbfile)
    return str(nwbfile_path)


@pytest.fixture(scope="session")
def zarr_nwbfile_path(tmpdir_factory):
    nwbfile_path = tmpdir_factory.mktemp("data").join("test_zarr_nwbfile_with_datasets.nwb")
    if not Path(nwbfile_path).exists():
        nwbfile = generate_nwbfile_with_datasets()
        with NWBZarrIO(path=str(nwbfile_path), mode="w") as io:
            io.write(nwbfile)
    return str(nwbfile_path)


def test_dataset_print():
    """Test the printout display of a Dataset modellooks nice."""
    test_dataset = Dataset(
        object_id="abc123",
        object_name="TestObject",
        parent="TestParent",
        field="data",
        maxshape=(2, 4),
        dtype="int16",
    )

    with patch("sys.stdout", new=StringIO()) as out:
        print(test_dataset)

    expected_print = """TestObject of TestParent
------------------------
  data
    maxshape: (2, 4)
    dtype: int16
"""
    assert out.getvalue() == expected_print


def test_dataset_repr():
    """Test the programmatic repr of a Dataset model is more dataclass-like."""
    test_dataset = Dataset(
        object_id="abc123",
        object_name="TestObject",
        parent="TestParent",
        field="data",
        maxshape=(2, 4),
        dtype="int16",
    )

    # Important to keep the `repr` unmodified for appearence inside lists of Datasets
    expected_repr = (
        "Dataset(object_id='abc123', object_name='TestObject', parent='TestParent', "
        "field='data', maxshape=(2, 4), dtype='int16')"
    )
    assert repr(test_dataset) == expected_repr


def test_simple_time_series():
    array = generate_2d_array()

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TimeSeries", data=array)
    nwbfile.add_acquisition(time_series)

    results = list(get_io_datasets(nwbfile=nwbfile))

    assert len(results) == 1

    result = results[0]
    assert isinstance(result, Dataset)
    assert result.object_name == "TimeSeries"
    assert result.field == "data"
    assert result.maxshape == array.shape
    assert result.dtype == array.dtype


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

    results = list(get_io_datasets(nwbfile=nwbfile))

    assert len(results) == 1

    result = results[0]
    assert isinstance(result, Dataset)
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

        results = list(get_io_datasets(nwbfile=nwbfile))

    assert len(results) == 1

    result = results[0]
    assert isinstance(result, Dataset)
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

        results = list(get_io_datasets(nwbfile=nwbfile))

    assert len(results) == 1

    result = results[0]
    assert isinstance(result, Dataset)
    assert result.object_name == "NewTimeSeries"
    assert result.field == "data"
    assert result.maxshape == array.shape
    assert result.dtype == str(array.dtype)  # TODO: add tests for if source specification was np.dtype et al.
