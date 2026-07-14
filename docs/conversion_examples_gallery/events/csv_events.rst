CSV Events data conversion
--------------------------

:py:class:`~neuroconv.datainterfaces.events.csv_events.csveventsdatainterface.CSVEventsInterface`
is a general-purpose reader for discrete events (e.g. TTL pulses) stored in a CSV file. You point it
at one CSV and assign each column a role. Every row is one event occurrence at ``timestamps_column``
(seconds). Pass ``event_type_column=None`` when the file is a single event type, in which case it is
written as one ``pynwb.event.EventsTable`` named after the file stem. When the file holds several event
types told apart by a label column, name that column with ``event_type_column``: each distinct value
becomes its own event type and, by default, its own ``EventsTable``. Merging several types into one
table with an ``event_type`` discriminator column is opt-in by pointing their ``table_metadata_key`` at
a shared key in the editable metadata. Optionally, ``value_columns`` carries extra columns along as
per-event values and ``durations_column`` writes per-event durations. Either way the tables land in
``nwbfile.events``.

CSV events need only NeuroConv's core dependencies, but the ``csv_events`` extra is available for a
consistent install command.

.. code-block:: bash

    pip install "neuroconv[csv_events]"

CSV recordings carry no embedded recording-start timestamp, so ``session_start_time`` must be
supplied explicitly in the metadata.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

    >>> import pandas as pd

    >>> from neuroconv.datainterfaces import CSVEventsInterface

    >>> # This format is just a CSV; here we write a small example event file with a single
    >>> # ``timestamps`` column holding the event timestamps (seconds).
    >>> file_path = output_folder / "ttl.csv"
    >>> pd.DataFrame({"timestamps": [1.5, 2.5, 3.5, 4.5]}).to_csv(file_path, index=False)

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
