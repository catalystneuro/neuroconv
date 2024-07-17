Excel data conversion
---------------------

Install NeuroConv with the additional dependencies necessary for reading Excel data.

.. code-block:: bash

    pip install "neuroconv[excel]"

Convert Excel data to NWB using
:py:class:`~neuroconv.datainterfaces.text.excel.exceltimeintervalsinterface.ExcelTimeIntervalsInterface`.

The Excel file must contain a header row that contains at least the column names "start_time" and "stop_time".
The Excel data will be saved as trials in the NWB file.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import ExcelTimeIntervalsInterface
    >>>
    >>> file_path = f"{TEXT_DATA_PATH}/trials.xlsx"
    >>> # Change the file_path to the location of the file in your system
    >>> interface = ExcelTimeIntervalsInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # Add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"] = dict(session_start_time=session_start_time)
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}" # This should be something like: "./saved_file.nwb"
    >>> nwbfile = interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
