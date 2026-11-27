OpenEphys Binary Events data conversion
---------------------------------------

Convert the discrete events of an `Open Ephys <https://open-ephys.org/gui>`_ binary recording to NWB using
:py:class:`~neuroconv.datainterfaces.events.openephys_events.openephysbinaryeventsdatainterface.OpenEphysBinaryEventsInterface`.
A Record Node writes one record every time a digital line changes state, into ``events/<stream>/TTL/``, and
writes its text annotations into a ``MessageCenter`` folder. By default a digital input stream becomes one
``pynwb.event.EventsTable`` in ``nwbfile.events`` with one row per recorded edge. Each row keeps the
signed ``open_ephys_state``, its ``line`` counted from 0 and ``onset``, and the recorded ``full_word`` when
available.

Install NeuroConv with the additional dependencies necessary for reading Open Ephys binary events.

.. code-block:: bash

    pip install "neuroconv[openephys_events]"

A recording holds one event stream per processor that emitted events, so the stream is selected by name, as
it is for the recording itself. ``event_extraction_configuration`` names the event types to write. Below, the
rising edge of line 0 opens a pulse and its next falling edge closes it, so each row has a duration. Event
table descriptions can be edited in the metadata. See :ref:`annotate_events_metadata`.

.. code-block:: python

    >>> from neuroconv.datainterfaces import OpenEphysBinaryEventsInterface

    >>> folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "v0.6.x_neuropixels_missing_folders"

    >>> OpenEphysBinaryEventsInterface.get_stream_names(folder_path=folder_path)
    ['Record Node 101#NI-DAQmx-103.PXIe-6341', 'Record Node 101#Neuropix-PXI-100.ProbeB']

    >>> interface = OpenEphysBinaryEventsInterface(
    ...     folder_path=folder_path,
    ...     stream_name="Record Node 101#NI-DAQmx-103.PXIe-6341",
    ...     event_extraction_configuration={
    ...         "sync_pulse": {"detection": {"lines": [0], "on_change": {"onset": "rising", "end": "falling"}}},
    ...     },
    ... )

    >>> # session_start_time is read from the settings file the GUI wrote for this experiment
    >>> metadata = interface.get_metadata()
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)

.. seealso::

    - :doc:`../recording/openephys` to convert the Open Ephys extracellular electrophysiology recording
      these events were recorded alongside.
