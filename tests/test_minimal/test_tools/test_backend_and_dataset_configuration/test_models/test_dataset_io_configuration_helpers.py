"""Unit tests for helper functions of DatasetIOConfiguration."""

import numpy as np
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers._configuration_models._base_dataset_io import (
    _find_location_in_memory_nwbfile,
    _infer_dtype,
)


def test_find_location_in_memory_nwbfile():
    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TimeSeries")
    nwbfile.add_acquisition(time_series)
    neurodata_object = nwbfile.acquisition["TimeSeries"]
    location = _find_location_in_memory_nwbfile(neurodata_object=neurodata_object, field_name="data")
    assert location == "acquisition/TimeSeries/data"


def test_infer_dtype_array():
    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TimeSeries", data=np.array([1.0, 2.0, 3.0], dtype="float64"))
    nwbfile.add_acquisition(time_series)
    dataset = nwbfile.acquisition["TimeSeries"].data
    dtype = _infer_dtype(dataset)
    assert dtype == np.dtype("float64")


def test_infer_dtype_list():
    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TimeSeries", data=[1.0, 2.0, 3.0])
    nwbfile.add_acquisition(time_series)
    dataset = nwbfile.acquisition["TimeSeries"].data
    dtype = _infer_dtype(dataset)
    assert dtype == np.dtype("float64")


def test_infer_dtype_object():
    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TimeSeries", data=(1.0, 2.0, 3.0))
    nwbfile.add_acquisition(time_series)
    dataset = nwbfile.acquisition["TimeSeries"]
    dtype = _infer_dtype(dataset)
    assert dtype == np.dtype("object")
