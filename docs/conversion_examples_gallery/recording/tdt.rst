Tucker-Davis Technologies (TDT) data conversion
-----------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading TDT data.

.. code-block:: bash

    pip install neuroconv[tdt]

Convert TDT data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.tdt.tdtdatainterface.TdtRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import TdtRecordingInterface
    >>>
    >>> # For this data interface we need to pass the folder_path with the location of the data
    >>> folder_path = f"{ECEPHY_DATA_PATH}/tdt/aep_05"
    >>> # Change the folder_path to the location of the data in your system
    >>> interface = TdtRecordingInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>>  # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    >>>
    >>> # If the conversion was successful this should evaluate to ``True`` as the file was created.
    >>> Path(nwbfile_path).is_file()
    True
