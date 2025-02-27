"""Unit tests for `get_default_dataset_io_configurations`."""

from typing import Literal

import numpy as np
import pytest
from hdmf.common import VectorData
from hdmf.data_utils import DataChunkIterator
from pynwb.base import DynamicTable
from pynwb.behavior import CompassDirection
from pynwb.image import ImageSeries
from pynwb.misc import Units
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.behavior import mock_SpatialSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.importing import is_package_installed
from neuroconv.tools.nwb_helpers import (
    DATASET_IO_CONFIGURATIONS,
    get_default_dataset_io_configurations,
    get_module,
)


@pytest.mark.parametrize("iterator", [lambda x: x, SliceableDataChunkIterator, DataChunkIterator])
@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_time_series(iterator: callable, backend: Literal["hdf5", "zarr"]):
    array = np.array([[1, 2, 3], [4, 5, 6]])
    data = iterator(array)

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=data)
    nwbfile.add_acquisition(time_series)

    dataset_configurations = list(get_default_dataset_io_configurations(nwbfile=nwbfile, backend=backend))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
    assert dataset_configuration.object_id == time_series.object_id
    assert dataset_configuration.location_in_file == "acquisition/TestTimeSeries/data"
    assert dataset_configuration.full_shape == array.shape
    assert dataset_configuration.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None

    if backend == "zarr":
        assert dataset_configuration.filter_methods is None
        assert dataset_configuration.filter_options is None


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_electrical_series_with_non_wrapped_data(backend: Literal["hdf5", "zarr"]):
    # Test that ElectricalSeries is chunked appropriately even if data is passed as an array
    # See https://github.com/catalystneuro/neuroconv/issues/1099
    from pynwb.testing.mock.ecephys import mock_ElectricalSeries
    from pynwb.testing.mock.file import mock_NWBFile

    data = np.ones((10_000, 128))

    nwbfile = mock_NWBFile()

    es = mock_ElectricalSeries(data=data, name="ElectricalSeries")
    nwbfile.add_acquisition(es)
    dataset_configurations = list(get_default_dataset_io_configurations(nwbfile=nwbfile, backend=backend))

    assert len(dataset_configurations) == 1

    electrical_series_configuration = dataset_configurations[0]

    exppected_chunk_for_channels = 64
    assert electrical_series_configuration.chunk_shape[1] == exppected_chunk_for_channels


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_external_image_series(backend: Literal["hdf5", "zarr"]):
    nwbfile = mock_NWBFile()
    image_series = ImageSeries(name="TestImageSeries", external_file=[""], rate=1.0, format="external")
    nwbfile.add_acquisition(image_series)

    dataset_configurations = list(get_default_dataset_io_configurations(nwbfile=nwbfile, backend=backend))

    assert len(dataset_configurations) == 0


