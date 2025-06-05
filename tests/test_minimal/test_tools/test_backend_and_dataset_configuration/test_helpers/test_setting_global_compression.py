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


class TestGlobalCompressionHDF5:
    """Test global compression functionality for HDF5 backend."""

    @pytest.mark.parametrize("compression_method", list(AVAILABLE_HDF5_COMPRESSION_METHODS.keys()))
    def test_global_compression_method_only(self, tmp_path, compression_method):
        """Test applying only global compression method without options."""
        nwbfile = create_test_nwbfile()
        nwbfile_path = tmp_path / f"test_global_compression_{compression_method}.nwb"

        configure_and_write_nwbfile(
            nwbfile=nwbfile,
            nwbfile_path=nwbfile_path,
            backend="hdf5",
            global_compression_method=compression_method,
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
        """Test applying global compression method with options."""
        nwbfile = create_test_nwbfile()
        nwbfile_path = tmp_path / "test_global_compression_options.nwb"

        configure_and_write_nwbfile(
            nwbfile=nwbfile,
            nwbfile_path=nwbfile_path,
            backend="hdf5",
            global_compression_method="gzip",
            global_compression_options={"level": 9},
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

    def test_global_compression_invalid_method(self, tmp_path):
        """Test that invalid compression method raises error."""
        nwbfile = create_test_nwbfile()
        nwbfile_path = tmp_path / "test_invalid_compression.nwb"

        with pytest.raises(ValueError, match="Compression method 'invalid_method' is not available"):
            configure_and_write_nwbfile(
                nwbfile=nwbfile,
                nwbfile_path=nwbfile_path,
                backend="hdf5",
                global_compression_method="invalid_method",
            )

    def test_global_compression_with_backend_configuration_raises_error(self, tmp_path):
        """Test that using global compression with backend_configuration raises error."""
        nwbfile = create_test_nwbfile()
        backend_configuration = get_default_backend_configuration(nwbfile, backend="hdf5")
        nwbfile_path = tmp_path / "test_error.nwb"

        with pytest.raises(ValueError, match="Global compression parameters cannot be used"):
            configure_and_write_nwbfile(
                nwbfile=nwbfile,
                nwbfile_path=nwbfile_path,
                backend_configuration=backend_configuration,
                global_compression_method="gzip",
            )

    def test_global_compression_options_without_method_raises_error(self, tmp_path):
        """Test that providing global compression options without method raises error."""
        nwbfile = create_test_nwbfile()
        backend_configuration = get_default_backend_configuration(nwbfile, backend="hdf5")
        nwbfile_path = tmp_path / "test_error.nwb"

        with pytest.raises(ValueError, match="Global compression parameters cannot be used"):
            configure_and_write_nwbfile(
                nwbfile=nwbfile,
                nwbfile_path=nwbfile_path,
                backend_configuration=backend_configuration,
                global_compression_options={"level": 5},
            )

    def test_global_compression_preserves_disabled_compression(self):
        """Test that datasets with compression disabled remain disabled."""
        nwbfile = create_test_nwbfile()
        backend_configuration = get_default_backend_configuration(nwbfile, backend="hdf5")

        # Disable compression for one dataset
        dataset_configs = list(backend_configuration.dataset_configurations.values())
        if dataset_configs:
            dataset_configs[0].compression_method = None
            original_compression_method = dataset_configs[0].compression_method

        # Apply global compression using the internal function
        from neuroconv.tools.nwb_helpers._metadata_and_file_helpers import (
            _apply_global_compression,
        )

        _apply_global_compression(
            backend_configuration=backend_configuration,
            global_compression_method="lzf",
            global_compression_options=None,
        )

        # Check that the disabled dataset remains disabled
        if dataset_configs:
            assert dataset_configs[0].compression_method == original_compression_method  # Should still be None

    def test_available_hdf5_compression_methods(self):
        """Test that available HDF5 compression methods are accessible."""
        assert "gzip" in AVAILABLE_HDF5_COMPRESSION_METHODS
        assert "lzf" in AVAILABLE_HDF5_COMPRESSION_METHODS


class TestGlobalCompressionZarr:
    """Test global compression functionality for Zarr backend."""

    @pytest.mark.parametrize("compression_method", list(AVAILABLE_ZARR_COMPRESSION_METHODS.keys()))
    def test_global_compression_method_only(self, tmp_path, compression_method):
        """Test applying only global compression method without options."""
        nwbfile = create_test_nwbfile()
        nwbfile_path = tmp_path / f"test_global_compression_{compression_method}.zarr"

        expected_compression = ZARR_COMPRESSION_EXPECTED.get(compression_method, compression_method)

        if expected_compression is None:
            # Skip compression methods that require specific parameters
            pytest.skip(
                f"Compression method '{compression_method}' requires specific parameters and cannot be tested with default options"
            )

        configure_and_write_nwbfile(
            nwbfile=nwbfile,
            nwbfile_path=nwbfile_path,
            backend="zarr",
            global_compression_method=compression_method,
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
        """Test applying global compression method with options."""
        nwbfile = create_test_nwbfile()
        nwbfile_path = tmp_path / "test_global_compression_options.zarr"

        configure_and_write_nwbfile(
            nwbfile=nwbfile,
            nwbfile_path=nwbfile_path,
            backend="zarr",
            global_compression_method="gzip",
            global_compression_options={"level": 6},
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
        """Test that invalid compression method raises error."""
        nwbfile = create_test_nwbfile()
        nwbfile_path = tmp_path / "test_invalid_compression.zarr"

        with pytest.raises(ValueError, match="Compression method 'invalid_method' is not available"):
            configure_and_write_nwbfile(
                nwbfile=nwbfile,
                nwbfile_path=nwbfile_path,
                backend="zarr",
                global_compression_method="invalid_method",
            )

    def test_available_zarr_compression_methods(self):
        """Test that available Zarr compression methods are accessible."""
        assert "gzip" in AVAILABLE_ZARR_COMPRESSION_METHODS
        assert "blosc" in AVAILABLE_ZARR_COMPRESSION_METHODS


class TestGlobalCompressionEdgeCases:
    """Test edge cases for global compression functionality."""

    def test_empty_nwbfile_with_global_compression(self, tmp_path):
        """Test global compression with an NWBFile that has no datasets."""
        nwbfile = mock_NWBFile()  # Empty NWBFile
        nwbfile_path = tmp_path / "test_empty.nwb"

        # Should not raise an error even with no datasets
        configure_and_write_nwbfile(
            nwbfile=nwbfile,
            nwbfile_path=nwbfile_path,
            backend="hdf5",
            global_compression_method="gzip",
        )

        assert nwbfile_path.exists()

    def test_global_compression_options_without_method_should_error(self, tmp_path):
        """Test that providing compression options without compression method should raise an error."""
        nwbfile = create_test_nwbfile()
        nwbfile_path = tmp_path / "test_options_only.nwb"

        # This should raise an error - compression options without compression method
        with pytest.raises(ValueError, match="Global compression options provided without global compression method"):
            configure_and_write_nwbfile(
                nwbfile=nwbfile,
                nwbfile_path=nwbfile_path,
                backend="hdf5",
                global_compression_options={"level": 5},
            )

    def test_backend_configuration_validation(self, tmp_path):
        """Test validation when both backend_configuration and global compression are provided."""
        nwbfile = create_test_nwbfile()
        backend_configuration = get_default_backend_configuration(nwbfile, backend="hdf5")
        nwbfile_path = tmp_path / "test_validation.nwb"

        # Test with global_compression_method
        with pytest.raises(ValueError, match="Global compression parameters cannot be used"):
            configure_and_write_nwbfile(
                nwbfile=nwbfile,
                nwbfile_path=nwbfile_path,
                backend_configuration=backend_configuration,
                global_compression_method="gzip",
            )

        # Test with global_compression_options
        with pytest.raises(ValueError, match="Global compression parameters cannot be used"):
            configure_and_write_nwbfile(
                nwbfile=nwbfile,
                nwbfile_path=nwbfile_path,
                backend_configuration=backend_configuration,
                global_compression_options={"level": 5},
            )

        # Test with both
        with pytest.raises(ValueError, match="Global compression parameters cannot be used"):
            configure_and_write_nwbfile(
                nwbfile=nwbfile,
                nwbfile_path=nwbfile_path,
                backend_configuration=backend_configuration,
                global_compression_method="gzip",
                global_compression_options={"level": 5},
            )
