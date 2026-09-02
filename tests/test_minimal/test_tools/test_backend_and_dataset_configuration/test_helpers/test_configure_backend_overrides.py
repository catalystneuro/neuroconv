"""Unit tests for `get_default_dataset_configurations`."""

from pathlib import Path
from typing import Literal

import numcodecs
import numpy as np
import pytest
from hdmf.common import DynamicTable, VectorData
from hdmf.data_utils import DataChunkIterator
from pynwb import read_nwb
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import (
    BACKEND_NWB_IO,
    configure_backend,
    get_default_backend_configuration,
)


@pytest.mark.parametrize(
    "case_name,iterator,iterator_options",
    [
        ("unwrapped", lambda x: x, dict()),
        ("generic", SliceableDataChunkIterator, dict()),
        ("classic", DataChunkIterator, dict(iter_axis=1, buffer_size=3_000)),
        # Need to hardcode buffer size in classic case or else it takes forever...
    ],
)
@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_simple_time_series_override(
    tmpdir: Path, case_name: str, iterator: callable, iterator_options: dict, backend: Literal["hdf5", "zarr"]
):
    array = np.zeros(shape=(3_000, 16), dtype="int16")
    data = iterator(array, **iterator_options)

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=data)
    nwbfile.add_acquisition(time_series)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestTimeSeries/data"]

    smaller_chunk_shape = (600, 4)
    smaller_buffer_shape = (1_200, 8)
    dataset_configuration.chunk_shape = smaller_chunk_shape
    dataset_configuration.buffer_shape = smaller_buffer_shape

    higher_gzip_level = 5
    if backend == "hdf5":
        dataset_configuration.compressor_options = [dict(level=higher_gzip_level)]
    elif backend == "zarr":
        dataset_configuration.compressor_options = [dict(level=higher_gzip_level)]

    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    if case_name != "unwrapped":  # TODO: eventually, even this case will be buffered automatically
        assert nwbfile.acquisition["TestTimeSeries"].data

    nwbfile_path = str(tmpdir / f"test_configure_defaults_{case_name}_data.nwb")
    with BACKEND_NWB_IO[backend](path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    written_nwbfile = read_nwb(nwbfile_path)
    written_data = written_nwbfile.acquisition["TestTimeSeries"].data

    assert written_data.chunks == smaller_chunk_shape

    if backend == "hdf5":
        assert written_data.compression == "gzip"
        assert written_data.compression_opts == higher_gzip_level
    elif backend == "zarr":
        assert written_data.compressor == numcodecs.GZip(level=5)
    written_nwbfile.read_io.close()


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_simple_dynamic_table_override(tmpdir: Path, backend: Literal["hdf5", "zarr"]):
    data = np.zeros(shape=(3_000, 16), dtype="int16")

    nwbfile = mock_NWBFile()
    dynamic_table = DynamicTable(
        name="TestDynamicTable", description="", columns=[VectorData(name="TestColumn", description="", data=data)]
    )
    nwbfile.add_acquisition(dynamic_table)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestDynamicTable/TestColumn/data"]

    smaller_chunk_shape = (600, 4)
    dataset_configuration.chunk_shape = smaller_chunk_shape

    higher_gzip_level = 5
    if backend == "hdf5":
        dataset_configuration.compressor_options = [dict(level=higher_gzip_level)]
    elif backend == "zarr":
        dataset_configuration.compressor_options = [dict(level=higher_gzip_level)]

    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    nwbfile_path = str(tmpdir / f"test_configure_defaults_dynamic_table.nwb")
    NWB_IO = BACKEND_NWB_IO[backend]
    with NWB_IO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    written_nwbfile = read_nwb(nwbfile_path)
    written_data = written_nwbfile.acquisition["TestDynamicTable"]["TestColumn"].data

    assert written_data.chunks == smaller_chunk_shape

    if backend == "hdf5":
        assert written_data.compression == "gzip"
        assert written_data.compression_opts == higher_gzip_level
    elif backend == "zarr":
        assert written_data.compressor == numcodecs.GZip(level=5)
    written_nwbfile.read_io.close()


def written_filters_and_compressors(array) -> tuple[list, list]:
    """
    Read a written Zarr array's codec chain in the terms zarr 3 uses.

    `Array.compressors` is a zarr 3 property that reports the bytes-to-bytes run for a v2 and a v3 array
    alike, while `Array.compressor` is the v2-only spelling it deprecates. Reading through it here keeps
    these assertions phrased in the vocabulary the model speaks, and the fallback can go when hdmf-zarr
    moves off `zarr<3.0`.
    """
    filters = list(array.filters or ())
    if hasattr(array, "compressors"):
        return filters, list(array.compressors)
    return filters, [] if array.compressor is None else [array.compressor]


def test_shuffle_is_correctly_propagated_as_filter_in_zarr(tmpdir: Path):
    """Zarr v2 has one compressor slot, so a shuffle named beside a compression method is written as a filter."""
    array = np.zeros(shape=(3_000, 16), dtype="int16")

    nwbfile = mock_NWBFile()
    nwbfile.add_acquisition(mock_TimeSeries(name="TestTimeSeries", data=array))

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="zarr")
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestTimeSeries/data"]
    dataset_configuration.compressors = ["shuffle", "gzip"]

    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    nwbfile_path = str(tmpdir / "test_configure_overrides_shuffle_with_compression.nwb")
    with BACKEND_NWB_IO["zarr"](path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    written_nwbfile = read_nwb(nwbfile_path)
    written_data = written_nwbfile.acquisition["TestTimeSeries"].data

    filters, compressors = written_filters_and_compressors(written_data)
    assert filters == [numcodecs.Shuffle(elementsize=2)]
    assert compressors == [numcodecs.GZip(level=1)]
    written_nwbfile.read_io.close()
