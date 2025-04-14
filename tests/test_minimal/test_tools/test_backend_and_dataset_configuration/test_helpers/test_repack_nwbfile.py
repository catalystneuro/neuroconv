from pathlib import Path

import numpy as np
import pytest
from hdmf_zarr import NWBZarrIO, ZarrDataIO
from hdmf_zarr.nwb import NWBZarrIO
from numcodecs import Blosc, GZip
from pynwb import NWBHDF5IO, H5DataIO, NWBFile
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import (
    get_module,
    repack_nwbfile,
)


def generate_complex_nwbfile() -> NWBFile:
    nwbfile = mock_NWBFile()

    raw_array = np.array([[1, 2, 3], [4, 5, 6]])
    raw_time_series = mock_TimeSeries(name="RawTimeSeries", data=raw_array)
    nwbfile.add_acquisition(raw_time_series)

    number_of_trials = 10
    for start_time, stop_time in zip(
        np.linspace(start=0.0, stop=10.0, num=number_of_trials), np.linspace(start=1.0, stop=11.0, num=number_of_trials)
    ):
        nwbfile.add_trial(start_time=start_time, stop_time=stop_time)

    ecephys_module = get_module(nwbfile=nwbfile, name="ecephys")
    processed_array = np.array([[7.0, 8.0], [9.0, 10.0], [11.0, 12.0], [13.0, 14.0]])
    processed_time_series = mock_TimeSeries(name="ProcessedTimeSeries", data=processed_array)
    ecephys_module.add(processed_time_series)

    return nwbfile


@pytest.fixture(scope="session")
def hdf5_nwbfile_path(tmpdir_factory):
    nwbfile_path = tmpdir_factory.mktemp("data").join("test_repack_nwbfile.nwb.h5")
    if not Path(nwbfile_path).exists():
        nwbfile = generate_complex_nwbfile()

        # Add a H5DataIO-compressed time series
        raw_array = np.array([[11, 21, 31], [41, 51, 61]], dtype="int32")
        data = H5DataIO(data=raw_array, compression="gzip", compression_opts=2)
        raw_time_series = mock_TimeSeries(name="CompressedRawTimeSeries", data=data)
        nwbfile.add_acquisition(raw_time_series)

        # Add H5DataIO-compressed trials column
        number_of_trials = 10
        start_time = np.linspace(start=0.0, stop=10.0, num=number_of_trials)
        nwbfile.add_trial_column(
            name="compressed_start_time",
            description="start time of epoch",
            data=H5DataIO(data=start_time, compression="gzip", compression_opts=2),
        )

        with NWBHDF5IO(path=str(nwbfile_path), mode="w") as io:
            io.write(nwbfile)
    return str(nwbfile_path)


