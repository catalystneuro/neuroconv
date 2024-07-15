Comma-Separated Values (CSV) files
----------------------------------

Install NeuroConv. No extra dependencies are necessary for reading CSV.

.. code-block:: bash

    pip install neuroconv

Convert CSV data to NWB using
:py:class:`~neuroconv.datainterfaces.text.csv.csvtimeintervalsinterface.CsvTimeIntervalsInterface`.

The CSV file must contain a header row that contains at least the column names "start_time" and "stop_time".
The CSV data will be saved as trials in the NWB file.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import CsvTimeIntervalsInterface
    >>>
    >>> file_path = f"{TEXT_DATA_PATH}/trials.csv"
    >>> # Change the file_path to the location of the file in your system
    >>> interface = CsvTimeIntervalsInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # Add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"] = dict(session_start_time=session_start_time)
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}" # This should be something like: "./saved_file.nwb"
    >>> nwbfile = interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
