"""Tests for global compression functionality in configure_and_write_nwbfile."""

import h5py
import numpy as np
import pytest
from pynwb import NWBHDF5IO
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import (
    AVAILABLE_HDF5_COMPRESSION_METHODS,
    AVAILABLE_ZARR_COMPRESSION_METHODS,
    configure_and_write_nwbfile,
    get_default_backend_configuration,
)


def get_hdf5_filter_info(dataset):
    """
    Get filter information from HDF5 dataset using low-level API of hdf5.

    For HDF5 plugins the high level attribute compression is empty so we need to look at the filter pipeline instead.

    This function retrieves the first (and only) filter from the HDF5 filter pipeline.
    All compression methods tested create exactly one filter in the HDF5 filter pipeline.

    See: https://api.h5py.org/h5p.html#h5py.h5p.PropDCID.get_filter for details on the filter pipeline.

    Parameters
    ----------
    dataset : h5py.Dataset
        The HDF5 dataset to inspect

    Returns
    -------
    tuple
        Filter information tuple from dcpl.get_filter(0) containing:
        - [0] filter_id (int): The HDF5 filter ID
        - [1] flags (int): Filter flags
        - [2] cd_values (tuple): Client data values/parameters
        - [3] name (bytes): Filter name as bytes

    Examples
    --------
    Filter info examples from actual compression methods:
    - gzip: (1, 1, (4,), b'deflate')
    - lzf: (32000, 1, (4, 261, 4000), b'lzf')
    - Blosc: (32001, 1, (2, 2, 4, 4000, 5, 1, 1), b'blosc')
    """
    # Get the dataset creation property list (DCPL)
    dcpl = dataset.id.get_create_plist()

    # All compression methods tested create exactly one filter, so we always get filter 0
    return dcpl.get_filter(0)


# Mapping of compression method names to their expected HDF5 filter IDs and descriptions
# See the gist https://gist.github.com/h-mayorquin/d6ea547f8061c9658011bb66edf9789d for details on how to generate
# this mapping.
HDF5_COMPRESSION_EXPECTED = {
    # Built-in HDF5 compression methods - these show up in both compression attribute and filter pipeline
    "gzip": {"compression_attribute": "gzip", "filter_id": 1, "filter_description": "deflate"},
    "lzf": {"compression_attribute": "lzf", "filter_id": 32000, "filter_description": "lzf"},
    "szip": {"compression_attribute": "szip", "filter_id": 4, "filter_description": "szip"},
    # Advanced compression methods from hdf5plugin - these only show up in filter pipeline
    "Bitshuffle": {
        "compression_attribute": None,
        "filter_id": 32008,
        "filter_description": "bitshuffle; see https://github.com/kiyo-masui/bitshuffle",
    },
    "Blosc": {"compression_attribute": None, "filter_id": 32001, "filter_description": "blosc"},
    "Blosc2": {"compression_attribute": None, "filter_id": 32026, "filter_description": "blosc2"},
    "BZip2": {"compression_attribute": None, "filter_id": 307, "filter_description": "bzip2"},
    "FciDecomp": {"compression_attribute": None, "filter_id": 32018, "filter_description": "HDF5 JPEG-LS filter"},
    "LZ4": {
        "compression_attribute": None,
        "filter_id": 32004,
        "filter_description": "HDF5 lz4 filter; see http://www.hdfgroup.org/services/contributions.html",
    },
    "Sperr": {"compression_attribute": None, "filter_id": 32028, "filter_description": "H5Z-SPERR"},
    "SZ": {
        "compression_attribute": None,
        "filter_id": 32017,
        "filter_description": "SZ compressor/decompressor for floating-point data.",
    },
    "SZ3": {
        "compression_attribute": None,
        "filter_id": 32024,
        "filter_description": "SZ3 compressor/decompressor for floating-point data.",
    },
    "Zfp": {"compression_attribute": None, "filter_id": 32013, "filter_description": "H5Z-ZFP-1.1.1 (ZFP-1.0.1)"},
    "Zstd": {
        "compression_attribute": None,
        "filter_id": 32015,
        "filter_description": "Zstandard compression: http://www.zstd.net",
    },
}

# Mapping of compression method names to their expected Zarr compressor class names
# None values indicate methods that don't work properly for various reasons
ZARR_COMPRESSION_EXPECTED = {
    "gzip": "gzip",
    "blosc": "blosc",
    "lzma": "lzma",
    "bz2": "bz2",
    "zlib": "zlib",
    "zstd": "zstd",
    "jenkins_lookup3": "jenkinslookup3",  # Note: the underscores removed in string representation
    "delta": None,  # TODO, implement a test for this, requires dtype parameter
    "categorize": None,  # TODO, implement a test for this, requires labels and dtype parameters
}


