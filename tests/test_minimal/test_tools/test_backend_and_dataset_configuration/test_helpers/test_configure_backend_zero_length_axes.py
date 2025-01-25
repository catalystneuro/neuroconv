"""
Reported in https://github.com/catalystneuro/neuroconv/issues/891, a failure occurred because of a zero-length axis.

These are specific tests for the additional skip condition that was added to the `get_default_dataset_io_configurations`
helper function which is called by `BackendConfiguration.from_nwbfile(...)`.
"""

from pathlib import Path
from typing import Literal, Tuple

import numcodecs
import numpy as np
import pytest
from hdmf.common import DynamicTable, VectorData
from numpy.testing import assert_array_equal
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import (
    BACKEND_NWB_IO,
    configure_backend,
    get_default_backend_configuration,
)


@pytest.fixture(scope="session")
def integer_array(
    seed: int = 0,
    dtype: np.dtype = np.dtype("int16"),
    shape: Tuple[int, int] = (12, 34),
):
    random_number_generator = np.random.default_rng(seed=seed)

    low = np.iinfo(dtype).min
    high = np.iinfo(dtype).max
    return random_number_generator.integers(low=low, high=high, size=shape, dtype=dtype)


@pytest.fixture(scope="session")
def integer_array_with_zero_length_axis(
    seed: int = 1,
    dtype: np.dtype = np.dtype("int16"),
    shape: Tuple[int, int] = (12, 0),  # 12 so it matches the dimension of the other column
):
    """Generate an array of integers with a zero-length axis."""
    assert 0 in shape, "The shape must contain a zero-length axis."

    random_number_generator = np.random.default_rng(seed=seed)

    low = np.iinfo(dtype).min
    high = np.iinfo(dtype).max
    return random_number_generator.integers(low=low, high=high, size=shape, dtype=dtype)


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_time_series_skip_zero_length_axis(
    tmpdir: Path,
    integer_array_with_zero_length_axis: np.ndarray,
    backend: Literal["hdf5", "zarr"],
):
    data = integer_array_with_zero_length_axis

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=data)
    nwbfile.add_acquisition(time_series)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)

    assert len(backend_configuration.dataset_configurations) == 0

    # dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestTimeSeries/data"]
    # configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)
    #
    # nwbfile_path = str(tmpdir / f"test_configure_defaults_{case_name}_time_series.nwb.{backend}")
    # with BACKEND_NWB_IO[backend](path=nwbfile_path, mode="w") as io:
    #     io.write(nwbfile)
    #
    # with BACKEND_NWB_IO[backend](path=nwbfile_path, mode="r") as io:
    #     written_nwbfile = io.read()
    #     written_data = written_nwbfile.acquisition["TestTimeSeries"].data
    #
    #     assert written_data.chunks == dataset_configuration.chunk_shape
    #
    #     if backend == "hdf5":
    #         assert written_data.compression == "gzip"
    #     elif backend == "zarr":
    #         assert written_data.compressor == numcodecs.GZip(level=1)
    #
    #     assert_array_equal(x=integer_array, y=written_data[:])


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_dynamic_table_skip_zero_length_axis(
    tmpdir: Path,
    integer_array: np.ndarray,
    integer_array_with_zero_length_axis: np.ndarray,
    backend: Literal["hdf5", "zarr"],
):
    nwbfile = mock_NWBFile()
    dynamic_table = DynamicTable(
        name="TestDynamicTable",
        description="",
        columns=[
            VectorData(name="TestColumn", description="", data=integer_array),
            VectorData(name="TestZeroLengthColumn", description="", data=integer_array_with_zero_length_axis),
        ],
    )
    nwbfile.add_acquisition(dynamic_table)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)

    assert "acquisition/TestDynamicTable/TestZeroLengthColumn/data" not in backend_configuration.dataset_configurations

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

        assert_array_equal(x=integer_array, y=written_data[:])
