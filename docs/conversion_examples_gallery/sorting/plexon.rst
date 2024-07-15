Plexon sorting data conversion
------------------------------

Install NeuroConv with the additional dependencies necessary for reading Plexon data.

.. code-block:: bash

    pip install "neuroconv[plexon]"

Convert Plexon spiking data (.plx) to NWB using :py:class:`~.neuroconv.datainterfaces.ecephys.plexon.plexondatainterface.PlexonSortingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import PlexonSortingInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/plexon/File_plexon_2.plx"
    >>> # Change the file_path to the location in your system
    >>> interface = PlexonSortingInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> tzinfo = ZoneInfo("US/Pacific")
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