@pytest.fixture(scope="session")
def zarr_nwbfile_path(tmpdir_factory):
    compressor = Blosc(cname="lz4", clevel=5, shuffle=Blosc.SHUFFLE, blocksize=0)
    filter1 = Blosc(cname="zstd", clevel=1, shuffle=Blosc.SHUFFLE)
    filter2 = Blosc(cname="zstd", clevel=2, shuffle=Blosc.SHUFFLE)
    filters = [filter1, filter2]

    nwbfile_path = tmpdir_factory.mktemp("data").join("test_default_backend_configuration_hdf5_nwbfile.nwb.zarr")
    if not Path(nwbfile_path).exists():
        nwbfile = generate_complex_nwbfile()

        # Add a ZarrDataIO-compressed time series
        raw_array = np.array([[11, 21, 31], [41, 51, 61]], dtype="int32")
        data = ZarrDataIO(data=raw_array, chunks=(1, 3), compressor=compressor, filters=filters)
        raw_time_series = mock_TimeSeries(name="CompressedRawTimeSeries", data=data)
        nwbfile.add_acquisition(raw_time_series)

        # Add ZarrDataIO-compressed trials column
        number_of_trials = 10
        start_time = np.linspace(start=0.0, stop=10.0, num=number_of_trials)
        data = ZarrDataIO(data=start_time, chunks=(5,), compressor=compressor, filters=filters)
        nwbfile.add_trial_column(
            name="compressed_start_time",
            description="start time of epoch",
            data=data,
        )

        with NWBZarrIO(path=str(nwbfile_path), mode="w") as io:
            io.write(nwbfile)
    return str(nwbfile_path)


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
@pytest.mark.parametrize("use_default_backend_configuration", [True, False])
def test_repack_nwbfile(hdf5_nwbfile_path, zarr_nwbfile_path, backend, use_default_backend_configuration):
    compressor = Blosc(cname="lz4", clevel=5, shuffle=Blosc.SHUFFLE, blocksize=0)
    filter1 = Blosc(cname="zstd", clevel=1, shuffle=Blosc.SHUFFLE)
    filter2 = Blosc(cname="zstd", clevel=2, shuffle=Blosc.SHUFFLE)
    filters = [filter1, filter2]
    default_compressor = GZip(level=1)

    if backend == "hdf5":
        nwbfile_path = hdf5_nwbfile_path
        export_path = Path(hdf5_nwbfile_path).parent / "repacked_test_repack_nwbfile.nwb.h5"
    elif backend == "zarr":
        nwbfile_path = zarr_nwbfile_path
        export_path = Path(hdf5_nwbfile_path).parent / "repacked_test_repack_nwbfile.nwb.zarr"
    repack_nwbfile(
        nwbfile_path=str(nwbfile_path),
        export_nwbfile_path=str(export_path),
        backend=backend,
        use_default_backend_configuration=use_default_backend_configuration,
    )
    IO = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with IO(str(export_path), mode="r") as io:
        nwbfile = io.read()

        if backend == "hdf5":
            if use_default_backend_configuration:
                assert nwbfile.acquisition["RawTimeSeries"].data.compression_opts == 4
                assert nwbfile.intervals["trials"].start_time.data.compression_opts == 4
                assert nwbfile.processing["ecephys"]["ProcessedTimeSeries"].data.compression_opts == 4
                assert nwbfile.acquisition["CompressedRawTimeSeries"].data.compression_opts == 4
                assert nwbfile.intervals["trials"].compressed_start_time.data.compression_opts == 4
            else:
                assert nwbfile.acquisition["RawTimeSeries"].data.compression_opts is None
                assert nwbfile.intervals["trials"].start_time.data.compression_opts is None
                assert nwbfile.processing["ecephys"]["ProcessedTimeSeries"].data.compression_opts is None
                assert nwbfile.acquisition["CompressedRawTimeSeries"].data.compression_opts == 2
                assert nwbfile.intervals["trials"].compressed_start_time.data.compression_opts == 2
        elif backend == "zarr":
            if use_default_backend_configuration:
                assert nwbfile.acquisition["RawTimeSeries"].data.compressor == default_compressor
                assert nwbfile.acquisition["RawTimeSeries"].data.filters is None
                assert nwbfile.intervals["trials"].start_time.data.compressor == default_compressor
                assert nwbfile.intervals["trials"].start_time.data.filters is None
                assert nwbfile.processing["ecephys"]["ProcessedTimeSeries"].data.compressor == default_compressor
                assert nwbfile.processing["ecephys"]["ProcessedTimeSeries"].data.filters is None
                assert nwbfile.acquisition["CompressedRawTimeSeries"].data.compressor == default_compressor
                assert nwbfile.acquisition["CompressedRawTimeSeries"].data.filters is None
            else:
                assert nwbfile.acquisition["RawTimeSeries"].data.compressor == compressor
                assert nwbfile.acquisition["RawTimeSeries"].data.filters is None
                assert nwbfile.intervals["trials"].start_time.data.compressor == compressor
                assert nwbfile.intervals["trials"].start_time.data.filters is None
                assert nwbfile.processing["ecephys"]["ProcessedTimeSeries"].data.compressor == compressor
                assert nwbfile.processing["ecephys"]["ProcessedTimeSeries"].data.filters is None
                assert nwbfile.acquisition["CompressedRawTimeSeries"].data.compressor == compressor
                assert nwbfile.acquisition["CompressedRawTimeSeries"].data.filters == filters


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
@pytest.mark.parametrize("use_default_backend_configuration", [True, False])
def test_repack_nwbfile_with_changes(hdf5_nwbfile_path, zarr_nwbfile_path, backend, use_default_backend_configuration):
    compressor = Blosc(cname="lz4", clevel=5, shuffle=Blosc.SHUFFLE, blocksize=0)
    filter1 = Blosc(cname="zstd", clevel=1, shuffle=Blosc.SHUFFLE)
    filter2 = Blosc(cname="zstd", clevel=2, shuffle=Blosc.SHUFFLE)
    filters = [filter1, filter2]
    default_compressor = GZip(level=1)

    if backend == "hdf5":
        nwbfile_path = hdf5_nwbfile_path
        export_path = Path(hdf5_nwbfile_path).parent / "repacked_test_repack_nwbfile.nwb.h5"
        backend_configuration_changes = {
            "acquisition/RawTimeSeries/data": dict(
                compression_method="gzip", compression_options=dict(compression_opts=1)
            )
        }
    elif backend == "zarr":
        nwbfile_path = zarr_nwbfile_path
        export_path = Path(hdf5_nwbfile_path).parent / "repacked_test_repack_nwbfile.nwb.zarr"
        changed_compressor = Blosc(cname="lz4", clevel=3, shuffle=Blosc.SHUFFLE, blocksize=0)
        changed_filters = [Blosc(cname="zstd", clevel=3, shuffle=Blosc.SHUFFLE)]
        backend_configuration_changes = {
            "acquisition/RawTimeSeries/data": dict(
                compression_method=changed_compressor, filter_methods=changed_filters
            )
        }
    repack_nwbfile(
        nwbfile_path=str(nwbfile_path),
        export_nwbfile_path=str(export_path),
        backend=backend,
        use_default_backend_configuration=use_default_backend_configuration,
        backend_configuration_changes=backend_configuration_changes,
    )

    IO = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with IO(str(export_path), mode="r") as io:
        nwbfile = io.read()
        if backend == "hdf5":
            if use_default_backend_configuration:
                assert nwbfile.acquisition["RawTimeSeries"].data.compression_opts == 1
                assert nwbfile.intervals["trials"].start_time.data.compression_opts == 4
                assert nwbfile.processing["ecephys"]["ProcessedTimeSeries"].data.compression_opts == 4
                assert nwbfile.acquisition["CompressedRawTimeSeries"].data.compression_opts == 4
                assert nwbfile.intervals["trials"].compressed_start_time.data.compression_opts == 4
            else:
                assert nwbfile.acquisition["RawTimeSeries"].data.compression_opts == 1
                assert nwbfile.intervals["trials"].start_time.data.compression_opts is None
                assert nwbfile.processing["ecephys"]["ProcessedTimeSeries"].data.compression_opts is None
                assert nwbfile.acquisition["CompressedRawTimeSeries"].data.compression_opts == 2
                assert nwbfile.intervals["trials"].compressed_start_time.data.compression_opts == 2
        elif backend == "zarr":
            if use_default_backend_configuration:
                assert nwbfile.acquisition["RawTimeSeries"].data.compressor == changed_compressor
                assert nwbfile.acquisition["RawTimeSeries"].data.filters == changed_filters
                assert nwbfile.intervals["trials"].start_time.data.compressor == default_compressor
                assert nwbfile.intervals["trials"].start_time.data.filters is None
                assert nwbfile.processing["ecephys"]["ProcessedTimeSeries"].data.compressor == default_compressor
                assert nwbfile.processing["ecephys"]["ProcessedTimeSeries"].data.filters is None
                assert nwbfile.acquisition["CompressedRawTimeSeries"].data.compressor == default_compressor
                assert nwbfile.acquisition["CompressedRawTimeSeries"].data.filters is None
            else:
                assert nwbfile.acquisition["RawTimeSeries"].data.compressor == changed_compressor
                assert nwbfile.acquisition["RawTimeSeries"].data.filters == changed_filters
                assert nwbfile.intervals["trials"].start_time.data.compressor == compressor
                assert nwbfile.intervals["trials"].start_time.data.filters is None
                assert nwbfile.processing["ecephys"]["ProcessedTimeSeries"].data.compressor == compressor
                assert nwbfile.processing["ecephys"]["ProcessedTimeSeries"].data.filters is None
                assert nwbfile.acquisition["CompressedRawTimeSeries"].data.compressor == compressor
                assert nwbfile.acquisition["CompressedRawTimeSeries"].data.filters == filters


