European Data Format (EDF) conversion
-------------------------------------

Install NeuroConv with the additional dependencies necessary for reading EDF data.

.. code-block:: bash

    pip install neuroconv[plexon]

Convert edf data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.plexon.plexondatainterface.PlexonRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import PlexonRecordingInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/plexon/File_plexon_3.plx"
    >>> # Change the file_path to the location in your system
    >>> interface = PlexonRecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
