TDT Events data conversion
--------------------------

Install NeuroConv with the additional dependencies necessary for reading `Tucker-Davis Technologies (TDT) <https://www.tdt.com/>`_ event data.

.. code-block:: bash

    pip install "neuroconv[tdt_events]"

Convert discrete TDT events (epocs such as port entries or nose pokes) to NWB using :py:class:`~neuroconv.datainterfaces.behavior.tdt_events.tdteventsdatainterface.TDTEventsInterface`.
Each selected epoc is written as an ``ndx_events.Events`` object (onset timestamps) into ``nwbfile.acquisition``.

.. code-block:: python

    >>> from neuroconv.datainterfaces import TDTEventsInterface

    >>> folder_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT" / "Photo_63_207-181030-103332"

    >>> # event_names selects which TDT epocs to store; omit it to store every epoc in the tank
    >>> interface = TDTEventsInterface(folder_path=folder_path, event_names=["PrtN", "LNRW"], verbose=False)

    >>> # Extract what metadata we can from the source files (session_start_time is read from the tank)
    >>> metadata = interface.get_metadata()
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)
