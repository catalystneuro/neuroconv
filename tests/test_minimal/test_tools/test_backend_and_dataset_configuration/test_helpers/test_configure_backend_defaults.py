"""Unit tests for `get_default_dataset_configurations`."""
from pathlib import Path
from typing import Literal

import numcodecs
import numpy as np
import pytest
from hdmf.common import DynamicTable, VectorData
from hdmf.data_utils import DataChunkIterator
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
        ("classic", DataChunkIterator, dict(iter_axis=1, buffer_size=30_000 * 5)),
        # Need to hardcode buffer size in classic case or else it takes forever...
    ],
)
@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_simple_time_series(
    tmpdir: Path, case_name: str, iterator: callable, iterator_options: dict, backend: Literal["hdf5", "zarr"]
):
    array = np.zeros(shape=(30_000 * 5, 384), dtype="int16")
    data = iterator(array, **iterator_options)

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=data)
    nwbfile.add_acquisition(time_series)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestTimeSeries/data"]
    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    nwbfile_path = str(tmpdir / f"test_configure_defaults_{case_name}_time_series.nwb.{backend}")
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


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_simple_dynamic_table(tmpdir: Path, backend: Literal["hdf5", "zarr"]):
    data = np.zeros(shape=(30_000 * 5, 384), dtype="int16")

    nwbfile = mock_NWBFile()
    dynamic_table = DynamicTable(
        name="TestDynamicTable", description="", columns=[VectorData(name="TestColumn", description="", data=data)]
    )
    nwbfile.add_acquisition(dynamic_table)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestDynamicTable/TestColumn/data"]
    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    nwbfile_path = str(tmpdir / f"test_configure_defaults_dynamic_table.nwb.{backend}")
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
