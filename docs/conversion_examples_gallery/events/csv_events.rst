CSV Events data conversion
--------------------------

:py:class:`~neuroconv.datainterfaces.events.csv_events.csveventsdatainterface.CSVEventsInterface`
is a general-purpose reader for discrete events (e.g. TTL pulses) stored in a CSV file. You point it
at one CSV and assign each column a role: ``timestamps_column`` gives each event's onset (seconds),
``event_type_column`` names the type of each event (pass ``None`` for a single-type file),
``value_columns`` carries extra columns along as per-event values, and ``durations_column`` writes
per-event durations. Any column you do not assign a role is omitted, so event payloads are opt-in --
only the columns you name in ``value_columns`` are carried along. The resulting
``pynwb.event.EventsTable`` objects land in ``nwbfile.events``.

How the event types map onto tables -- one table per type by default, or several types merged into a
single table -- is driven entirely by the editable events metadata. See :ref:`annotate_events_metadata`
for the full metadata format.

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
