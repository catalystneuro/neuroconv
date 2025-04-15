"""Unit tests for `get_default_dataset_io_configurations`."""

from typing import Literal

import numpy as np
import pytest
from hdmf.common import VectorData
from hdmf_zarr import ZarrDataIO
from hdmf_zarr.nwb import NWBZarrIO
from numcodecs import Blosc
from pynwb import NWBHDF5IO, H5DataIO
from pynwb.base import DynamicTable
from pynwb.behavior import CompassDirection
from pynwb.image import ImageSeries
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.behavior import mock_SpatialSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.importing import is_package_installed
from neuroconv.tools.nwb_helpers import (
    DATASET_IO_CONFIGURATIONS,
    get_existing_dataset_io_configurations,
    get_module,
)


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_time_series(tmp_path, backend: Literal["hdf5", "zarr"]):
    data = np.array([[1, 2, 3], [4, 5, 6]])

    nwbfile = mock_NWBFile()
    if backend == "zarr":  # ZarrDataIO compresses by default, so we disable it to test no-compression
        data = ZarrDataIO(data=data, compressor=False)
    time_series = mock_TimeSeries(name="TestTimeSeries", data=data)
    nwbfile.add_acquisition(time_series)

    data = np.array([[1, 2, 3], [4, 5, 6]])
    if backend == "hdf5":
        data = H5DataIO(data=data, compression="gzip", compression_opts=2, chunks=(1, 3))
    elif backend == "zarr":
        compressor = Blosc(cname="lz4", clevel=5, shuffle=Blosc.SHUFFLE, blocksize=0)
        filter1 = Blosc(cname="zstd", clevel=1, shuffle=Blosc.SHUFFLE)
        filter2 = Blosc(cname="zstd", clevel=2, shuffle=Blosc.SHUFFLE)
        filters = [filter1, filter2]
        data = ZarrDataIO(data=data, chunks=(1, 3), compressor=compressor, filters=filters)
    compressed_time_series = mock_TimeSeries(
        name="CompressedTimeSeries",
        data=data,
    )
    nwbfile.add_acquisition(compressed_time_series)

    nwbfile_path = tmp_path / "test_existing_dataset_io_configurations_timeseries.nwb"
    IO = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with IO(str(nwbfile_path), "w") as io:
        io.write(nwbfile)
    with IO(str(nwbfile_path), "r") as io:
        nwbfile = io.read()

        dataset_configurations = list(get_existing_dataset_io_configurations(nwbfile=nwbfile, backend=backend))

        assert len(dataset_configurations) == 2

        dataset_configuration = dataset_configurations[0]
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.object_id == time_series.object_id
        assert dataset_configuration.location_in_file == "acquisition/TestTimeSeries/data"
        assert dataset_configuration.full_shape == data.shape
        assert dataset_configuration.dtype == data.dtype
        assert dataset_configuration.buffer_shape == data.shape
        assert dataset_configuration.compression_method is None

        if backend == "hdf5":
            assert dataset_configuration.chunk_shape is None
            assert dataset_configuration.compression_options == dict(compression_opts=None)

        elif backend == "zarr":
            assert dataset_configuration.chunk_shape == (2, 3)
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods is None
            assert dataset_configuration.filter_options is None

        dataset_configuration = dataset_configurations[1]
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.object_id == compressed_time_series.object_id
        assert dataset_configuration.location_in_file == "acquisition/CompressedTimeSeries/data"
        assert dataset_configuration.full_shape == data.shape
        assert dataset_configuration.dtype == data.dtype
        assert dataset_configuration.chunk_shape == (1, 3)
        assert dataset_configuration.buffer_shape == data.shape

        if backend == "hdf5":
            assert dataset_configuration.compression_method == "gzip"
            assert dataset_configuration.compression_options["compression_opts"] == 2

        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods == filters
            assert dataset_configuration.filter_options is None


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_external_image_series(tmp_path, backend: Literal["hdf5", "zarr"]):
    nwbfile = mock_NWBFile()
    image_series = ImageSeries(name="TestImageSeries", format="external", external_file=[""], rate=1.0)
    nwbfile.add_acquisition(image_series)

    nwbfile_path = tmp_path / "test_existing_dataset_io_configurations_external_image_series.nwb"
    IO = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with IO(str(nwbfile_path), "w") as io:
        io.write(nwbfile)
    with IO(str(nwbfile_path), "r") as io:
        nwbfile = io.read()
        dataset_configurations = list(get_existing_dataset_io_configurations(nwbfile=nwbfile, backend=backend))
        assert len(dataset_configurations) == 0


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_dynamic_table(tmp_path, backend: Literal["hdf5", "zarr"]):
    data = np.array([0.1, 0.2, 0.3])

    nwbfile = mock_NWBFile()
    if backend == "zarr":  # ZarrDataIO compresses by default, so we disable it to test no-compression
        data = ZarrDataIO(data=data, compressor=False)
    column = VectorData(name="TestColumn", description="", data=data)

    data = np.array([0.1, 0.2, 0.3])
    if backend == "hdf5":
        data = H5DataIO(data=data, compression="gzip", compression_opts=2, chunks=(1,))
    elif backend == "zarr":
        compressor = Blosc(cname="lz4", clevel=5, shuffle=Blosc.SHUFFLE, blocksize=0)
        filter1 = Blosc(cname="zstd", clevel=1, shuffle=Blosc.SHUFFLE)
        filter2 = Blosc(cname="zstd", clevel=2, shuffle=Blosc.SHUFFLE)
        filters = [filter1, filter2]
        data = ZarrDataIO(data=data, chunks=(1,), compressor=compressor, filters=filters)
    compressed_column = VectorData(
        name="CompressedColumn",
        description="",
        data=data,
    )
    dynamic_table = DynamicTable(
        name="TestDynamicTable", description="", columns=[column, compressed_column], id=list(range(len(data)))
    )
    nwbfile.add_acquisition(dynamic_table)

    nwbfile_path = tmp_path / "test_existing_dataset_io_configurations_dynamic_table.nwb"
    IO = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with IO(str(nwbfile_path), "w") as io:
        io.write(nwbfile)
    with IO(str(nwbfile_path), "r") as io:
        nwbfile = io.read()

        dataset_configurations = list(get_existing_dataset_io_configurations(nwbfile=nwbfile, backend=backend))

        assert len(dataset_configurations) == 2

        dataset_configuration = dataset_configurations[0]
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.object_id == column.object_id
        assert dataset_configuration.location_in_file == "acquisition/TestDynamicTable/TestColumn/data"
        assert dataset_configuration.full_shape == data.shape
        assert dataset_configuration.dtype == data.dtype
        assert dataset_configuration.buffer_shape == data.shape
        assert dataset_configuration.compression_method is None

        if backend == "hdf5":
            assert dataset_configuration.chunk_shape is None
            assert dataset_configuration.compression_options == dict(compression_opts=None)
        elif backend == "zarr":
            assert dataset_configuration.chunk_shape == (3,)
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods is None
            assert dataset_configuration.filter_options is None

        dataset_configuration = dataset_configurations[1]
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.object_id == compressed_column.object_id
        assert dataset_configuration.location_in_file == "acquisition/TestDynamicTable/CompressedColumn/data"
        assert dataset_configuration.full_shape == data.shape
        assert dataset_configuration.dtype == data.dtype
        assert dataset_configuration.chunk_shape == (1,)
        assert dataset_configuration.buffer_shape == data.shape

        if backend == "hdf5":
            assert dataset_configuration.compression_method == "gzip"
            assert dataset_configuration.compression_options == dict(compression_opts=2)
        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods == filters
            assert dataset_configuration.filter_options is None


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_ragged_units_table(tmp_path, backend: Literal["hdf5", "zarr"]):
    nwbfile = mock_NWBFile()

    spike_times1 = np.array([0.0, 1.0, 2.0])
    waveforms1 = np.array(
        [[[1, 2, 3], [1, 2, 3], [1, 2, 3]], [[1, 2, 3], [1, 2, 3], [1, 2, 3]], [[1, 2, 3], [1, 2, 3], [1, 2, 3]]],
        dtype="int32",
    )
    nwbfile.add_unit(spike_times=spike_times1, waveforms=waveforms1)

    spike_times2 = np.array([3.0, 4.0])
    waveforms2 = np.array([[[4, 5, 6], [4, 5, 6], [4, 5, 6]], [[4, 5, 6], [4, 5, 6], [4, 5, 6]]], dtype="int32")
    nwbfile.add_unit(spike_times=spike_times2, waveforms=waveforms2)

    spike_times = np.concatenate([spike_times1, spike_times2])
    waveforms = np.concatenate([waveforms1, waveforms2], axis=0)
    index = [len(spike_times1), len(spike_times1) + len(spike_times2)]
    if backend == "hdf5":
        spike_times = H5DataIO(data=spike_times, compression="gzip", compression_opts=2, chunks=(2,))
        waveforms = H5DataIO(data=waveforms, compression="gzip", compression_opts=2, chunks=(1, 3, 3))
    elif backend == "zarr":
        compressor = Blosc(cname="lz4", clevel=5, shuffle=Blosc.SHUFFLE, blocksize=0)
        filter1 = Blosc(cname="zstd", clevel=1, shuffle=Blosc.SHUFFLE)
        filter2 = Blosc(cname="zstd", clevel=2, shuffle=Blosc.SHUFFLE)
        filters = [filter1, filter2]
        spike_times = ZarrDataIO(data=spike_times, chunks=(2,), compressor=compressor, filters=filters)
        waveforms = ZarrDataIO(data=waveforms, chunks=(1, 3, 3), compressor=compressor, filters=filters)
    nwbfile.add_unit_column(name="compressed_spike_times", description="", data=spike_times, index=index)
    nwbfile.add_unit_column(name="compressed_waveforms", description="", data=waveforms, index=index)

    nwbfile_path = tmp_path / "test_existing_dataset_io_configurations_ragged_units_table.nwb"
    IO = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with IO(str(nwbfile_path), "w") as io:
        io.write(nwbfile)
    with IO(str(nwbfile_path), "r") as io:
        nwbfile = io.read()
        dataset_configurations = list(get_existing_dataset_io_configurations(nwbfile=nwbfile, backend=backend))

        assert len(dataset_configurations) == 9

        dataset_configuration = next(
            dataset_configuration
            for dataset_configuration in dataset_configurations
            if dataset_configuration.location_in_file == "units/spike_times/data"
        )
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.full_shape == (5,)
        assert dataset_configuration.dtype == np.dtype("float64")
        assert dataset_configuration.buffer_shape == (5,)
        if backend == "hdf5":
            assert dataset_configuration.compression_method is None
            assert dataset_configuration.chunk_shape is None
            assert dataset_configuration.compression_options == dict(compression_opts=None)
        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.chunk_shape == (5,)
            assert dataset_configuration.compression_options is None
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
        assert dataset_configuration.buffer_shape == (2,)
        if backend == "hdf5":
            assert dataset_configuration.compression_method is None
            assert dataset_configuration.chunk_shape is None
            assert dataset_configuration.compression_options == dict(compression_opts=None)
        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.chunk_shape == (2,)
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods is None
            assert dataset_configuration.filter_options is None

        dataset_configuration = next(
            dataset_configuration
            for dataset_configuration in dataset_configurations
            if dataset_configuration.location_in_file == "units/waveforms/data"
        )
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.full_shape == (15, 3)
        assert dataset_configuration.dtype == np.dtype("int32")
        assert dataset_configuration.buffer_shape == (15, 3)
        if backend == "hdf5":
            assert dataset_configuration.compression_method is None
            assert dataset_configuration.chunk_shape is None
            assert dataset_configuration.compression_options == dict(compression_opts=None)
        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.chunk_shape == (15, 3)
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods is None
            assert dataset_configuration.filter_options is None

        dataset_configuration = next(
            dataset_configuration
            for dataset_configuration in dataset_configurations
            if dataset_configuration.location_in_file == "units/waveforms_index/data"
        )
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.full_shape == (5,)
        assert dataset_configuration.dtype == np.dtype("uint8")
        assert dataset_configuration.buffer_shape == (5,)
        if backend == "hdf5":
            assert dataset_configuration.compression_method is None
            assert dataset_configuration.chunk_shape is None
            assert dataset_configuration.compression_options == dict(compression_opts=None)
        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.chunk_shape == (5,)
            assert dataset_configuration.compression_options is None
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
        assert dataset_configuration.buffer_shape == (2,)
        if backend == "hdf5":
            assert dataset_configuration.compression_method is None
            assert dataset_configuration.chunk_shape is None
            assert dataset_configuration.compression_options == dict(compression_opts=None)
        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.chunk_shape == (2,)
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods is None
            assert dataset_configuration.filter_options is None

        dataset_configuration = next(
            dataset_configuration
            for dataset_configuration in dataset_configurations
            if dataset_configuration.location_in_file == "units/compressed_spike_times/data"
        )
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.full_shape == (5,)
        assert dataset_configuration.dtype == np.dtype("float64")
        assert dataset_configuration.buffer_shape == (5,)
        assert dataset_configuration.chunk_shape == (2,)
        if backend == "hdf5":
            assert dataset_configuration.compression_method == "gzip"
            assert dataset_configuration.compression_options == dict(compression_opts=2)
        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods == filters
            assert dataset_configuration.filter_options is None

        dataset_configuration = next(
            dataset_configuration
            for dataset_configuration in dataset_configurations
            if dataset_configuration.location_in_file == "units/compressed_spike_times_index/data"
        )
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.full_shape == (2,)
        assert dataset_configuration.dtype == np.dtype("uint8")
        assert dataset_configuration.buffer_shape == (2,)
        if backend == "hdf5":
            assert dataset_configuration.compression_method is None
            assert dataset_configuration.compression_options == dict(compression_opts=None)
            assert dataset_configuration.chunk_shape is None
        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods is None
            assert dataset_configuration.filter_options is None
            assert dataset_configuration.chunk_shape == (2,)

        dataset_configuration = next(
            dataset_configuration
            for dataset_configuration in dataset_configurations
            if dataset_configuration.location_in_file == "units/compressed_waveforms/data"
        )
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.full_shape == (5, 3, 3)
        assert dataset_configuration.dtype == np.dtype("int32")
        assert dataset_configuration.chunk_shape == (1, 3, 3)
        assert dataset_configuration.buffer_shape == (5, 3, 3)
        if backend == "hdf5":
            assert dataset_configuration.compression_method == "gzip"
            assert dataset_configuration.compression_options == dict(compression_opts=2)
        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods == filters
            assert dataset_configuration.filter_options is None

        dataset_configuration = next(
            dataset_configuration
            for dataset_configuration in dataset_configurations
            if dataset_configuration.location_in_file == "units/compressed_waveforms_index/data"
        )
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.full_shape == (2,)
        assert dataset_configuration.dtype == np.dtype("uint8")
        assert dataset_configuration.buffer_shape == (2,)
        if backend == "hdf5":
            assert dataset_configuration.compression_method is None
            assert dataset_configuration.compression_options == dict(compression_opts=None)
            assert dataset_configuration.chunk_shape is None
        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods is None
            assert dataset_configuration.filter_options is None
            assert dataset_configuration.chunk_shape == (2,)


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_compass_direction(tmp_path, backend: Literal["hdf5", "zarr"]):
    data = np.array([[1, 2, 3], [4, 5, 6]])

    nwbfile = mock_NWBFile()
    if backend == "zarr":  # ZarrDataIO compresses by default, so we disable it to test no-compression
        data = ZarrDataIO(data=data, compressor=False)
    spatial_series = mock_SpatialSeries(name="TestSpatialSeries", data=data)
    compass_direction = CompassDirection(name="TestCompassDirection", spatial_series=spatial_series)
    behavior_module = get_module(nwbfile=nwbfile, name="behavior")
    behavior_module.add(compass_direction)
    data = np.array([[1, 2, 3], [4, 5, 6]])
    if backend == "hdf5":
        data = H5DataIO(data=data, compression="gzip", compression_opts=2, chunks=(1, 3))
    elif backend == "zarr":
        filter1 = Blosc(cname="zstd", clevel=1, shuffle=Blosc.SHUFFLE)
        filter2 = Blosc(cname="zstd", clevel=2, shuffle=Blosc.SHUFFLE)
        filters = [filter1, filter2]
        compressor = Blosc(cname="lz4", clevel=5, shuffle=Blosc.SHUFFLE, blocksize=0)
        data = ZarrDataIO(data=data, chunks=(1, 3), compressor=compressor, filters=filters)
    compressed_spatial_series = mock_SpatialSeries(
        name="CompressedSpatialSeries",
        data=data,
    )
    compressed_compass_direction = CompassDirection(
        name="CompressedCompassDirection", spatial_series=compressed_spatial_series
    )
    behavior_module.add(compressed_compass_direction)
    nwbfile_path = tmp_path / "test_existing_dataset_io_configurations_compass_direction.nwb"
    IO = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with IO(str(nwbfile_path), "w") as io:
        io.write(nwbfile)

    with IO(str(nwbfile_path), "r") as io:
        nwbfile = io.read()
        dataset_configurations = list(get_existing_dataset_io_configurations(nwbfile=nwbfile, backend=backend))

        assert len(dataset_configurations) == 2

        dataset_configuration = dataset_configurations[0]
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.object_id == spatial_series.object_id
        assert (
            dataset_configuration.location_in_file == "processing/behavior/TestCompassDirection/TestSpatialSeries/data"
        )
        assert dataset_configuration.full_shape == data.shape
        assert dataset_configuration.dtype == data.dtype
        assert dataset_configuration.buffer_shape == data.shape
        assert dataset_configuration.compression_method is None
        if backend == "hdf5":
            assert dataset_configuration.compression_options == dict(compression_opts=None)
            assert dataset_configuration.chunk_shape is None
        elif backend == "zarr":
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.chunk_shape == data.shape
            assert dataset_configuration.filter_methods is None
            assert dataset_configuration.filter_options is None

        dataset_configuration = dataset_configurations[1]
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.object_id == compressed_spatial_series.object_id
        assert (
            dataset_configuration.location_in_file
            == "processing/behavior/CompressedCompassDirection/CompressedSpatialSeries/data"
        )
        assert dataset_configuration.full_shape == data.shape
        assert dataset_configuration.dtype == data.dtype
        assert dataset_configuration.chunk_shape == (1, 3)
        assert dataset_configuration.buffer_shape == data.shape
        if backend == "hdf5":
            assert dataset_configuration.compression_method == "gzip"
            assert dataset_configuration.compression_options == dict(compression_opts=2)
        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods == filters
            assert dataset_configuration.filter_options is None


