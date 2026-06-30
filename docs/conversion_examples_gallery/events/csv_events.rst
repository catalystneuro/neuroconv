CSV Events data conversion
--------------------------

This CSV format is a raw acquisition format for discrete events (e.g. TTL pulses), with one CSV per
event stream. Each event CSV has a single ``timestamps`` column holding the onset times (seconds)
and is named after its stream (``<event_name>.csv``).

Install NeuroConv with the additional dependencies necessary for reading CSV event data.

.. code-block:: bash

    pip install "neuroconv[csv_events]"

Convert CSV event data to NWB using
:py:class:`~neuroconv.datainterfaces.events.csv_events.csveventsdatainterface.CSVEventsInterface`.
Each event stream is written as an ``ndx_events.Events`` object (onset timestamps) into ``nwbfile.acquisition``.

CSV recordings carry no embedded recording-start timestamp, so ``session_start_time`` must be
supplied explicitly in the metadata.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import CSVEventsInterface

    >>> folder_path = f"{OPHYS_DATA_PATH}/fiber_photometry_datasets/CSV/sample_data_csv_1"

    >>> interface = CSVEventsInterface(folder_path=folder_path, verbose=False)
    >>> metadata = interface.get_metadata()
    >>> # CSV recordings have no embedded start time, so it must be set explicitly.
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
