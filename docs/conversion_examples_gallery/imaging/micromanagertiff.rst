Micro-Manager TIFF data conversion
----------------------------------

Install NeuroConv with the additional dependencies necessary for reading Micro-Manager TIFF data.

.. code-block:: bash

    pip install "neuroconv[micromanagertiff]"

Convert Micro-Manager TIFF imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.micromanagertiff.micromanagertiffdatainterface.MicroManagerTiffImagingInterface`.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import MicroManagerTiffImagingInterface
    >>>
    >>> # The 'folder_path' is the path to the folder containing the OME-TIF image files and the 'DisplaySettings.json' file with the Micro-Manager properties.
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "MicroManagerTif" / "TS12_20220407_20hz_noteasy_1"
    >>> interface = MicroManagerTiffImagingInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we can add the time zone information to the conversion if missing
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> if session_start_time.tzinfo is None:
    ...     tzinfo = ZoneInfo("US/Pacific")
    ...     metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

NeuroConv writes as much metadata as is available in the source format, but most of the time the
experimenter has metadata that the records do not carry. Adding the rest improves the provenance of
the file and makes it more useful for future users and for the community as a whole. To add it, follow
:ref:`the ophys how-to <annotate_ophys_metadata>`, which walks through common experimental
configurations, and in particular
:ref:`its section on templates <how_to_annotate_ophys_from_a_template>`, which starts from scratch.
For a general reference of every element the metadata accepts, see the
:ref:`reference template <ophys_imaging_metadata_template>`.
