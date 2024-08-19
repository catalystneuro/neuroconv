"""Integration tests for `get_default_backend_configuration`."""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from pynwb import NWBHDF5IO, H5DataIO, NWBFile
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import (
    HDF5BackendConfiguration,
    get_existing_backend_configuration,
    get_module,
)


def generate_complex_nwbfile() -> NWBFile:
    nwbfile = mock_NWBFile()

    raw_array = np.array([[1, 2, 3], [4, 5, 6]])
    raw_time_series = mock_TimeSeries(name="RawTimeSeries", data=raw_array)
    nwbfile.add_acquisition(raw_time_series)

    number_of_trials = 10
    for start_time, stop_time in zip(
        np.linspace(start=0.0, stop=10.0, num=number_of_trials), np.linspace(start=1.0, stop=11.0, num=number_of_trials)
    ):
        nwbfile.add_trial(start_time=start_time, stop_time=stop_time)

    ecephys_module = get_module(nwbfile=nwbfile, name="ecephys")
    processed_array = np.array([[7.0, 8.0], [9.0, 10.0], [11.0, 12.0], [13.0, 14.0]])
    processed_time_series = mock_TimeSeries(name="ProcessedTimeSeries", data=processed_array)
    ecephys_module.add(processed_time_series)

    return nwbfile


@pytest.fixture(scope="session")
def hdf5_nwbfile_path(tmpdir_factory):
    nwbfile_path = tmpdir_factory.mktemp("data").join("test_default_backend_configuration_hdf5_nwbfile.nwb.h5")
    if not Path(nwbfile_path).exists():
        nwbfile = generate_complex_nwbfile()

        # Add a H5DataIO-compressed time series
        raw_array = np.array([[11, 21, 31], [41, 51, 61]], dtype="int32")
        data = H5DataIO(data=raw_array, compression="gzip", compression_opts=2)
        raw_time_series = mock_TimeSeries(name="CompressedRawTimeSeries", data=data)
        nwbfile.add_acquisition(raw_time_series)

        with NWBHDF5IO(path=str(nwbfile_path), mode="w") as io:
            io.write(nwbfile)
    return str(nwbfile_path)


def test_complex_hdf5(hdf5_nwbfile_path):
    with NWBHDF5IO(path=hdf5_nwbfile_path, mode="a") as io:
        nwbfile = io.read()
        backend_configuration = get_existing_backend_configuration(nwbfile=nwbfile)

    assert isinstance(backend_configuration, HDF5BackendConfiguration)

    dataset_configurations = backend_configuration.dataset_configurations
    assert len(dataset_configurations) == 5

    # Best summary test of expected output is the printout
    with patch("sys.stdout", new=StringIO()) as stdout:
        print(backend_configuration)

    expected_print = """
HDF5 dataset configurations
---------------------------

intervals/trials/start_time/data
--------------------------------
  dtype : float64
  full shape of source array : (10,)
  full size of source array : 80 B

  buffer shape : (10,)
  expected RAM usage : 80 B

  compression options : {'compression_opts': None}


intervals/trials/stop_time/data
-------------------------------
  dtype : float64
  full shape of source array : (10,)
  full size of source array : 80 B

  buffer shape : (10,)
  expected RAM usage : 80 B

  compression options : {'compression_opts': None}


processing/ecephys/ProcessedTimeSeries/data
-------------------------------------------
  dtype : float64
  full shape of source array : (4, 2)
  full size of source array : 64 B

  buffer shape : (4, 2)
  expected RAM usage : 64 B

  compression options : {'compression_opts': None}


acquisition/RawTimeSeries/data
------------------------------
  dtype : int64
  full shape of source array : (2, 3)
  full size of source array : 48 B

  buffer shape : (2, 3)
  expected RAM usage : 48 B

  compression options : {'compression_opts': None}


acquisition/CompressedRawTimeSeries/data
----------------------------------------
  dtype : int32
  full shape of source array : (2, 3)
  full size of source array : 24 B

  buffer shape : (2, 3)
  expected RAM usage : 24 B

  chunk shape : (2, 3)
  disk space usage per chunk : 24 B

  compression method : gzip
  compression options : {'compression_opts': 2}

"""
    assert stdout.getvalue() == expected_print
