Bruker TIFF data conversion
---------------------------

Install NeuroConv with the additional dependencies necessary for reading Bruker TIFF data.

.. code-block:: bash

    pip install neuroconv[brukertiff]

Convert Bruker TIFF imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.brukertiff.brukertiffdatainterface.BrukerTiffImagingInterface`.

.. code-block:: python

    >>> from dateutil import tz
    >>> from neuroconv.datainterfaces import BrukerTiffImagingInterface
    >>>
    >>> # The 'folder_path' is the path to the folder containing the OME-TIF image files and the XML configuration file.
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2023_02_20_Into_the_void_t_series_baseline-000"
    >>> interface = BrukerTiffImagingInterface(folder_path=folder_path)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we can add the time zone information to the conversion if missing
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = tz.gettz("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    NWB file saved at ...
