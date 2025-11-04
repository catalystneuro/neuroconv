Comma-Separated Values (CSV) files
----------------------------------

Install NeuroConv. No extra dependencies are necessary for reading CSV.

.. code-block:: bash

    pip install neuroconv

Convert CSV data to NWB using
:py:class:`~neuroconv.datainterfaces.text.csv.csvtimeintervalsinterface.CsvTimeIntervalsInterface`.
This interface is designed to convert tabular time interval data (such as experimental trials, behavioral epochs, or task events)
from CSV files into NWB format as TimeIntervals objects, which are typically saved as trials in the NWB file.

Understanding CSV Format Requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The CSV file must contain time interval data with at least timing information for each interval.
Each row represents one time interval (e.g., a trial, epoch, or event), and columns represent properties of those intervals.

**Required Columns:**

- ``start_time``: Start time of each interval in seconds (REQUIRED)

**Optional Columns:**

- ``stop_time``: Stop time of each interval in seconds

  - If not provided, it will be automatically generated from the next interval's ``start_time``
  - The last interval's ``stop_time`` will be NaN if not provided

- **Any additional columns**: Custom metadata for each interval (e.g., trial_type, condition, reward, correct, etc.)

**Example CSV Structure:**

Here is an example of a properly formatted CSV file demonstrating different data types:

.. code-block:: text

    start_time,stop_time,trial_id,condition,trial_type,correct,reward_amount
    0.5,1.2,1,1,left,True,0.1
    1.5,2.1,2,2,right,False,0.0
    2.3,3.0,3,1,left,True,0.15
    3.2,4.1,4,2,right,,
    4.5,5.3,5,1,left,True,0.1

This CSV demonstrates different data types that are preserved when converting to NWB:

- ``start_time`` (float): Trial start time in seconds
- ``stop_time`` (float): Trial end time in seconds
- ``trial_id`` (integer): Unique trial identifier
- ``condition`` (integer): Experimental condition code
- ``trial_type`` (string): Type of trial ("left" or "right")
- ``correct`` (boolean): Whether the response was correct (True/False)
- ``reward_amount`` (float): Amount of liquid reward in mL



Basic Usage
~~~~~~~~~~~

The following example demonstrates basic conversion of a CSV file containing trial data to NWB format:

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import CsvTimeIntervalsInterface
    >>>
    >>> # Path to your CSV file containing trial data
    >>> file_path = f"{TEXT_DATA_PATH}/trials.csv"
    >>> # Change the file_path to the location of the file in your system
    >>> interface = CsvTimeIntervalsInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract metadata from the source file
    >>> metadata = interface.get_metadata()
    >>> # Add the required time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"] = dict(session_start_time=session_start_time)
    >>>
    >>> # Run the conversion to create an NWB file
    >>> nwbfile_path = path_to_save_nwbfile  # This should be something like: "./saved_file.nwb"
    >>> nwbfile = interface.run_conversion(
    ...     nwbfile_path=nwbfile_path,
    ...     metadata=metadata,
    ...     column_descriptions={
    ...         "trial_id": "Unique identifier for each trial",
    ...         "condition": "Experimental condition code",
    ...         "trial_type": "Type of trial (left or right)",
    ...         "correct": "Whether the response was correct",
    ...         "reward_amount": "Amount of liquid reward delivered in mL"
    ...     }
    ... )

After conversion, the trial data will be accessible as ``nwbfile.trials`` in the output NWB file, with columns
for ``start_time``, ``stop_time``, and any additional columns from the CSV.

Customizing the Conversion
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Changing Where Data is Stored**

By default, CSV data is saved as **trials** (accessible as ``nwbfile.trials``). You can change where the data
is stored by modifying the ``table_name`` in the metadata before calling ``run_conversion()``:

- Set ``table_name="epochs"`` to save as epochs (accessible as ``nwbfile.epochs``)
- Set ``table_name="custom_name"`` to save as custom intervals (accessible as ``nwbfile.intervals["custom_name"]``)

You should also update the ``table_description`` to match your data:

.. code-block:: python

    # Example: Save as epochs instead of trials
    metadata["TimeIntervals"]["trials"].update(
        table_name="epochs",
        table_description="Behavioral epochs during the experimental session"
    )

    # Or save as custom time intervals
    metadata["TimeIntervals"]["trials"].update(
        table_name="stimulus_presentations",
        table_description="Time intervals when visual stimuli were presented"
    )

**Column Descriptions and Renaming**

You can provide descriptions for your columns and rename them during conversion:

- ``column_descriptions``: Dictionary providing descriptions for each column (e.g., ``{"trial_type": "Type of trial presented"}``)
- ``column_name_mapping``: Dictionary to rename columns (e.g., ``{"condition": "trial_type"}``)

Advanced Reading Options
~~~~~~~~~~~~~~~~~~~~~~~~~

The interface provides additional options for customizing how CSV files are read and how columns are mapped.

You can pass additional parameters to pandas ``read_csv()`` function using the ``read_kwargs`` parameter,
which is useful for handling CSV files with different delimiters, encodings, or other special formatting.
You can also rename columns using the ``column_name_mapping`` parameter, which is especially useful for
CSVs with non-standard column names (e.g., ``start`` instead of ``start_time``):

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import CsvTimeIntervalsInterface
    >>>
    >>> # Example with custom CSV reading parameters and column renaming
    >>> interface = CsvTimeIntervalsInterface(
    ...     file_path=f"{TEXT_DATA_PATH}/trials.csv",
    ...     read_kwargs={
    ...         "sep": ",",           # Column separator (default is comma)
    ...         "encoding": "utf-8",  # File encoding
    ...         "skiprows": 0,        # Number of rows to skip at the start
    ...     },
    ...     verbose=False
    ... )
    >>>
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"] = dict(session_start_time=session_start_time)
    >>>
    >>> # Rename columns during conversion (e.g., 'condition' to 'trial_type')
    >>> nwbfile_path = path_to_save_nwbfile
    >>> interface.run_conversion(
    ...     nwbfile_path=nwbfile_path,
    ...     metadata=metadata,
    ...     column_name_mapping={"condition": "trial_type"},
    ...     overwrite=True
    ... )