def create_test_nwbfile():
    """Create a test NWBFile with some data for testing compression."""
    nwbfile = mock_NWBFile()

    # Add multiple test datasets to ensure global compression is applied to all
    array1 = np.random.rand(100, 10).astype(np.float32)
    array2 = np.random.rand(50, 5).astype(np.float64)

    ts1 = mock_TimeSeries(name="TestTimeSeries1", data=array1)
    ts2 = mock_TimeSeries(name="TestTimeSeries2", data=array2)

    nwbfile.add_acquisition(ts1)
    nwbfile.add_acquisition(ts2)

    return nwbfile


# We need this so that pytest-xdist can run tests in parallel without issues
# Otherwise the order of the parameterized test is not deterministic and the
# Different runners fail to find the same tests
sorted_hdf5_compression_methods = sorted(AVAILABLE_HDF5_COMPRESSION_METHODS.keys())


class TestGlobalCompressionHDF5:
    """Test global compression functionality for HDF5 backend."""

    @pytest.mark.parametrize("compression_method", sorted_hdf5_compression_methods)
    def test_global_compression_method_only(self, tmp_path, compression_method):
        """Test applying only global compression method without options using backend configuration."""
        nwbfile = create_test_nwbfile()
        nwbfile_path = tmp_path / f"test_global_compression_{compression_method}.nwb"

        # Get default backend configuration and apply global compression
        backend_configuration = get_default_backend_configuration(nwbfile, backend="hdf5")
        backend_configuration.apply_global_compression(compression_method)

        configure_and_write_nwbfile(
            nwbfile=nwbfile,
            nwbfile_path=nwbfile_path,
            backend_configuration=backend_configuration,
        )

        assert nwbfile_path.exists()

        # Verify compression was applied by reading the file
        with NWBHDF5IO(str(nwbfile_path), mode="r") as io:
            read_nwbfile = io.read()
            assert "TestTimeSeries1" in read_nwbfile.acquisition
            assert "TestTimeSeries2" in read_nwbfile.acquisition

        # Check compression at HDF5 level for both datasets using proper filter pipeline inspection
        with h5py.File(str(nwbfile_path), "r") as f:
            dataset1 = f["acquisition/TestTimeSeries1/data"]
            dataset2 = f["acquisition/TestTimeSeries2/data"]

            expected = HDF5_COMPRESSION_EXPECTED.get(compression_method)
            if expected is not None:
                # Check compression attribute for built-in filters
                expected_compression_attr = expected["compression_attribute"]
                if expected_compression_attr is not None:
                    assert dataset1.compression == expected_compression_attr
                    assert dataset2.compression == expected_compression_attr

                # Check filter pipeline for all compression methods
                expected_filter_id = expected["filter_id"]
                expected_filter_description = expected["filter_description"]

                # Use our helper function to inspect the filter pipeline
                filter_info1 = get_hdf5_filter_info(dataset1)
                filter_info2 = get_hdf5_filter_info(dataset2)

                # Extract filter ID and description from the filter info tuple
                actual_filter_id1 = filter_info1[0]
                actual_filter_description1 = filter_info1[3].decode("utf-8")
                assert (
                    actual_filter_id1 == expected_filter_id
                ), f"Expected filter ID {expected_filter_id} but got {actual_filter_id1} for dataset1"
                assert (
                    actual_filter_description1 == expected_filter_description
                ), f"Expected filter description '{expected_filter_description}' but got '{actual_filter_description1}' for dataset1"

                actual_filter_id2 = filter_info2[0]
                actual_filter_description2 = filter_info2[3].decode("utf-8")
                assert (
                    actual_filter_id2 == expected_filter_id
                ), f"Expected filter ID {expected_filter_id} but got {actual_filter_id2} for dataset2"
                assert (
                    actual_filter_description2 == expected_filter_description
                ), f"Expected filter description '{expected_filter_description}' but got '{actual_filter_description2}' for dataset2"
            else:
                # For compression methods that don't work properly, we just verify the file was created
                # The compression may be None or fallback to a default method
                pass

    def test_global_compression_with_options(self, tmp_path):
        """Test applying global compression method with options using backend configuration."""
        nwbfile = create_test_nwbfile()
        nwbfile_path = tmp_path / "test_global_compression_options.nwb"

        # Get default backend configuration and apply global compression with options
        backend_configuration = get_default_backend_configuration(nwbfile, backend="hdf5")
        backend_configuration.apply_global_compression("gzip", {"level": 9})

        configure_and_write_nwbfile(
            nwbfile=nwbfile,
            nwbfile_path=nwbfile_path,
            backend_configuration=backend_configuration,
        )

        assert nwbfile_path.exists()

        # Verify compression was applied by reading the file
        with NWBHDF5IO(str(nwbfile_path), mode="r") as io:
            read_nwbfile = io.read()
            assert "TestTimeSeries1" in read_nwbfile.acquisition
            assert "TestTimeSeries2" in read_nwbfile.acquisition

        # Check compression at HDF5 level for both datasets
        with h5py.File(str(nwbfile_path), "r") as f:
            dataset1 = f["acquisition/TestTimeSeries1/data"]
            dataset2 = f["acquisition/TestTimeSeries2/data"]
            assert dataset1.compression == "gzip"
            assert dataset1.compression_opts == 9
            assert dataset2.compression == "gzip"
            assert dataset2.compression_opts == 9

    def test_global_compression_invalid_method(self):
        """Test that invalid compression method raises error when using apply_global_compression."""
        nwbfile = create_test_nwbfile()
        backend_configuration = get_default_backend_configuration(nwbfile, backend="hdf5")

        with pytest.raises(ValueError, match="Compression method 'invalid_method' is not available"):
            backend_configuration.apply_global_compression("invalid_method")


