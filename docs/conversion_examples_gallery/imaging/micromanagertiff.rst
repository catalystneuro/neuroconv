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

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as the anatomical location,
the meaning of the values, or a semantically meaningful description of the data. Follow
:ref:`the ophys how-to <annotate_ophys_metadata>` for a modality-relevant guide to adding
this extra metadata, which makes the data more useful for future users and for the community as a whole.
Its :ref:`section on templates <how_to_annotate_ophys_from_a_template>` starts from scratch, and the
:ref:`reference template <ophys_imaging_metadata_template>` lists every element the metadata accepts.
