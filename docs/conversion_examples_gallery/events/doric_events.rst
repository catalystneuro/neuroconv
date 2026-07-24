Doric Events data conversion
----------------------------

Convert discrete events from Doric Neuroscience Studio ``.doric`` digital IO to NWB using :py:class:`~neuroconv.datainterfaces.events.doric_events.doriceventsdatainterface.DoricEventsInterface`.
Each digital line's rising edges are detected and written as one ``pynwb.event.EventsTable`` per line (onset timestamps) into ``nwbfile.events``.

.. code-block:: python

    >>> from neuroconv.datainterfaces import DoricEventsInterface

    >>> file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "doric" / "BBC300_Acq_0093_stub.doric"

    >>> interface = DoricEventsInterface(file_path=file_path, verbose=False)

    >>> # session_start_time is read from the file's "Created" attribute
    >>> metadata = interface.get_metadata()
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)

.. seealso::

    - :doc:`../fiberphotometry/doric_fp` to convert Doric fiber photometry signals.
