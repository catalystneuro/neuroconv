import re

import numpy as np
import pytest
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal
from pynwb import get_manager
from pynwb.behavior import BehavioralTimeSeries
from pynwb.ophys import PlaneSegmentation
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.ecephys import mock_ElectrodeGroup
from pynwb.testing.mock.file import mock_NWBFile
from pynwb.testing.mock.ophys import mock_ImagingPlane

from neuroconv.tools.hdmf import (
    SliceableDataChunkIterator,
    _find_sub_builder,
    get_dataset_builder,
    get_full_data_shape,
    has_compound_dtype,
)


class TestIteratorAssertions(TestCase):
    def test_buffer_bigger_than_chunk_assertion(self):
        with self.assertRaisesWith(
            AssertionError, exc_msg="buffer_gb (5e-06) must be greater than the chunk size (0.008)!"
        ):
            SliceableDataChunkIterator(data=np.empty(shape=(1000, 1000)), buffer_gb=0.000005)


def test_early_exit():
    """Uses a 32 byte array with 1 GB buffer size (default) and 1 MB chunk size (default)."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(2, 2)))
    assert iterator.maxshape == iterator.buffer_shape


def test_buffer_padding_long_shape():
    """Uses ~8 MB array with 11 MB buffer size and 1 MB chunk size (default)."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(10**7, 20)), buffer_gb=1.1e-2)
    assert iterator.buffer_shape == (1000000, 1)


def test_buffer_padding_mixed_shape():
    """Uses ~15 MB array with 11 MB buffer size and 1 MB chunk size (default)."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(20, 40, 2401)), buffer_gb=1.1e-2)
    assert iterator.buffer_shape == (17, 34, 2040)


def test_min_axis_too_large():
    """Uses ~8 MB array with each contiguous axis at around ~8 KB with 5 KB buffer_size and 1 KB chunk size."""
    iterator = SliceableDataChunkIterator(data=np.empty(shape=(1000, 1000)), chunk_mb=1e-3, buffer_gb=5e-6)
    assert iterator.buffer_shape == (22, 22)


def test_sliceable_data_chunk_iterator():
    data = np.arange(100).reshape(10, 10)

    iterator = SliceableDataChunkIterator(data=data, buffer_shape=(5, 5), chunk_shape=(5, 5))

    data_chunk = next(iterator)

    assert data_chunk.selection == (slice(0, 5, None), slice(0, 5, None))

    assert_array_equal(
        data_chunk.data,
        [[0, 1, 2, 3, 4], [10, 11, 12, 13, 14], [20, 21, 22, 23, 24], [30, 31, 32, 33, 34], [40, 41, 42, 43, 44]],
    )


def test_sliceable_data_chunk_iterator_edge_case_1():
    """Caused an error prior to https://github.com/catalystneuro/neuroconv/pull/735."""
    shape = (3600, 304, 608)
    buffer_gb = 0.5

    random_number_generator = np.random.default_rng(seed=0)
    dtype = "uint16"

    low = np.iinfo(dtype).min
    high = np.iinfo(dtype).max
    integer_array = random_number_generator.integers(low=low, high=high, size=shape, dtype=dtype)

    iterator = SliceableDataChunkIterator(data=integer_array, buffer_gb=buffer_gb)

    assert iterator.buffer_shape == (2013, 183, 366)
    assert iterator.chunk_shape == (671, 61, 122)


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


def test_get_full_data_shape():
    nwbfile = mock_NWBFile()
    data = np.array(
        [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
        ]
    )
    time_series = mock_TimeSeries(name="TimeSeries", data=data)
    nwbfile.add_acquisition(time_series)

    manager = get_manager()
    builder = manager.build(nwbfile)
    location_in_file = "acquisition/TimeSeries/data"
    dataset = nwbfile.acquisition["TimeSeries"].data
    full_data_shape = get_full_data_shape(dataset=dataset, builder=builder, location_in_file=location_in_file)

    assert full_data_shape == (2, 3)


def test_get_full_data_shape_compound():
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
    dataset = nwbfile.processing["ophys"]["PlaneSegmentation"].pixel_mask
    full_data_shape = get_full_data_shape(dataset=dataset, builder=builder, location_in_file=location_in_file)

    assert full_data_shape == (1,)


def test_get_full_data_shape_no_builder():
    nwbfile = mock_NWBFile()
    data = np.array(
        [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
        ]
    )
    time_series = mock_TimeSeries(name="TimeSeries", data=data)
    nwbfile.add_acquisition(time_series)

    location_in_file = "acquisition/TimeSeries/data"
    dataset = nwbfile.acquisition["TimeSeries"].data
    full_data_shape = get_full_data_shape(dataset=dataset, builder=None, location_in_file=location_in_file)

    assert full_data_shape == (2, 3)
