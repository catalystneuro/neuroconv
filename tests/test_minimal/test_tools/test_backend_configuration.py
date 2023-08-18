from pathlib import Path

import pytest
import numpy as np
from pynwb import NWBFile, NWBHDF5IO
from pynwb.base import DynamicTable
from hdmf_zarr import NWBZarrIO
from pynwb.testing.mock.file import mock_NWBFile
from pynwb.testing.mock.base import mock_TimeSeries

from neuroconv.tools.nwb_helpers import Dataset, get_io_datasets

MEMMAP_SHAPE = (30_000, 16)
MEMMAP_DTYPE = "int16"

@pytest.fixture(scope="session")
def memmap_file(tmpdir_factory):
    memmap_file_path = str(tmpdir_factory.mktemp("data").join("test_memmap.dat"))  # All calls to np.memmap expect str
    if not Path(memmap_file_path).exists():
        np.memmap(filename=memmap_file_path, mode="w+", shape=MEMMAP_SHAPE, dtype=MEMMAP_DTYPE)
    return memmap_file_path

# TODO: consider adding non-memmap cases

def generate_nwbfile_with_datasets() -> NWBFile:
    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(data=np.memmap(filename=filename, mode="r", shape=MEMMAP_SHAPE, dtype=MEMMAP_DTYPE))
    nwbfile.add_acquisition(time_series)
    return nwbfile

@pytest.fixture(scope="session")
def hdf5_nwbfile_path(tmpdir_factory):
    nwbfile_path = tmpdir_factory.mktemp("data").join("test_hdf5_nwbfile_with_datasets.nwb")
    if not Path(nwbfile_path).exists():
        nwbfile = generate_nwbfile_with_datasets()
        with NWBZarrIO(path=str(nwbfile_path), mode="w") as io:
            io.write(nwbfile)
    return nwbfile_path

@pytest.fixture(scope="session")
def zarr_nwbfile_path(tmpdir_factory):
    nwbfile_path = tmpdir_factory.mktemp("data").join("test_zarr_nwbfile_with_datasets.nwb")
    if not Path(nwbfile_path).exists():
        nwbfile = generate_nwbfile_with_datasets()
        with NWBZarrIO(path=str(nwbfile_path), mode="w") as io:
            io.write(nwbfile)
    return nwbfile_path

def test_simple_time_series(memmap_file):
    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(
        name="TimeSeries",
        data=np.memmap(filename=memmap_file, mode="r", shape=MEMMAP_SHAPE, dtype=MEMMAP_DTYPE),
    )
    nwbfile.add_acquisition(time_series)

    results = list(get_io_datasets(nwbfile=nwbfile))
    
    assert len(results) == 1
    
    result = results[0]
    assert isinstance(result, Dataset)
    assert result.object_name == "TimeSeries"
    assert result.field == "data"
    assert result.maxshape == MEMMAP_SHAPE
    assert result.dtype == MEMMAP_DTYPE  # TODO: add tests for if source specification was np.dtype et al.

def test_simple_dynamic_table(memmap_file):
    nwbfile = mock_NWBFile()
    column_length = MEMMAP_SHAPE[1]
    dynamic_table = DynamicTable(
        name="DynamicTable",
        description="",
        id=list(range(column_length)),  # Need to include ID since the data of the column is not wrapped in an IO
    )
    dynamic_table.add_column(
        name="TestColumn",
        description="",
        data=np.memmap(filename=memmap_file, mode="r", shape=MEMMAP_SHAPE, dtype=MEMMAP_DTYPE)[0,:],
    )
    nwbfile.add_acquisition(dynamic_table)

    results = list(get_io_datasets(nwbfile=nwbfile))
    
    assert len(results) == 1
    
    result = results[0]
    assert isinstance(result, Dataset)
    assert result.object_name == "TestColumn"
    assert result.field == "data"
    assert result.maxshape == (column_length,)
    assert result.dtype == MEMMAP_DTYPE

    