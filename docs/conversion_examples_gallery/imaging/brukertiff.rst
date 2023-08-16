Bruker TIFF data conversion
---------------------------

Install NeuroConv with the additional dependencies necessary for reading Bruker TIFF data.

.. code-block:: bash

    pip install neuroconv[brukertiff]

**Convert Bruker single imaging plane**

Convert Bruker TIFF imaging data to NWB using
:py:class:`~neuroconv.converters.BrukerTiffSinglePlaneConverter`.

.. code-block:: python

    >>> from dateutil import tz
    >>> from neuroconv.converters import BrukerTiffSinglePlaneConverter
    >>>
    >>> # The 'folder_path' is the path to the folder containing the OME-TIF image files and the XML configuration file.
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2023_02_20_Into_the_void_t_series_baseline-000"
    >>> converter = BrukerTiffSinglePlaneConverter(folder_path=folder_path)
    >>>
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we can add the time zone information to the conversion if missing
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = tz.gettz("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


**Convert Bruker multiple imaging planes**

Convert volumetric Bruker TIFF imaging data to NWB using
:py:class:`~neuroconv.converters.BrukerTiffMultiPlaneConverter`.
The `plane_separation_type` defined how to handle the imaging planes.
Use "contiguous" to create the volumetric two photon series, and "disjoint" to create separate imaging plane and two photon series for each plane.

.. code-block:: python

    >>> from dateutil import tz
    >>> from neuroconv.converters import BrukerTiffMultiPlaneConverter
    >>>
    >>> # The 'folder_path' is the path to the folder containing the OME-TIF image files and the XML configuration file.
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
    >>> converter = BrukerTiffMultiPlaneConverter(folder_path=folder_path, plane_separation_type="contiguous")
    >>>
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we can add the time zone information to the conversion if missing
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = tz.gettz("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
