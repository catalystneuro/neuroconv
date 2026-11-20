Neuralynx Events data conversion
--------------------------------

Install NeuroConv with the additional dependencies necessary for reading Neuralynx event files.

.. code-block:: bash

    pip install "neuroconv[neuralynx_events]"

Convert the events of a Neuralynx event file (``.nev``) to NWB using :py:class:`~neuroconv.datainterfaces.events.neuralynx_events.neuralynxeventsdatainterface.NeuralynxEventsInterface`.
Every record of the file (TTL changes, recording starts and stops, typed comments) is written as a row of a ``pynwb.event.EventsTable`` in ``nwbfile.events``.

How the event types are named, described and grouped into tables is driven entirely by the editable events metadata. See :ref:`annotate_events_metadata`.

.. code-block:: python

    >>> from neuroconv.datainterfaces import NeuralynxEventsInterface

    >>> file_path = ECEPHY_DATA_PATH / "neuralynx" / "pegasus" / "version_2_1_1_development" / "events" / "ttl_and_start_stop" / "Events_0008.nev"
    >>> interface = NeuralynxEventsInterface(file_path=file_path, verbose=False)

    >>> # Extract what metadata we can from the source file (session_start_time is read from the header)
    >>> metadata = interface.get_metadata()
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)

.. seealso::

    Other Neuralynx data interfaces:

    - :doc:`../recording/neuralynx` to convert Neuralynx extracellular electrophysiology recordings.
    - :doc:`../sorting/neuralynx` to convert Neuralynx spike sorting data.