def test_repack_nwbfile_hdf5_to_zarr(hdf5_nwbfile_path: str, tmp_path: Path):
    """Test repackaging an NWB file from HDF5 to Zarr."""
    export_nwbfile_path = tmp_path / "repacked_hdf5_to_zarr.nwb.zarr"
    default_compressor = GZip(level=1)

    repack_nwbfile(
        nwbfile_path=Path(hdf5_nwbfile_path),
        export_nwbfile_path=export_nwbfile_path,
        backend="hdf5",
        export_backend="zarr",
        use_default_backend_configuration=True,
    )

    assert export_nwbfile_path.exists()

    # Read original HDF5
    with NWBHDF5IO(hdf5_nwbfile_path, mode="r") as io_hdf5:
        nwbfile_hdf5 = io_hdf5.read()
        # Read repacked Zarr
        with NWBZarrIO(str(export_nwbfile_path), mode="r") as io_zarr:
            nwbfile_zarr = io_zarr.read()

            # Compare key data
            np.testing.assert_array_equal(
                nwbfile_hdf5.acquisition["RawTimeSeries"].data[:], nwbfile_zarr.acquisition["RawTimeSeries"].data[:]
            )
            np.testing.assert_array_equal(
                nwbfile_hdf5.intervals["trials"]["start_time"][:], nwbfile_zarr.intervals["trials"]["start_time"][:]
            )
            np.testing.assert_array_equal(
                nwbfile_hdf5.processing["ecephys"]["ProcessedTimeSeries"].data[:],
                nwbfile_zarr.processing["ecephys"]["ProcessedTimeSeries"].data[:],
            )
            # Compare specifically compressed data
            np.testing.assert_array_equal(
                nwbfile_hdf5.acquisition["CompressedRawTimeSeries"].data[:],
                nwbfile_zarr.acquisition["CompressedRawTimeSeries"].data[:],
            )
            np.testing.assert_array_equal(
                nwbfile_hdf5.intervals["trials"]["compressed_start_time"][:],
                nwbfile_zarr.intervals["trials"]["compressed_start_time"][:],
            )

            # Check that compression is applied properly in zarr format
            assert nwbfile_zarr.acquisition["RawTimeSeries"].data.compressor == default_compressor
            assert nwbfile_zarr.acquisition["CompressedRawTimeSeries"].data.compressor == default_compressor
            assert nwbfile_zarr.intervals["trials"].start_time.data.compressor == default_compressor
            assert nwbfile_zarr.intervals["trials"].compressed_start_time.data.compressor == default_compressor
            assert nwbfile_zarr.processing["ecephys"]["ProcessedTimeSeries"].data.compressor == default_compressor


