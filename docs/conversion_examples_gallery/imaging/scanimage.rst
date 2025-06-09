ScanImage data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading ScanImage data.

.. code-block:: bash

    pip install "neuroconv[scanimage]"

Convert ScanImage imaging data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The `ScanImageImagingInterface` handles both single and multi-file data, as well as multi-channel data.
For multi-channel data, you need to specify the channel name, and you can use `plane_index` if you want to only write a specific plane.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import ScanImageImagingInterface
    >>>
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "volumetric_single_channel_single_file_no_flyback" / "vol_no_flyback_00001_00001.tif"
    >>>
    >>> # Specify channel_name for multi-channel data
    >>> # Specify plane_index for selecting a specific plane in multi-plane data or leave undefined  to write volumetric data
    >>> interface = ScanImageImagingInterface(
    ...     file_path=file_path,
    ...     channel_name="Channel 1",  # Required for multi-channel data
    ...     plane_index=None,  # Optional: specify to only write a specific plane
    ... )
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

.. note::
    For older ScanImage files (v3.8 and earlier), use the :doc:`ScanImageLegacyImagingInterface <scanimage_legacy>` interface instead.
