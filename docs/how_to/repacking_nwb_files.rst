.. _repacking_nwb_files:

How to Repack NWB Files
=======================

When you have an existing NWB file that was created without optimal chunking and compression settings,
or when you want to convert between storage backends (HDF5 and Zarr), you can use NeuroConv's repacking
functionality to create a new file with improved configurations without losing any data.

What is Repacking?
------------------

Repacking is the process of reading an existing NWB file and writing its contents to a new file with
updated backend configuration settings. This is useful for:

- Applying recommended chunking and compression to files created without them
- Converting between HDF5 and Zarr storage backends
- Updating compression methods or levels for better performance or storage efficiency
- Applying NeuroConv's default backend configurations to legacy files

The :py:meth:`~neuroconv.tools.nwb_helpers.repack_nwbfile` function handles this process automatically,
reading the source file and writing a new file with optimal default settings.

.. note::

    Repacking creates a **new file** and does not modify the original. Both files will exist after
    the operation completes, so ensure you have sufficient disk space.


Basic Repacking Example
------------------------

The simplest use case is repacking a file to apply NeuroConv's recommended default settings:

.. code-block:: python

    from neuroconv.tools.nwb_helpers import repack_nwbfile

    # Repack with default recommended settings
    repack_nwbfile(
        nwbfile_path="original_file.nwb",
        export_nwbfile_path="repacked_file.nwb",
    )

This will:

1. Read the original NWB file (automatically detecting whether it's HDF5 or Zarr)
2. Apply NeuroConv's recommended chunking and compression settings
3. Write a new file with the same backend type as the original

The repacked file will contain all the same data as the original, but with optimized storage settings
that can improve read performance and reduce file size.


Converting Between Backends
----------------------------

You can convert between HDF5 and Zarr backends by specifying the ``export_backend`` parameter:

**Converting HDF5 to Zarr**

.. code-block:: python

    from neuroconv.tools.nwb_helpers import repack_nwbfile

    # Convert from HDF5 (.nwb) to Zarr (.nwb.zarr)
    repack_nwbfile(
        nwbfile_path="file.nwb",
        export_nwbfile_path="file.nwb.zarr",
        export_backend="zarr",
    )

**Converting Zarr to HDF5**

.. code-block:: python

    from neuroconv.tools.nwb_helpers import repack_nwbfile

    # Convert from Zarr (.nwb.zarr) to HDF5 (.nwb)
    repack_nwbfile(
        nwbfile_path="file.nwb.zarr",
        export_nwbfile_path="file.nwb",
        export_backend="hdf5",
    )

.. tip::

    Zarr is particularly well-suited for cloud storage and parallel access, while HDF5 is a more
    mature format with broader tool support. Choose the backend that best fits your use case.


Complete Workflow Example
--------------------------

Here's a complete example showing how to create an uncompressed file, inspect its properties,
repack it, and verify the improvements:

.. code-block:: python

    from datetime import datetime
    from uuid import uuid4
    from pathlib import Path

    from pynwb import NWBFile, TimeSeries, NWBHDF5IO
    from neuroconv.tools.nwb_helpers import repack_nwbfile
    import h5py
    import numpy as np

    # Create sample data
    session_start_time = datetime(2020, 1, 1, 12, 30, 0)
    nwbfile = NWBFile(
        identifier=str(uuid4()),
        session_start_time=session_start_time,
        session_description="Example session for repacking demo",
    )

    # Add a large time series without compression
    data = np.random.randn(10000, 10)  # 10,000 time points, 10 channels
    timestamps = np.arange(10000) * 0.001  # 1 kHz sampling

    time_series = TimeSeries(
        name="LargeTimeSeries",
        description="Example data without compression",
        unit="volts",
        data=data,
        timestamps=timestamps,
    )
    nwbfile.add_acquisition(time_series)

    # Write without compression
    original_path = "uncompressed_file.nwb"
    with NWBHDF5IO(original_path, mode="w") as io:
        io.write(nwbfile)

    # Check original file properties
    with h5py.File(original_path, "r") as f:
        dataset = f["acquisition/LargeTimeSeries/data"]
        print("Original file:")
        print(f"  Chunks: {dataset.chunks}")
        print(f"  Compression: {dataset.compression}")
        print(f"  Size: {Path(original_path).stat().st_size / 1024:.1f} KB")

    # Repack with recommended settings
    repacked_path = "repacked_file.nwb"
    repack_nwbfile(
        nwbfile_path=original_path,
        export_nwbfile_path=repacked_path,
    )

    # Check repacked file properties
    with h5py.File(repacked_path, "r") as f:
        dataset = f["acquisition/LargeTimeSeries/data"]
        print("\nRepacked file:")
        print(f"  Chunks: {dataset.chunks}")
        print(f"  Compression: {dataset.compression}")
        print(f"  Size: {Path(repacked_path).stat().st_size / 1024:.1f} KB")

Expected output::

    Original file:
      Chunks: None
      Compression: None
      Size: 823.5 KB

    Repacked file:
      Chunks: (10000, 1)
      Compression: gzip
      Size: 156.2 KB

This demonstrates that repacking can significantly reduce file size while maintaining all the original data.


Advanced: Custom Backend Configuration
---------------------------------------

If you need more control over the repacking process beyond the default settings, you can manually
configure the backend before writing. This approach gives you fine-grained control over chunking,
compression, and buffering for each dataset.

.. code-block:: python

    from pynwb import read_nwb
    from neuroconv.tools.nwb_helpers import (
        get_default_backend_configuration,
        configure_and_write_nwbfile,
    )

    # Read the original file
    nwbfile = read_nwb("original_file.nwb")

    # Get default configuration as a starting point
    backend_configuration = get_default_backend_configuration(
        nwbfile=nwbfile,
        backend="hdf5"
    )

    # Customize specific datasets
    dataset_config = backend_configuration.dataset_configurations[
        "acquisition/LargeTimeSeries/data"
    ]
    # Note: Check AVAILABLE_HDF5_COMPRESSION_METHODS for available options
    dataset_config.compression_method = "Blosc"
    dataset_config.compression_options = {"cname": "zstd", "clevel": 5}
    dataset_config.chunk_shape = (1000, 10)  # Custom chunk shape

    # Write with custom configuration
    configure_and_write_nwbfile(
        nwbfile=nwbfile,
        backend_configuration=backend_configuration,
        nwbfile_path="custom_repacked_file.nwb",
        backend="hdf5",
    )

For more details on backend configuration, see :doc:`../user_guide/backend_configuration`.


Best Practices
--------------

**When to Repack**

- After receiving data files from external sources that lack compression
- When transitioning from development to production storage
- Before uploading to data archives that have strict size requirements
- When converting to a cloud-optimized format (Zarr) for remote access

**Performance Considerations**

- Repacking can take significant time for large files (proportional to file size)
- Ensure sufficient disk space for both the original and repacked files
- For very large files, consider processing during off-peak hours
- The repacked file size will typically be smaller due to compression

**Validation**

Always verify the repacked file contains the expected data:

.. code-block:: python

    from pynwb import read_nwb

    # Read and inspect the repacked file
    nwbfile = read_nwb("repacked_file.nwb")

    # Verify key data is present
    assert "LargeTimeSeries" in nwbfile.acquisition
    print(f"Session: {nwbfile.session_description}")
    print(f"Duration: {nwbfile.acquisition['LargeTimeSeries'].data.shape}")

**Cleanup**

After verifying the repacked file, you can safely remove the original:

.. code-block:: python

    import os

    # Only after verification!
    if os.path.exists("repacked_file.nwb"):
        os.remove("original_file.nwb")


Common Issues and Solutions
----------------------------

**Out of Memory Errors**

If repacking fails due to memory constraints with very large files, the default buffering
may need adjustment. Use the advanced custom configuration approach to set smaller buffer sizes.

**Incompatible Compression Methods**

Not all compression methods are available on all systems. If you encounter an error about an
unavailable compression method, check which methods are available:

.. code-block:: python

    from neuroconv.tools.nwb_helpers import AVAILABLE_HDF5_COMPRESSION_METHODS

    print(AVAILABLE_HDF5_COMPRESSION_METHODS)

The ``repack_nwbfile`` function uses ``gzip`` by default, which is universally available.

**Zarr-Specific Considerations**

When repacking to Zarr format:

- All datasets must be chunked (Zarr does not support contiguous layout)
- The output path should end with ``.nwb.zarr`` by convention
- The result will be a directory, not a single file


See Also
--------

- :doc:`../user_guide/backend_configuration` - Detailed information on backend configuration
- `PyNWB Advanced I/O Tutorial <https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/h5dataio.html>`_ - Low-level HDF5 dataset configuration
- `NWB Format Documentation <https://nwb-overview.readthedocs.io/>`_ - Background on the NWB format