def test_repack_nwbfile_zarr_to_hdf5(zarr_nwbfile_path: str, tmp_path: Path):
    """Test repackaging an NWB file from Zarr to HDF5."""
    export_nwbfile_path = tmp_path / "repacked_zarr_to_hdf5.nwb.h5"

    repack_nwbfile(
        nwbfile_path=Path(zarr_nwbfile_path),
        export_nwbfile_path=export_nwbfile_path,
        backend="zarr",
        export_backend="hdf5",
        use_default_backend_configuration=True,
    )

    assert export_nwbfile_path.exists()

    # Read original Zarr
    with NWBZarrIO(zarr_nwbfile_path, mode="r") as io_zarr:
        nwbfile_zarr = io_zarr.read()
        # Read repacked HDF5
        with NWBHDF5IO(str(export_nwbfile_path), mode="r") as io_hdf5:
            nwbfile_hdf5 = io_hdf5.read()

            # Compare key data
            np.testing.assert_array_equal(
                nwbfile_zarr.acquisition["RawTimeSeries"].data[:], nwbfile_hdf5.acquisition["RawTimeSeries"].data[:]
            )
            np.testing.assert_array_equal(
                nwbfile_zarr.intervals["trials"]["start_time"][:], nwbfile_hdf5.intervals["trials"]["start_time"][:]
            )
            np.testing.assert_array_equal(
                nwbfile_zarr.processing["ecephys"]["ProcessedTimeSeries"].data[:],
                nwbfile_hdf5.processing["ecephys"]["ProcessedTimeSeries"].data[:],
            )
            # Compare specifically compressed data
            np.testing.assert_array_equal(
                nwbfile_zarr.acquisition["CompressedRawTimeSeries"].data[:],
                nwbfile_hdf5.acquisition["CompressedRawTimeSeries"].data[:],
            )
            np.testing.assert_array_equal(
                nwbfile_zarr.intervals["trials"]["compressed_start_time"][:],
                nwbfile_hdf5.intervals["trials"]["compressed_start_time"][:],
            )

            # Check that compression is applied properly in hdf5 format
            assert nwbfile_hdf5.acquisition["RawTimeSeries"].data.compression_opts == 4
            assert nwbfile_hdf5.acquisition["CompressedRawTimeSeries"].data.compression_opts == 4
            assert nwbfile_hdf5.intervals["trials"].start_time.data.compression_opts == 4
            assert nwbfile_hdf5.intervals["trials"].compressed_start_time.data.compression_opts == 4
            assert nwbfile_hdf5.processing["ecephys"]["ProcessedTimeSeries"].data.compression_opts == 4


def test_repack_nwbfile_invalid_configuration_error(hdf5_nwbfile_path, tmp_path):
    """Test that an error is raised when trying to change backend without using default config."""
    # Create a path for the output file with a different backend (HDF5 -> Zarr)
    export_path = tmp_path / "should_fail.nwb.zarr"

    # Attempt to repack with different export backend but not using default configuration
    with pytest.raises(
        ValueError, match="When 'export_backend' is different from 'backend', the default configuration must be used"
    ):
        repack_nwbfile(
            nwbfile_path=Path(hdf5_nwbfile_path),
            export_nwbfile_path=export_path,
            backend="hdf5",
            export_backend="zarr",
            use_default_backend_configuration=False,
        )

    # Verify the export file was not created
    assert not export_path.exists()