@pytest.mark.skipif(
    not is_package_installed(package_name="ndx_events"),
    reason="The extra testing package 'ndx-events' is not installed!",
)
@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_ndx_events(tmp_path, backend: Literal["hdf5", "zarr"]):
    from ndx_events import LabeledEvents

    # ndx_events data fields do not support wrapping in DataChunkIterators - data is nearly always small enough
    # to fit entirely in memory
    data = np.array([1, 2, 3], dtype="uint32")
    timestamps = np.array([4.5, 6.7, 8.9])

    nwbfile = mock_NWBFile()
    if backend == "zarr":  # ZarrDataIO compresses by default, so we disable it to test no-compression
        data = ZarrDataIO(data=data, compressor=False)
        timestamps = ZarrDataIO(data=timestamps, compressor=False)
    labeled_events = LabeledEvents(
        name="TestLabeledEvents",
        description="",
        timestamps=timestamps,
        data=data,
        labels=["response_left", "cue_onset", "cue_offset"],
    )
    behavior_module = get_module(nwbfile=nwbfile, name="behavior")
    behavior_module.add(labeled_events)
    data = np.array([1, 2, 3], dtype="uint32")
    timestamps = np.array([4.5, 6.7, 8.9])
    if backend == "hdf5":
        data = H5DataIO(data=data, compression="gzip", compression_opts=2, chunks=(3,))
        timestamps = H5DataIO(data=timestamps, compression="gzip", compression_opts=2, chunks=(3,))
    elif backend == "zarr":
        compressor = Blosc(cname="lz4", clevel=5, shuffle=Blosc.SHUFFLE, blocksize=0)
        filter1 = Blosc(cname="zstd", clevel=1, shuffle=Blosc.SHUFFLE)
        filter2 = Blosc(cname="zstd", clevel=2, shuffle=Blosc.SHUFFLE)
        filters = [filter1, filter2]
        data = ZarrDataIO(data=data, chunks=(3,), compressor=compressor, filters=filters)
        timestamps = ZarrDataIO(data=timestamps, chunks=(3,), compressor=compressor, filters=filters)
    compressed_labeled_events = LabeledEvents(
        name="CompressedLabeledEvents",
        description="",
        timestamps=timestamps,
        data=data,
        labels=["response_left", "cue_onset", "cue_offset"],
    )
    behavior_module.add(compressed_labeled_events)
    nwbfile_path = tmp_path / "test_existing_dataset_io_configurations_ndx_events.nwb"
    IO = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with IO(str(nwbfile_path), "w") as io:
        io.write(nwbfile)

    with IO(str(nwbfile_path), "r") as io:
        nwbfile = io.read()

        dataset_configurations = list(get_existing_dataset_io_configurations(nwbfile=nwbfile, backend=backend))

        # Note that the labels dataset is not caught since we search only for 'data' and 'timestamps' fields
        assert len(dataset_configurations) == 4

        data_dataset_configuration = next(
            dataset_configuration
            for dataset_configuration in dataset_configurations
            if dataset_configuration.location_in_file == "processing/behavior/TestLabeledEvents/data"
        )
        assert isinstance(data_dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert data_dataset_configuration.object_id == labeled_events.object_id
        assert data_dataset_configuration.full_shape == data.shape
        assert data_dataset_configuration.dtype == data.dtype
        assert data_dataset_configuration.buffer_shape == data.shape
        assert data_dataset_configuration.compression_method is None
        if backend == "hdf5":
            assert data_dataset_configuration.compression_options == dict(compression_opts=None)
            assert data_dataset_configuration.chunk_shape is None
        elif backend == "zarr":
            assert data_dataset_configuration.compression_options is None
            assert data_dataset_configuration.chunk_shape == data.shape
            assert data_dataset_configuration.filter_methods is None
            assert data_dataset_configuration.filter_options is None

        timestamps_dataset_configuration = next(
            dataset_configuration
            for dataset_configuration in dataset_configurations
            if dataset_configuration.location_in_file == "processing/behavior/TestLabeledEvents/timestamps"
        )
        assert isinstance(timestamps_dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert timestamps_dataset_configuration.object_id == labeled_events.object_id
        assert timestamps_dataset_configuration.full_shape == timestamps.shape
        assert timestamps_dataset_configuration.dtype == timestamps.dtype
        assert timestamps_dataset_configuration.buffer_shape == timestamps.shape
        assert timestamps_dataset_configuration.compression_method is None
        if backend == "hdf5":
            assert timestamps_dataset_configuration.compression_options == dict(compression_opts=None)
            assert timestamps_dataset_configuration.chunk_shape is None
        elif backend == "zarr":
            assert timestamps_dataset_configuration.compression_options is None
            assert timestamps_dataset_configuration.chunk_shape == timestamps.shape
            assert timestamps_dataset_configuration.filter_methods is None
            assert timestamps_dataset_configuration.filter_options is None

        data_dataset_configuration = next(
            dataset_configuration
            for dataset_configuration in dataset_configurations
            if dataset_configuration.location_in_file == "processing/behavior/CompressedLabeledEvents/data"
        )
        assert isinstance(data_dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert data_dataset_configuration.object_id == compressed_labeled_events.object_id
        assert data_dataset_configuration.full_shape == data.shape
        assert data_dataset_configuration.dtype == data.dtype
        assert data_dataset_configuration.chunk_shape == (3,)
        assert data_dataset_configuration.buffer_shape == data.shape
        if backend == "hdf5":
            assert data_dataset_configuration.compression_method == "gzip"
            assert data_dataset_configuration.compression_options == dict(compression_opts=2)
        elif backend == "zarr":
            assert data_dataset_configuration.compression_method == compressor
            assert data_dataset_configuration.compression_options is None
            assert data_dataset_configuration.filter_methods == filters
            assert data_dataset_configuration.filter_options is None

        timestamps_dataset_configuration = next(
            dataset_configuration
            for dataset_configuration in dataset_configurations
            if dataset_configuration.location_in_file == "processing/behavior/CompressedLabeledEvents/timestamps"
        )
        assert isinstance(timestamps_dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert timestamps_dataset_configuration.object_id == compressed_labeled_events.object_id
        assert timestamps_dataset_configuration.full_shape == timestamps.shape
        assert timestamps_dataset_configuration.dtype == timestamps.dtype
        assert timestamps_dataset_configuration.chunk_shape == (3,)
        assert timestamps_dataset_configuration.buffer_shape == timestamps.shape
        if backend == "hdf5":
            assert timestamps_dataset_configuration.compression_method == "gzip"
            assert timestamps_dataset_configuration.compression_options == dict(compression_opts=2)
        elif backend == "zarr":
            assert timestamps_dataset_configuration.compression_method == compressor
            assert timestamps_dataset_configuration.compression_options is None
            assert timestamps_dataset_configuration.filter_methods == filters
            assert timestamps_dataset_configuration.filter_options is None


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configuration_on_time_series_automatic_backend(tmp_path, backend: Literal["hdf5", "zarr"]):
    data = np.array([[1, 2, 3], [4, 5, 6]])

    nwbfile = mock_NWBFile()
    if backend == "zarr":  # ZarrDataIO compresses by default, so we disable it to test no-compression
        data = ZarrDataIO(data=data, compressor=False)
    time_series = mock_TimeSeries(name="TestTimeSeries", data=data)
    nwbfile.add_acquisition(time_series)

    data = np.array([[1, 2, 3], [4, 5, 6]])
    if backend == "hdf5":
        data = H5DataIO(data=data, compression="gzip", compression_opts=2, chunks=(1, 3))
    elif backend == "zarr":
        compressor = Blosc(cname="lz4", clevel=5, shuffle=Blosc.SHUFFLE, blocksize=0)
        filter1 = Blosc(cname="zstd", clevel=1, shuffle=Blosc.SHUFFLE)
        filter2 = Blosc(cname="zstd", clevel=2, shuffle=Blosc.SHUFFLE)
        filters = [filter1, filter2]
        data = ZarrDataIO(data=data, chunks=(1, 3), compressor=compressor, filters=filters)
    compressed_time_series = mock_TimeSeries(
        name="CompressedTimeSeries",
        data=data,
    )
    nwbfile.add_acquisition(compressed_time_series)

    nwbfile_path = tmp_path / "test_existing_dataset_io_configurations_timeseries.nwb"
    IO = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with IO(str(nwbfile_path), "w") as io:
        io.write(nwbfile)
    with IO(str(nwbfile_path), "r") as io:
        nwbfile = io.read()

        dataset_configurations = list(get_existing_dataset_io_configurations(nwbfile=nwbfile))

        assert len(dataset_configurations) == 2

        dataset_configuration = dataset_configurations[0]
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.object_id == time_series.object_id
        assert dataset_configuration.location_in_file == "acquisition/TestTimeSeries/data"
        assert dataset_configuration.full_shape == data.shape
        assert dataset_configuration.dtype == data.dtype
        assert dataset_configuration.buffer_shape == data.shape
        assert dataset_configuration.compression_method is None

        if backend == "hdf5":
            assert dataset_configuration.chunk_shape is None
            assert dataset_configuration.compression_options == dict(compression_opts=None)

        elif backend == "zarr":
            assert dataset_configuration.chunk_shape == (2, 3)
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods is None
            assert dataset_configuration.filter_options is None

        dataset_configuration = dataset_configurations[1]
        assert isinstance(dataset_configuration, DATASET_IO_CONFIGURATIONS[backend])
        assert dataset_configuration.object_id == compressed_time_series.object_id
        assert dataset_configuration.location_in_file == "acquisition/CompressedTimeSeries/data"
        assert dataset_configuration.full_shape == data.shape
        assert dataset_configuration.dtype == data.dtype
        assert dataset_configuration.chunk_shape == (1, 3)
        assert dataset_configuration.buffer_shape == data.shape

        if backend == "hdf5":
            assert dataset_configuration.compression_method == "gzip"
            assert dataset_configuration.compression_options["compression_opts"] == 2

        elif backend == "zarr":
            assert dataset_configuration.compression_method == compressor
            assert dataset_configuration.compression_options is None
            assert dataset_configuration.filter_methods == filters
            assert dataset_configuration.filter_options is None