@pytest.mark.parametrize("iterator", [lambda x: x, SliceableDataChunkIterator, DataChunkIterator])
@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_dynamic_table(iterator: callable, backend: Literal["hdf5", "zarr"]):
    array = np.array([0.1, 0.2, 0.3])
    data = iterator(array)

    nwbfile = mock_NWBFile()
    column = VectorData(name="TestColumn", description="", data=data)
    dynamic_table = DynamicTable(name="TestDynamicTable", description="", columns=[column], id=list(range(len(array))))
    nwbfile.add_acquisition(dynamic_table)

    dataset_configurations = list(get_default_dataset_io_configurations(nwbfile=nwbfile, backend=backend))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
    assert dataset_configuration.object_id == column.object_id
    assert dataset_configuration.location_in_file == "acquisition/TestDynamicTable/TestColumn/data"
    assert dataset_configuration.full_shape == array.shape
    assert dataset_configuration.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None

    if backend == "zarr":
        assert dataset_configuration.filter_methods is None
        assert dataset_configuration.filter_options is None


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_ragged_units_table(backend: Literal["hdf5", "zarr"]):
    nwbfile = mock_NWBFile()
    units = Units(name="units", description="")

    spike_times = np.array([0.0, 1.0, 2.0])
    waveforms = np.array([[[1, 2, 3], [1, 2, 3], [1, 2, 3]], [[1, 2, 3], [1, 2, 3], [1, 2, 3]]], dtype="int32")
    units.add_unit(spike_times=spike_times, waveforms=waveforms)

    spike_times = np.array([3.0, 4.0])
    waveforms = np.array([[[4, 5], [4, 5], [4, 5]], [[4, 5], [4, 5], [4, 5]]], dtype="int32")
    units.add_unit(spike_times=spike_times, waveforms=waveforms)

    nwbfile.units = units

    dataset_configurations = list(get_default_dataset_io_configurations(nwbfile=nwbfile, backend=backend))

    assert len(dataset_configurations) == 5

    dataset_configuration = next(
        dataset_configuration
        for dataset_configuration in dataset_configurations
        if dataset_configuration.location_in_file == "units/spike_times/data"
    )
    assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
    assert dataset_configuration.full_shape == (5,)
    assert dataset_configuration.dtype == np.dtype("float64")
    assert dataset_configuration.chunk_shape == (5,)
    assert dataset_configuration.buffer_shape == (5,)
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None

    if backend == "zarr":
        assert dataset_configuration.filter_methods is None
        assert dataset_configuration.filter_options is None

    dataset_configuration = next(
        dataset_configuration
        for dataset_configuration in dataset_configurations
        if dataset_configuration.location_in_file == "units/spike_times_index/data"
    )
    assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
    assert dataset_configuration.full_shape == (2,)
    assert dataset_configuration.dtype == np.dtype("uint8")
    assert dataset_configuration.chunk_shape == (2,)
    assert dataset_configuration.buffer_shape == (2,)
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None

    if backend == "zarr":
        assert dataset_configuration.filter_methods is None
        assert dataset_configuration.filter_options is None

    dataset_configuration = next(
        dataset_configuration
        for dataset_configuration in dataset_configurations
        if dataset_configuration.location_in_file == "units/waveforms/data"
    )
    assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
    assert dataset_configuration.full_shape == (12, 3)
    assert dataset_configuration.dtype == np.dtype("int32")
    assert dataset_configuration.chunk_shape == (12, 3)
    assert dataset_configuration.buffer_shape == (12, 3)
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None

    if backend == "zarr":
        assert dataset_configuration.filter_methods is None
        assert dataset_configuration.filter_options is None

    dataset_configuration = next(
        dataset_configuration
        for dataset_configuration in dataset_configurations
        if dataset_configuration.location_in_file == "units/waveforms_index/data"
    )
    assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
    assert dataset_configuration.full_shape == (4,)
    assert dataset_configuration.dtype == np.dtype("uint8")
    assert dataset_configuration.chunk_shape == (4,)
    assert dataset_configuration.buffer_shape == (4,)
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None

    if backend == "zarr":
        assert dataset_configuration.filter_methods is None
        assert dataset_configuration.filter_options is None

    dataset_configuration = next(
        dataset_configuration
        for dataset_configuration in dataset_configurations
        if dataset_configuration.location_in_file == "units/waveforms_index_index/data"
    )
    assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
    assert dataset_configuration.full_shape == (2,)
    assert dataset_configuration.dtype == np.dtype("uint8")
    assert dataset_configuration.chunk_shape == (2,)
    assert dataset_configuration.buffer_shape == (2,)
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None

    if backend == "zarr":
        assert dataset_configuration.filter_methods is None
        assert dataset_configuration.filter_options is None


