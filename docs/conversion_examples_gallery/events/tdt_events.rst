TDT Events data conversion
--------------------------

Install NeuroConv with the additional dependencies necessary for reading `Tucker-Davis Technologies (TDT) <https://www.tdt.com/>`_ event data.

.. code-block:: bash

    pip install "neuroconv[tdt_events]"

Convert discrete TDT events (epocs such as port entries or nose pokes) to NWB using :py:class:`~neuroconv.datainterfaces.events.tdt_events.tdteventsdatainterface.TDTEventsInterface`.
Each selected epoc is written as a ``pynwb.event.EventsTable`` into ``nwbfile.events``.

How the event types are named, described and grouped into tables is driven entirely by the editable events metadata. See :ref:`annotate_events_metadata`.

.. code-block:: python

    >>> from neuroconv.datainterfaces import TDTEventsInterface

    >>> folder_path = ECEPHY_DATA_PATH / "tdt" / "epocs_with_offsets_1"

    >>> # exclude_events drops specific TDT epocs; omit it to store every epoc in the tank
    >>> interface = TDTEventsInterface(folder_path=folder_path, exclude_events=["Tick"], verbose=False)

    >>> # Extract what metadata we can from the source files (session_start_time is read from the tank)
    >>> metadata = interface.get_metadata()
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)

.. seealso::

    Other TDT data interfaces:

    - :doc:`../recording/tdt` to convert TDT extracellular electrophysiology recordings.
    - :doc:`../fiberphotometry/tdt_fp` to convert TDT fiber photometry signals.
