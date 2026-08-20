Scanbox data conversion
-----------------------

Install NeuroConv with the additional dependencies necessary for reading Scanbox data.

.. code-block:: bash

    pip install"neuroconv[scanbox]"

Convert Scanbox imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.sbx.sbxdatainterface.SbxImagingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import SbxImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Scanbox" / "sample.sbx"
    >>> interface = SbxImagingInterface(file_path=file_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
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
