"""
Reported in https://github.com/catalystneuro/neuroconv/issues/1909, datasets added to a file after
``nwbfile.objects`` had been read were written with no compression and no chunking.

``nwbfile.objects`` is built on its first read and never invalidated, and interfaces read it in the middle
of a write to inspect what the file already holds. The only variable in each test below is whether anything
read it before the second dataset was added.
"""

from typing import Literal

import h5py
import numpy as np
import pytest
from hdmf.data_utils import DataIO
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import (
    configure_and_write_nwbfile,
    configure_backend,
    get_default_backend_configuration,
    get_default_dataset_io_configurations,
)


@pytest.fixture
def nwbfile_with_a_dataset_added_after_the_cache_was_read():
    """An NWBFile holding two time series, whose ``objects`` was read between the two additions."""
    nwbfile = mock_NWBFile()
    nwbfile.add_acquisition(mock_TimeSeries(name="Early", data=np.arange(1000, dtype="float64")))

    nwbfile.objects  # what a mid-write inspection inside an interface does

    nwbfile.add_acquisition(mock_TimeSeries(name="Late", data=np.arange(1000, dtype="float64")))
    return nwbfile


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_default_dataset_io_configurations_include_the_late_dataset(
    nwbfile_with_a_dataset_added_after_the_cache_was_read, backend: Literal["hdf5", "zarr"]
):
    dataset_io_configurations = get_default_dataset_io_configurations(
        nwbfile=nwbfile_with_a_dataset_added_after_the_cache_was_read, backend=backend
    )
    locations_in_file = {configuration.location_in_file for configuration in dataset_io_configurations}

    assert locations_in_file == {"acquisition/Early/data", "acquisition/Late/data"}


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configure_backend_wraps_the_late_dataset(
    nwbfile_with_a_dataset_added_after_the_cache_was_read, backend: Literal["hdf5", "zarr"]
):
    nwbfile = nwbfile_with_a_dataset_added_after_the_cache_was_read
    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    assert isinstance(nwbfile.acquisition["Early"].data, DataIO)
    assert isinstance(nwbfile.acquisition["Late"].data, DataIO)


def test_written_file_compresses_the_late_dataset(nwbfile_with_a_dataset_added_after_the_cache_was_read, tmp_path):
    nwbfile_path = tmp_path / "test_written_file_compresses_the_late_dataset.nwb"
    configure_and_write_nwbfile(
        nwbfile=nwbfile_with_a_dataset_added_after_the_cache_was_read, nwbfile_path=nwbfile_path, backend="hdf5"
    )

    with h5py.File(name=nwbfile_path, mode="r") as file:
        assert file["acquisition/Early/data"].compression == "gzip"
        assert file["acquisition/Late/data"].compression == "gzip"


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configure_backend_raises_when_a_dataset_was_added_after_the_configuration(backend: Literal["hdf5", "zarr"]):
    """A configuration no longer describes the file once another dataset has been added to it."""
    nwbfile = mock_NWBFile()
    nwbfile.add_acquisition(mock_TimeSeries(name="Early", data=np.arange(1000, dtype="float64")))
    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)

    nwbfile.add_acquisition(mock_TimeSeries(name="Late", data=np.arange(1000, dtype="float64")))

    with pytest.raises(ValueError, match="does not match the number of specified configurations"):
        configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)
