MaxTwo conversion
-----------------

Install NeuroConv with the additional dependencies necessary for reading MaxTwo data.

.. code-block:: bash

    pip install neuroconv[maxwell]

Convert a single data stream from a single recording session in a MaxTwo file to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.maxwell.maxtwodatainterface.MaxTwoRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import MaxTwoRecordingInterface
    >>>
    >>> # Change the file_path to the location in your system
    >>> file_path = f"{ECEPHY_DATA_PATH}/maxwell/MaxTwo_data/Activity_Scan/000021/data.raw.h5"
    >>>
    >>> # If recording session names are not known ahead of time, you can easily retrieve them
    >>> MaxTwoRecordingInterface.get_recording_names(file_path=file_path, verbose=False)
    ["rec0000", "rec0001"]
    >>> # Choose a name from the list
    >>> recording_name = "rec0000"
    >>>
    >>> # If stream names are not known ahead of time, you can easily retrieve them
    >>> MaxTwoRecordingInterface.get_stream_names(
    >>>     file_path=file_path, recording_name=recording_name, verbose=False
    >>> )
    ["well000", "well001", "well002", "well003", "well004", "well005"]
    >>> stream_name = "well000"
    >>>
    >>> interface = MaxTwoRecordingInterface(
    >>>    file_path=file_path, recording_name=recording_name, stream_name=stream_name, verbose=False
    >>> )
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
