OpenEphys data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading OpenEphys data.

.. code-block:: bash

    pip install neuroconv[openephys]

Convert OpenEphys data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.openephys.openephysdatainterface.OpenEphysRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>>
    >>> from neuroconv.datainterfaces import OpenEphysRecordingInterface
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/openephysbinary/v0.4.4.1_with_video_tracking"
    >>> # Change the folder_path to the appropriate location in your system
    >>> interface = OpenEphysRecordingInterface(folder_path=folder_path)
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    NWB file saved at ...
