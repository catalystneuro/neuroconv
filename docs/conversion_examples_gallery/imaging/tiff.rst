TIFF data conversion
--------------------

Install NeuroConv with the additional dependencies necessary for reading TIFF data.

.. code-block:: bash

    pip install "neuroconv[tiff]"

Convert TIFF imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.tiff.tiffdatainterface.TiffImagingInterface`.

Single File, Planar and Single-Channel TIFF conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import TiffImagingInterface
    >>>
    >>> # Single TIFF file
    >>> file_paths = [OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "demoMovie.tif"]
    >>> interface = TiffImagingInterface(file_paths=file_paths, sampling_frequency=15.0, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

By default, the :py:class:`~neuroconv.datainterfaces.ophys.tiff.tiffdatainterface.TiffImagingInterface`
assumes that the data is single-channel and planar (i.e., non-volumetric). In terms of data layout,
this means the TIFF pages represent successive frames over time for a single channel.

For multi-channel and/or volumetric data, you can specify the number of channels and number of planes.
However, this introduces a question about the data layout: how do the TIFF pages correspond to channels,
planes, and timepoints? To specify this information, the interface relies on the concept of dimension
order from the `OME-TIFF specification <https://docs.openmicroscopy.org/ome-model/5.6.3/ome-tiff/specification.html#dimensionorder>`_.

The dimension order uses three letters:

* **Z**: Depth plane (z-axis position in volumetric imaging)
* **C**: Channel (e.g., different fluorophores or wavelengths)
* **T**: Time (or acquisition cycles)

The order indicates which dimension varies **fastest** (leftmost) to **slowest** (rightmost) when
reading frames sequentially from the TIFF file. The key principle is that the leftmost dimension
changes most frequently between consecutive frames.

For detailed explanations of all six dimension orders (ZCT, CZT, ZTC, CTZ, TCZ, TZC) with example
sequences and use cases, see the
:py:class:`~neuroconv.datainterfaces.ophys.tiff.tiffdatainterface.TiffImagingInterface` documentation.

.. raw:: html
   :file: ../../_static/js/dimension-order-visualizer-embed.html

|

Multi-channel multi-file TIFF conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For multi-channel and/or multi-plane data split across multiple files, you specify the dimension order,
number of channels, which channel to extract, and number of planes:

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import TiffImagingInterface
    >>>
    >>> # Multi-file TIFF dataset with 2 channels and 5 z-planes
    >>> file_paths = [
    ...     OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20240320_multifile_00001.tif",
    ...     OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20240320_multifile_00002.tif",
    ...     OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20240320_multifile_00003.tif",
    ... ]
    >>> interface = TiffImagingInterface(
    ...     file_paths=file_paths,
    ...     sampling_frequency=30.0,
    ...     dimension_order="CZT",  # Channels vary fastest, then Z-planes, then time
    ...     num_channels=2,
    ...     channel_name="0",       # Extract channel 0
    ...     num_planes=5,           # 5 z-planes per volume
    ...     verbose=False,
    ... )
    >>>
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

**Important**: When using multiple files, TIFF pages are assumed to continue **contiguously** across files
following the same dimension order. For example, if your dimension order is "CZT" and the first file ends
at page 23, the first page of the second file is treated as page 24 in the same acquisition sequence.
This is common when microscope software splits large acquisitions across multiple files to avoid file size limits.