# We need this so that pytest-xdist can run tests in parallel without issues
# See the comment above in the hdf5 methods for details
sorted_zarr_compression_methods = sorted(AVAILABLE_ZARR_COMPRESSION_METHODS.keys())


class TestGlobalCompressionZarr:
    """Test global compression functionality for Zarr backend."""

    @pytest.mark.parametrize("compression_method", sorted_zarr_compression_methods)
    def test_global_compression_method_only(self, tmp_path, compression_method):
        """Test applying only global compression method without options using backend configuration."""
        nwbfile = create_test_nwbfile()
        nwbfile_path = tmp_path / f"test_global_compression_{compression_method}.zarr"

        expected_compression = ZARR_COMPRESSION_EXPECTED.get(compression_method, compression_method)

        if expected_compression is None:
            # Skip compression methods that require specific parameters
            pytest.skip(
                f"Compression method '{compression_method}' requires specific parameters and cannot be tested with default options"
            )

        # Get default backend configuration and apply global compression
        backend_configuration = get_default_backend_configuration(nwbfile, backend="zarr")
        backend_configuration.apply_global_compression(compression_method)

        configure_and_write_nwbfile(
            nwbfile=nwbfile,
            nwbfile_path=nwbfile_path,
            backend_configuration=backend_configuration,
        )

        assert nwbfile_path.exists()

        # Verify compression was applied by reading the file
        from hdmf_zarr import NWBZarrIO

        with NWBZarrIO(str(nwbfile_path), mode="r") as io:
            read_nwbfile = io.read()
            assert "TestTimeSeries1" in read_nwbfile.acquisition
            assert "TestTimeSeries2" in read_nwbfile.acquisition

        # Check compression at Zarr level for both datasets
        import zarr

        zarr_group = zarr.open(str(nwbfile_path), mode="r")
        dataset1 = zarr_group["acquisition/TestTimeSeries1/data"]
        dataset2 = zarr_group["acquisition/TestTimeSeries2/data"]

        # Verify that compression is applied
        assert dataset1.compressor is not None
        assert dataset2.compressor is not None
        # Check that the compressor name matches the expected compression method
        assert expected_compression in str(dataset1.compressor).lower()
        assert expected_compression in str(dataset2.compressor).lower()

    def test_global_compression_with_options(self, tmp_path):
        """Test applying global compression method with options using backend configuration."""
        nwbfile = create_test_nwbfile()
        nwbfile_path = tmp_path / "test_global_compression_options.zarr"

        # Get default backend configuration and apply global compression with options
        backend_configuration = get_default_backend_configuration(nwbfile, backend="zarr")
        backend_configuration.apply_global_compression("gzip", {"level": 6})

        configure_and_write_nwbfile(
            nwbfile=nwbfile,
            nwbfile_path=nwbfile_path,
            backend_configuration=backend_configuration,
        )

        assert nwbfile_path.exists()

        # Verify compression was applied by reading the file
        from hdmf_zarr import NWBZarrIO

        with NWBZarrIO(str(nwbfile_path), mode="r") as io:
            read_nwbfile = io.read()
            assert "TestTimeSeries1" in read_nwbfile.acquisition
            assert "TestTimeSeries2" in read_nwbfile.acquisition

        # Check compression at Zarr level for both datasets
        import zarr

        zarr_group = zarr.open(str(nwbfile_path), mode="r")
        dataset1 = zarr_group["acquisition/TestTimeSeries1/data"]
        dataset2 = zarr_group["acquisition/TestTimeSeries2/data"]

        # Verify that compression is applied
        assert dataset1.compressor is not None
        assert dataset2.compressor is not None
        # Check that the compressor name matches the expected compression method
        assert "gzip" in str(dataset1.compressor).lower()
        assert "gzip" in str(dataset2.compressor).lower()
        # Check that compression level is applied (for gzip compressor)
        if hasattr(dataset1.compressor, "level"):
            assert dataset1.compressor.level == 6
        if hasattr(dataset2.compressor, "level"):
            assert dataset2.compressor.level == 6

    def test_global_compression_invalid_method(self, tmp_path):
        """Test that invalid compression method raises error when using apply_global_compression."""
        nwbfile = create_test_nwbfile()
        backend_configuration = get_default_backend_configuration(nwbfile, backend="zarr")

        with pytest.raises(ValueError, match="Compression method 'invalid_method' is not available"):
            backend_configuration.apply_global_compression("invalid_method")
