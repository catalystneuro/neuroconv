"""Unit tests for helper functions of DatasetIOConfiguration."""

import re

import numpy as np
import pytest
from pynwb import get_manager
from pynwb.behavior import BehavioralTimeSeries
from pynwb.ophys import PlaneSegmentation
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.ecephys import mock_ElectrodeGroup
from pynwb.testing.mock.file import mock_NWBFile
from pynwb.testing.mock.ophys import mock_ImagingPlane

from neuroconv.tools.nwb_helpers._configuration_models._base_dataset_io import (
    _find_location_in_memory_nwbfile,
    _find_sub_builder,
    _infer_dtype,
    get_dataset_builder,
    has_compound_dtype,
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


def test_find_sub_builder_shallow():
    nwbfile = mock_NWBFile()
    data = np.array([1.0, 2.0, 3.0], dtype="float64")
    time_series = mock_TimeSeries(name="TimeSeries", data=data)
    nwbfile.add_acquisition(time_series)
    manager = get_manager()
    builder = manager.build(nwbfile)
    acquisition_builder = _find_sub_builder(builder, "acquisition")
    time_series_builder = _find_sub_builder(acquisition_builder, "TimeSeries")
    np.testing.assert_array_equal(time_series_builder["data"].data, data)


def test_find_sub_builder_deep():
    nwbfile = mock_NWBFile()
    data = np.array([1.0, 2.0, 3.0], dtype="float64")
    time_series = mock_TimeSeries(name="TimeSeries", data=data)
    nwbfile.add_acquisition(time_series)
    neurodata_object = nwbfile.acquisition["TimeSeries"]
    manager = get_manager()
    builder = manager.build(nwbfile)
    time_series_builder = _find_sub_builder(builder, "TimeSeries")
    np.testing.assert_array_equal(time_series_builder["data"].data, data)


def test_find_sub_builder_breadth_first():
    nwbfile = mock_NWBFile()
    data1 = np.array([1.0, 2.0, 3.0], dtype="float64")
    time_series1 = mock_TimeSeries(name="TimeSeries", data=data1)
    behavioral_time_series = BehavioralTimeSeries(name="BehavioralTimeSeries", time_series=[time_series1])
    behavior1_module = nwbfile.create_processing_module(name="behavior1", description="Behavioral data")
    behavior1_module.add(behavioral_time_series)

    behavior2_module = nwbfile.create_processing_module(name="behavior2", description="Behavioral data")
    data2 = np.array([4.0, 5.0, 6.0], dtype="float64")
    time_series2 = mock_TimeSeries(name="TimeSeries", data=data2)
    behavior2_module.add(time_series2)

    manager = get_manager()
    builder = manager.build(nwbfile)
    assert list(builder["processing"].keys()) == [
        "behavior1",
        "behavior2",
    ]  # double check that depth-first would find 'behavior1' first
    time_series_builder = _find_sub_builder(builder, "TimeSeries")
    np.testing.assert_array_equal(time_series_builder["data"].data, data2)


def test_get_dataset_builder_time_series():
    nwbfile = mock_NWBFile()
    data = np.array([1.0, 2.0, 3.0], dtype="float64")
    time_series = mock_TimeSeries(name="TimeSeries", data=data)
    nwbfile.add_acquisition(time_series)
    manager = get_manager()
    builder = manager.build(nwbfile)
    location_in_file = "acquisition/TimeSeries/data"
    dataset_builder = get_dataset_builder(builder=builder, location_in_file=location_in_file)
    np.testing.assert_array_equal(dataset_builder.data, data)


def test_get_dataset_builder_electrodes():
    nwbfile = mock_NWBFile()
    group = mock_ElectrodeGroup(nwbfile=nwbfile)
    nwbfile.add_electrode(location="test_location", group=group, group_name=group.name)
    manager = get_manager()
    builder = manager.build(nwbfile)
    location_in_file = "electrodes/location"
    dataset_builder = get_dataset_builder(builder=builder, location_in_file=location_in_file)
    assert dataset_builder.data == ["test_location"]


def test_get_dataset_builder_stimulus():
    nwbfile = mock_NWBFile()
    data = np.array([1.0, 2.0, 3.0], dtype="float64")
    time_series = mock_TimeSeries(name="TimeSeries", data=data)
    nwbfile.add_stimulus(time_series)
    manager = get_manager()
    builder = manager.build(nwbfile)
    location_in_file = "stimulus/TimeSeries/data"
    dataset_builder = get_dataset_builder(builder=builder, location_in_file=location_in_file)
    np.testing.assert_array_equal(dataset_builder.data, data)


def test_get_dataset_builder_missing():
    nwbfile = mock_NWBFile()
    manager = get_manager()
    builder = manager.build(nwbfile)
    location_in_file = "acquisition/missing"
    error_message = re.escape(f"Could not find location '{location_in_file}' in builder (missing is missing).")
    with pytest.raises(ValueError, match=error_message):
        get_dataset_builder(builder=builder, location_in_file=location_in_file)


def test_get_dataset_builder_not_a_dataset():
    nwbfile = mock_NWBFile()
    manager = get_manager()
    builder = manager.build(nwbfile)
    location_in_file = "acquisition"
    error_message = re.escape(
        f"Could not find location '{location_in_file}' in builder (acquisition is not a dataset)."
    )
    with pytest.raises(ValueError, match=error_message):
        get_dataset_builder(builder=builder, location_in_file=location_in_file)


def test_has_compound_dtype_True():
    nwbfile = mock_NWBFile()
    imaging_plane = mock_ImagingPlane(nwbfile=nwbfile)
    plane_segmentation = PlaneSegmentation(
        name="PlaneSegmentation",
        description="description",
        imaging_plane=imaging_plane,
    )
    pixel_mask = [[0, 0, 1]]
    plane_segmentation.add_roi(pixel_mask=pixel_mask)
    nwbfile.processing["ophys"].add(plane_segmentation)

    manager = get_manager()
    builder = manager.build(nwbfile)
    location_in_file = "processing/ophys/PlaneSegmentation/pixel_mask"
    assert has_compound_dtype(builder=builder, location_in_file=location_in_file)


def test_has_compound_dtype_False():
    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TimeSeries")
    nwbfile.add_acquisition(time_series)

    manager = get_manager()
    builder = manager.build(nwbfile)
    location_in_file = "acquisition/TimeSeries/data"
    assert not has_compound_dtype(builder=builder, location_in_file=location_in_file)
