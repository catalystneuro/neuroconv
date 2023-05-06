Micro-Manager TIFF data conversion
----------------------------------

Install NeuroConv with the additional dependencies necessary for reading Micro-Manager TIFF data.

.. code-block:: bash

    pip install neuroconv[micromanagertiff]

Convert Micro-Manager TIFF imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.micromanagertiff.micromanagertiffdatainterface.MicroManagerTiffImagingInterface`.

.. code-block:: python

    >>> from dateutil import tz
    >>> from neuroconv.datainterfaces import MicroManagerTiffImagingInterface
    >>>
    >>> # The 'folder_path' is the path to the folder containing the OME-TIF image files and the 'DisplaySettings.json' file with the Micro-Manager properties.
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "MicroManagerTif" / "TS12_20220407_20hz_noteasy_1"
    >>> interface = MicroManagerTiffImagingInterface(folder_path=folder_path)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we can add the time zone information to the conversion if missing
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> if session_start_time.tzinfo is None:
    ...     tzinfo = tz.gettz("US/Pacific")
    ...     metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    NWB file saved at ...
