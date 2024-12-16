"""Tests related to the equivalency feature of `configure_backend`."""

from pathlib import Path
from typing import Literal, Tuple

import numcodecs
import numpy as np
import pytest
from numpy.testing import assert_array_equal
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import (
    BACKEND_NWB_IO,
    configure_backend,
    get_default_backend_configuration,
    get_module,
)


def _generate_integer_array(
    seed: int,
    dtype: np.dtype = np.dtype("int16"),
    shape: Tuple[int, int] = (12, 5),
) -> np.ndarray:
    random_number_generator = np.random.default_rng(seed=seed)

    low = np.iinfo(dtype).min
    high = np.iinfo(dtype).max
    data = random_number_generator.integers(low=low, high=high, size=shape, dtype=dtype)

    return data


@pytest.fixture(scope="module")
def array_1(seed: int = 0) -> np.ndarray:
    integer_array = _generate_integer_array(seed=seed)

    return integer_array


@pytest.fixture(scope="module")
def array_2(seed: int = 1) -> np.ndarray:
    integer_array = _generate_integer_array(seed=seed)

    return integer_array


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configure_backend_equivalency(
    tmpdir: Path,
    array_1: np.ndarray,
    array_2: np.ndarray,
    backend: Literal["hdf5", "zarr"],
):
    nwbfile_1 = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=array_1)
    nwbfile_1.add_acquisition(time_series)

    nwbfile_2 = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=array_2)
    nwbfile_2.add_acquisition(time_series)

    backend_configuration_2 = get_default_backend_configuration(nwbfile=nwbfile_2, backend=backend)

    # assert False, f"{backend_configuration_2=}"

    dataset_configuration = backend_configuration_2.dataset_configurations["acquisition/TestTimeSeries/data"]
    dataset_configuration.compression_options = {"level": 2}
    configure_backend(nwbfile=nwbfile_1, backend_configuration=backend_configuration_2)

    nwbfile_path = str(tmpdir / f"test_configure_backend_equivalency.nwb")
    with BACKEND_NWB_IO[backend](path=nwbfile_path, mode="w") as io:
        io.write(nwbfile_1)

    with BACKEND_NWB_IO[backend](path=nwbfile_path, mode="r") as io:
        written_nwbfile = io.read()
        written_data = written_nwbfile.acquisition["TestTimeSeries"].data

        assert written_data.chunks == dataset_configuration.chunk_shape

        if backend == "hdf5":
            assert written_data.compression == "gzip"
            assert written_data.compression_opts == 2
        elif backend == "zarr":
            assert written_data.compressor == numcodecs.GZip(level=2)

        assert_array_equal(x=nwbfile_1.acquisition["TestTimeSeries"].data[:], y=written_data[:])


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configure_backend_nonequivalency_failure(
    array_1: np.ndarray,
    array_2: np.ndarray,
    backend: Literal["hdf5", "zarr"],
):
    nwbfile_1 = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=array_1)
    nwbfile_1.add_acquisition(time_series)

    # Same data as 'nwbfile_2' but different structure
    nwbfile_3 = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=array_2)
    processing_module = get_module(nwbfile=nwbfile_3, name="TestModule")
    processing_module.add(data_interfaces=[time_series])

    backend_configuration_3 = get_default_backend_configuration(nwbfile=nwbfile_3, backend=backend)

    with pytest.raises(KeyError) as exception_info:
        configure_backend(nwbfile=nwbfile_1, backend_configuration=backend_configuration_3)

    expected_message = (
        "\"Unable to remap the object IDs for object at location 'acquisition/TestTimeSeries/data'! "
        'This usually occurs if you are attempting to configure the backend for two files of non-equivalent structure."'
    )
    assert expected_message == str(exception_info.value)


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configure_backend_equivalency_empty_to_nonempty_failure(array_1: np.ndarray, backend: Literal["hdf5", "zarr"]):
    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=array_1)
    nwbfile.add_acquisition(time_series)

    empty_nwbfile = mock_NWBFile()

    empty_backend_configuration = get_default_backend_configuration(nwbfile=empty_nwbfile, backend=backend)

    with pytest.raises(ValueError) as exception_info:
        configure_backend(nwbfile=nwbfile, backend_configuration=empty_backend_configuration)

    expected_message = (
        "The number of default configurations (1) does not match the number of specified configurations (0)!"
    )
    assert expected_message == str(exception_info.value)


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configure_backend_equivalency_nonempty_to_empty_failure(array_1: np.ndarray, backend: Literal["hdf5", "zarr"]):
    nwbfile_1 = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=array_1)
    nwbfile_1.add_acquisition(time_series)

    empty_nwbfile = mock_NWBFile()

    nonempty_backend_configuration = get_default_backend_configuration(nwbfile=nwbfile_1, backend=backend)

    with pytest.raises(ValueError) as exception_info:
        configure_backend(nwbfile=empty_nwbfile, backend_configuration=nonempty_backend_configuration)

    expected_message = (
        "The number of default configurations (0) does not match the number of specified configurations (1)!"
    )
    assert expected_message == str(exception_info.value)
