"""Unit tests for `get_default_dataset_configurations`."""

from pathlib import Path
from typing import Literal, Tuple

import numcodecs
import numpy as np
import pytest
from hdmf.common import DynamicTable, VectorData
from hdmf.data_utils import DataChunkIterator
from numpy.testing import assert_array_equal
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import (
    BACKEND_NWB_IO,
    configure_backend,
    get_default_backend_configuration,
)


@pytest.fixture(scope="session")
def integer_array(
    seed: int = 0,
    dtype: np.dtype = np.dtype("int16"),
    shape: Tuple[int, int] = (30_000 * 5, 384),
):
    """
    Generate an array of integers.

    Default values are chosen to be similar to 5 seconds of v1 NeuroPixel data.
    """
    random_number_generator = np.random.default_rng(seed=seed)

    low = np.iinfo(dtype).min
    high = np.iinfo(dtype).max
    return random_number_generator.integers(low=low, high=high, size=shape, dtype=dtype)


@pytest.mark.parametrize(
    "case_name,iterator,iterator_options",
    [
        ("unwrapped", lambda x: x, dict()),
        ("generic", SliceableDataChunkIterator, dict()),
        ("classic", DataChunkIterator, dict(iter_axis=1, buffer_size=30_000 * 5)),
        # Need to hardcode buffer size in classic case or else it takes forever...
    ],
)
@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_simple_time_series(
    tmpdir: Path,
    integer_array: np.ndarray,
    case_name: str,
    iterator: callable,
    iterator_options: dict,
    backend: Literal["hdf5", "zarr"],
):
    data = iterator(integer_array, **iterator_options)

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=data)
    nwbfile.add_acquisition(time_series)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestTimeSeries/data"]
    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    nwbfile_path = str(tmpdir / f"test_configure_defaults_{case_name}_time_series.nwb")
    with BACKEND_NWB_IO[backend](path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    with BACKEND_NWB_IO[backend](path=nwbfile_path, mode="r") as io:
        written_nwbfile = io.read()
        written_data = written_nwbfile.acquisition["TestTimeSeries"].data

        assert written_data.chunks == dataset_configuration.chunk_shape

        if backend == "hdf5":
            assert written_data.compression == "gzip"
        elif backend == "zarr":
            assert written_data.compressor == numcodecs.GZip(level=1)

        assert_array_equal(integer_array, written_data[:])


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_simple_dynamic_table(tmpdir: Path, integer_array: np.ndarray, backend: Literal["hdf5", "zarr"]):
    nwbfile = mock_NWBFile()
    dynamic_table = DynamicTable(
        name="TestDynamicTable",
        description="",
        columns=[VectorData(name="TestColumn", description="", data=integer_array)],
    )
    nwbfile.add_acquisition(dynamic_table)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestDynamicTable/TestColumn/data"]
    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    nwbfile_path = str(tmpdir / f"test_configure_defaults_dynamic_table.nwb")
    NWB_IO = BACKEND_NWB_IO[backend]
    with NWB_IO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    with NWB_IO(path=nwbfile_path, mode="r") as io:
        written_nwbfile = io.read()
        written_data = written_nwbfile.acquisition["TestDynamicTable"]["TestColumn"].data

        assert written_data.chunks == dataset_configuration.chunk_shape

        if backend == "hdf5":
            assert written_data.compression == "gzip"
        elif backend == "zarr":
            assert written_data.compressor == numcodecs.GZip(level=1)

        assert_array_equal(integer_array, written_data[:])


@pytest.mark.parametrize(
    "case_name,iterator,data_iterator_options,timestamps_iterator_options",
    [
        ("unwrapped", lambda x: x, dict(), dict()),
        ("generic", SliceableDataChunkIterator, dict(), dict()),
        ("classic", DataChunkIterator, dict(iter_axis=1, buffer_size=30_000), dict(buffer_size=30_000)),
        # Need to hardcode buffer size in classic case or else it takes forever...
    ],
)
@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_time_series_timestamps_linkage(
    tmpdir: Path,
    integer_array: np.ndarray,
    case_name: str,
    iterator: callable,
    data_iterator_options: dict,
    timestamps_iterator_options: dict,
    backend: Literal["hdf5", "zarr"],
):
    data_1 = iterator(integer_array, **data_iterator_options)
    data_2 = iterator(integer_array, **data_iterator_options)

    timestamps_array = np.linspace(start=0.0, stop=1.0, num=integer_array.shape[0])
    timestamps = iterator(timestamps_array, **timestamps_iterator_options)

    nwbfile = mock_NWBFile()
    time_series_1 = mock_TimeSeries(name="TestTimeSeries1", data=data_1, timestamps=timestamps, rate=None)
    nwbfile.add_acquisition(time_series_1)

    time_series_2 = mock_TimeSeries(name="TestTimeSeries2", data=data_2, timestamps=time_series_1, rate=None)
    nwbfile.add_acquisition(time_series_2)

    # Note that the field will still show up in the configuration display
    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
    # print(backend_configuration)
    dataset_configuration_1 = backend_configuration.dataset_configurations["acquisition/TestTimeSeries1/data"]
    dataset_configuration_2 = backend_configuration.dataset_configurations["acquisition/TestTimeSeries2/data"]
    timestamps_configuration_1 = backend_configuration.dataset_configurations["acquisition/TestTimeSeries1/timestamps"]
    timestamps_configuration_1 = backend_configuration.dataset_configurations["acquisition/TestTimeSeries2/timestamps"]
    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    if case_name != "unwrapped":  # TODO: eventually, even this case will be buffered automatically
        assert nwbfile.acquisition["TestTimeSeries1"].data
        assert nwbfile.acquisition["TestTimeSeries2"].data
        assert nwbfile.acquisition["TestTimeSeries1"].timestamps
        assert nwbfile.acquisition["TestTimeSeries2"].timestamps

    nwbfile_path = str(tmpdir / f"test_time_series_timestamps_linkage_{case_name}_data.nwb")
    with BACKEND_NWB_IO[backend](path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    with BACKEND_NWB_IO[backend](path=nwbfile_path, mode="r") as io:
        written_nwbfile = io.read()

        written_data_1 = written_nwbfile.acquisition["TestTimeSeries1"].data
        assert written_data_1.chunks == dataset_configuration_1.chunk_shape
        if backend == "hdf5":
            assert written_data_1.compression == "gzip"
        elif backend == "zarr":
            assert written_data_1.compressor == numcodecs.GZip(level=1)
        assert_array_equal(integer_array, written_data_1[:])

        written_data_2 = written_nwbfile.acquisition["TestTimeSeries2"].data
        assert written_data_2.chunks == dataset_configuration_2.chunk_shape
        if backend == "hdf5":
            assert written_data_2.compression == "gzip"
        elif backend == "zarr":
            assert written_data_2.compressor == numcodecs.GZip(level=1)
        assert_array_equal(integer_array, written_data_2[:])

        written_timestamps_1 = written_nwbfile.acquisition["TestTimeSeries1"].timestamps
        assert written_timestamps_1.chunks == timestamps_configuration_1.chunk_shape
        if backend == "hdf5":
            assert written_timestamps_1.compression == "gzip"
        elif backend == "zarr":
            assert written_timestamps_1.compressor == numcodecs.GZip(level=1)
        assert_array_equal(timestamps_array, written_timestamps_1[:])

        written_timestamps_2 = written_nwbfile.acquisition["TestTimeSeries2"].timestamps
        assert written_timestamps_2 == written_timestamps_1
