Doric Events data conversion
----------------------------

Convert discrete events (digital IO) from Doric Neuroscience Studio recordings to NWB. Doric records digital IO as sampled ``0``/``1`` lines; each line is edge-detected and written as one ``pynwb.event.EventsTable`` per line into ``nwbfile.events``. Doric ships these in two container forms, each with its own interface.

Both interfaces take a ``detection_configuration`` to select which lines are read and how each one's transitions become events. See :ref:`extract_events_from_signals` for that argument, and :ref:`annotate_events_metadata` for naming the resulting event types and grouping them into tables. This page covers the defaults and what is specific to the two Doric layouts.

Convert from a .doric HDF5 file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use :py:class:`~neuroconv.datainterfaces.events.doric_events.doriceventsdatainterface.DoricEventsInterface` for either ``.doric`` HDF5 layout: the modern one (root group ``DataAcquisition``, digital lines in ``DigitalIO`` groups) and the legacy "EPConsole" one (root group ``Traces``, digital lines the ``DI--O-*`` streams under each console). The layout is detected from the file, so the same call reads both. Each line is edge-detected; by default it is read as a ``high_period`` (onset at the rising edge, duration to the falling edge). ``session_start_time`` is read from the file's ``Created`` attribute when present, which the legacy layout does not carry.

.. code-block:: python

    >>> from neuroconv.datainterfaces import DoricEventsInterface

    >>> file_path = OPHYS_DATA_PATH / "events_datasets" / "doric" / "root_is_data_acquisition" / "single_line.doric"

    >>> interface = DoricEventsInterface(file_path=file_path, verbose=False)

    >>> # session_start_time is read from the file's "Created" attribute
    >>> metadata = interface.get_metadata()
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)


Convert from a DoricStudio CSV export
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use :py:class:`~neuroconv.datainterfaces.events.doric_events.doriccsveventsdatainterface.DoricCSVEventsInterface` for the DoricStudio CSV export. The digital IO columns (grouped under ``Digital I/O`` in the export's two-row header) are read the same way; by default each line is read as a ``high_period`` (onset at the rising edge, duration to the falling edge). The CSV export carries no session start time, so it must be set explicitly.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import DoricCSVEventsInterface

    >>> file_path = OPHYS_DATA_PATH / "events_datasets" / "doric" / "csv_export" / "interval_events.csv"

    >>> interface = DoricCSVEventsInterface(file_path=file_path, verbose=False)

    >>> metadata = interface.get_metadata()
    >>> # The DoricStudio CSV export carries no session start time, so it must be set explicitly.
    >>> metadata["NWBFile"]["session_start_time"] = datetime(2024, 1, 1, tzinfo=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)

.. seealso::

    - :doc:`../fiberphotometry/doric_fp` to convert Doric fiber photometry signals.
