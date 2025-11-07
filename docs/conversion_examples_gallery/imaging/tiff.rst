TIFF data conversion
--------------------

Install NeuroConv with the additional dependencies necessary for reading TIFF data.

.. code-block:: bash

    pip install "neuroconv[tiff]"

Convert TIFF imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.tiff.tiffdatainterface.TiffImagingInterface`.

Basic single-file TIFF conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import TiffImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "demoMovie.tif"
    >>> interface = TiffImagingInterface(file_path=file_path, sampling_frequency=15.0, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

Multi-file TIFF conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The interface also supports multi-file TIFF datasets with configurable dimension orders and multi-channel data:

.. code-block:: python

    >>> from neuroconv.datainterfaces import TiffImagingInterface
    >>>
    >>> file_paths = [
    >>>     "path/to/file_001.tif",
    >>>     "path/to/file_002.tif",
    >>>     "path/to/file_003.tif",
    >>> ]
    >>> interface = TiffImagingInterface(
    >>>     file_paths=file_paths,
    >>>     sampling_frequency=30.0,
    >>>     dimension_order="CZT",  # Channel, Z-plane, Time
    >>>     num_channels=2,
    >>>     channel_name="0",  # Extract channel 0
    >>> )

Advanced parameters
^^^^^^^^^^^^^^^^^^^

The interface supports several parameters for handling complex TIFF data:

* ``dimension_order``: Specify how dimensions are organized in the TIFF file (default: "ZCT")

  - "ZCT": Z-planes, Channels, Time
  - "CZT": Channels, Z-planes, Time
  - Other combinations are supported

* ``num_channels``: Number of color channels in the TIFF file (default: 1)
* ``channel_name``: Name of the channel to extract (e.g., "0", "1"). Required when num_channels > 1
* ``num_planes``: Number of z-planes per volume for volumetric data (default: 1)

To get available channel names programmatically:

.. code-block:: python

    >>> available_channels = TiffImagingInterface.get_available_channels(num_channels=2)
    >>> print(available_channels)  # ['0', '1']
