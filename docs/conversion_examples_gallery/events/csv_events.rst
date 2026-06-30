CSV Events data conversion
--------------------------

:py:class:`~neuroconv.datainterfaces.events.csv_events.csveventsdatainterface.CSVEventsInterface`
is a general-purpose reader for discrete events (e.g. TTL pulses) stored in a CSV file. You point it
at one CSV and name the column that holds the event onset times (``timestamps_column``). Pass
``event_type_column=None`` when the file is a single event type, in which case it is written as an
``ndx_events.Events`` object named after the file stem. When the file holds several event types told
apart by a label column, name that column with ``event_type_column`` and the file is written as an
``ndx_events.LabeledEvents`` object carrying the per-event labels. Either way the object lands in
``nwbfile.acquisition``.

Install NeuroConv with the additional dependencies necessary for reading CSV event data.

.. code-block:: bash

    pip install "neuroconv[csv_events]"

CSV recordings carry no embedded recording-start timestamp, so ``session_start_time`` must be
supplied explicitly in the metadata.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import CSVEventsInterface

    >>> file_path = f"{OPHYS_DATA_PATH}/fiber_photometry_datasets/CSV/sample_data_csv_1/Sample_TTL.csv"

    >>> interface = CSVEventsInterface(
    ...     file_path=file_path, timestamps_column="timestamps", event_type_column=None, verbose=False
    ... )
    >>> metadata = interface.get_metadata()
    >>> # CSV recordings have no embedded start time, so it must be set explicitly.
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
