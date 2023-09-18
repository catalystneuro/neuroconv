"""Unit tests for `get_default_dataset_configurations`."""
import numcodecs
import numpy as np
from hdmf.data_utils import DataChunkIterator
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import (
    configure_backend,
    get_default_backend_configuration,
)


def test_unwrapped_time_series_hdf5(tmpdir):
    array = np.zeros(shape=(30_000 * 5, 384), dtype="int16")

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=array)
    nwbfile.add_acquisition(time_series)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestTimeSeries/data"]
    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    nwbfile_path = tmpdir / "test_configure_backend_hdf5_defaults_unwrapped_data.nwb.h5"
    with NWBHDF5IO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        written_nwbfile = io.read()
        written_data = written_nwbfile.acquisition["TestTimeSeries"].data

        assert written_data.chunks == dataset_configuration.chunk_shape
        assert written_data.compression == "gzip"


def test_unwrapped_time_series_zarr(tmpdir):
    array = np.zeros(shape=(30_000 * 5, 384), dtype="int16")

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=array)
    nwbfile.add_acquisition(time_series)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="zarr")
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestTimeSeries/data"]
    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    nwbfile_path = tmpdir / "test_configure_backend_zarr_defaults_unwrapped_data.nwb.zarr"
    with NWBZarrIO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    with NWBZarrIO(path=nwbfile_path, mode="r") as io:
        written_nwbfile = io.read()
        written_data = written_nwbfile.acquisition["TestTimeSeries"].data

        assert written_data.chunks == dataset_configuration.chunk_shape
        assert written_data.compressor == numcodecs.GZip(level=4)


def test_generic_iterator_wrapped_time_series_hdf5(tmpdir):
    array = np.zeros(shape=(30_000 * 5, 384), dtype="int16")

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=SliceableDataChunkIterator(data=array))
    nwbfile.add_acquisition(time_series)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestTimeSeries/data"]
    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    nwbfile_path = tmpdir / "test_configure_backend_hdf5_defaults_generic_wrapped_data.nwb.h5"
    with NWBHDF5IO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        written_nwbfile = io.read()
        written_data = written_nwbfile.acquisition["TestTimeSeries"].data

        assert written_data.chunks == dataset_configuration.chunk_shape
        assert written_data.compression == "gzip"


def test_generic_iterator_wrapped_simple_time_series_zarr(tmpdir):
    array = np.zeros(shape=(30_000 * 5, 384), dtype="int16")

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=SliceableDataChunkIterator(data=array))
    nwbfile.add_acquisition(time_series)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="zarr")
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestTimeSeries/data"]

    smaller_buffer_shape = (30_000 * 1, 192)
    dataset_configuration.buffer_shape = smaller_buffer_shape

    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    # double .data to get past the DataIO to the iterator
    assert nwbfile.acquisition["TestTimeSeries"].data.data.buffer_shape == smaller_buffer_shape

    nwbfile_path = tmpdir / "test_configure_backend_iterator_buffer_generic_wrapped_data.nwb.zarr"
    with NWBZarrIO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    with NWBZarrIO(path=nwbfile_path, mode="r") as io:
        written_nwbfile = io.read()
        written_data = written_nwbfile.acquisition["TestTimeSeries"].data

        assert written_data.chunks == dataset_configuration.chunk_shape
        assert written_data.compression == "gzip"


def test_classic_iterator_wrapped_time_series_hdf5(tmpdir):
    array = np.zeros(shape=(30_000 * 5, 384), dtype="int16")

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=DataChunkIterator(data=array))
    nwbfile.add_acquisition(time_series)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestTimeSeries/data"]
    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    nwbfile_path = tmpdir / "test_configure_backend_hdf5_defaults_classic_wrapped_data.nwb.h5"
    with NWBHDF5IO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        written_nwbfile = io.read()
        written_data = written_nwbfile.acquisition["TestTimeSeries"].data

        assert written_data.chunks == dataset_configuration.chunk_shape
        assert written_data.compression == "gzip"


def test_classic_iterator_wrapped_simple_time_series_zarr(tmpdir):
    array = np.zeros(shape=(30_000 * 5, 384), dtype="int16")

    nwbfile = mock_NWBFile()
    time_series = mock_TimeSeries(name="TestTimeSeries", data=DataChunkIterator(data=array))
    nwbfile.add_acquisition(time_series)

    backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend="hdf5")
    dataset_configuration = backend_configuration.dataset_configurations["acquisition/TestTimeSeries/data"]
    configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

    nwbfile_path = tmpdir / "test_configure_backend_hdf5_defaults_classic_wrapped_data.nwb.zarr"
    with NWBZarrIO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    with NWBZarrIO(path=nwbfile_path, mode="r") as io:
        written_nwbfile = io.read()
        written_data = written_nwbfile.acquisition["TestTimeSeries"].data

        assert written_data.chunks == dataset_configuration.chunk_shape
        assert written_data.compression == "gzip"