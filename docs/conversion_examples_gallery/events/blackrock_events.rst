Blackrock Events data conversion
--------------------------------

Install NeuroConv with the additional dependencies necessary for reading Blackrock event files.

.. code-block:: bash

    pip install "neuroconv[blackrock_events]"

Convert the events of a Blackrock event file (``.nev``) to NWB using :py:class:`~neuroconv.datainterfaces.events.blackrock_events.blackrockeventsdatainterface.BlackrockEventsInterface`.
Each kind of event packet in the file (the digital input port, comments, recording events and the others) is written as a ``pynwb.event.EventsTable`` into ``nwbfile.events``.

How the event types are named, described and grouped into tables is driven entirely by the editable events metadata. See :ref:`annotate_events_metadata`.

.. code-block:: python

    >>> from neuroconv.datainterfaces import BlackrockEventsInterface

    >>> file_path = ECEPHY_DATA_PATH / "blackrock" / "version_2_3" / "events" / "frame_counter_comments" / "frame_counter_comments.nev"
    >>> interface = BlackrockEventsInterface(file_path=file_path, verbose=False)

    >>> # Extract what metadata we can from the source file (session_start_time is read from the header)
    >>> metadata = interface.get_metadata()
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)

.. seealso::

    Other Blackrock data interfaces:

    - :doc:`../recording/blackrock` to convert Blackrock extracellular electrophysiology recordings.
    - :doc:`../sorting/blackrock` to convert Blackrock spike sorting data.