@pytest.mark.parametrize("iterator", [lambda x: x, SliceableDataChunkIterator, DataChunkIterator])
@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_compass_direction(iterator: callable, backend: Literal["hdf5", "zarr"]):
    array = np.array([[1, 2, 3], [4, 5, 6]])
    data = iterator(array)

    nwbfile = mock_NWBFile()
    spatial_series = mock_SpatialSeries(name="TestSpatialSeries", data=data)
    compass_direction = CompassDirection(name="TestCompassDirection", spatial_series=spatial_series)
    behavior_module = get_module(nwbfile=nwbfile, name="behavior")
    behavior_module.add(compass_direction)

    dataset_configurations = list(get_default_dataset_io_configurations(nwbfile=nwbfile, backend=backend))

    assert len(dataset_configurations) == 1

    dataset_configuration = dataset_configurations[0]
    assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
    assert dataset_configuration.object_id == spatial_series.object_id
    assert dataset_configuration.location_in_file == "processing/behavior/TestCompassDirection/TestSpatialSeries/data"
    assert dataset_configuration.full_shape == array.shape
    assert dataset_configuration.dtype == array.dtype
    assert dataset_configuration.chunk_shape == array.shape
    assert dataset_configuration.buffer_shape == array.shape
    assert dataset_configuration.compression_method == "gzip"
    assert dataset_configuration.compression_options is None

    if backend == "zarr":
        assert dataset_configuration.filter_methods is None
        assert dataset_configuration.filter_options is None


@pytest.mark.skipif(
    not is_package_installed(package_name="ndx_events"),
    reason="The extra testing package 'ndx-events' is not installed!",
)
@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_ndx_events(backend: Literal["hdf5", "zarr"]):
    from ndx_events import LabeledEvents

    # ndx_events data fields do not support wrapping in DataChunkIterators - data is nearly always small enough
    # to fit entirely in memory
    data = np.array([1, 2, 3], dtype="uint32")
    timestamps = np.array([4.5, 6.7, 8.9])

    nwbfile = mock_NWBFile()
    labeled_events = LabeledEvents(
        name="TestLabeledEvents",
        description="",
        timestamps=timestamps,
        data=data,
        labels=["response_left", "cue_onset", "cue_offset"],
    )
    behavior_module = get_module(nwbfile=nwbfile, name="behavior")
    behavior_module.add(labeled_events)

    dataset_configurations = list(get_default_dataset_io_configurations(nwbfile=nwbfile, backend=backend))

    # Note that the labels dataset is not caught since we search only for 'data' and 'timestamps' fields
    assert len(dataset_configurations) == 2

    data_dataset_configuration = next(
        dataset_configuration
        for dataset_configuration in dataset_configurations
        if dataset_configuration.dataset_name == "data"
    )
    assert isinstance(data_dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
    assert data_dataset_configuration.object_id == labeled_events.object_id
    assert data_dataset_configuration.location_in_file == "processing/behavior/TestLabeledEvents/data"
    assert data_dataset_configuration.full_shape == data.shape
    assert data_dataset_configuration.dtype == data.dtype
    assert data_dataset_configuration.chunk_shape == data.shape
    assert data_dataset_configuration.buffer_shape == data.shape
    assert data_dataset_configuration.compression_method == "gzip"
    assert data_dataset_configuration.compression_options is None

    if backend == "zarr":
        assert data_dataset_configuration.filter_methods is None
        assert data_dataset_configuration.filter_options is None

    timestamps_dataset_configuration = next(
        dataset_configuration
        for dataset_configuration in dataset_configurations
        if dataset_configuration.dataset_name == "timestamps"
    )
    assert isinstance(timestamps_dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
    assert timestamps_dataset_configuration.object_id == labeled_events.object_id
    assert timestamps_dataset_configuration.location_in_file == "processing/behavior/TestLabeledEvents/timestamps"
    assert timestamps_dataset_configuration.full_shape == timestamps.shape
    assert timestamps_dataset_configuration.dtype == timestamps.dtype
    assert timestamps_dataset_configuration.chunk_shape == timestamps.shape
    assert timestamps_dataset_configuration.buffer_shape == timestamps.shape
    assert timestamps_dataset_configuration.compression_method == "gzip"
    assert timestamps_dataset_configuration.compression_options is None

    if backend == "zarr":
        assert timestamps_dataset_configuration.filter_methods is None
        assert timestamps_dataset_configuration.filter_options is None
