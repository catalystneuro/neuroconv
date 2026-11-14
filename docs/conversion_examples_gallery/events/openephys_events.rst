OpenEphys Binary Events data conversion
---------------------------------------

Convert the discrete events of an `Open Ephys <https://open-ephys.org/gui>`_ binary recording to NWB using
:py:class:`~neuroconv.datainterfaces.events.openephys_events.openephysbinaryeventsdatainterface.OpenEphysBinaryEventsInterface`.
A Record Node writes one record every time a digital line changes state, into ``events/<stream>/TTL/``, and
writes its text annotations into a ``MessageCenter`` folder. Each line that fired becomes its own
``pynwb.event.EventsTable`` in ``nwbfile.events``, holding every edge that line produced with the direction
of the transition in an ``edge`` column and the latched port value in a ``full_word`` column.

Open Ephys events are read straight from the ``.npy`` arrays, so this interface needs only NeuroConv's core
dependencies; the ``openephys_events`` extra is available for a consistent install command.

.. code-block:: bash

    pip install "neuroconv[openephys_events]"

A recording holds one event stream per processor that emitted events, so the stream is selected by name, as
it is for the recording itself. The tables are named after the lines (``Line1``, ``Line2``) because the file
records which wire fired and not what was wired to it; rename them in the metadata to say what they are. How
the event types are named, described and grouped into tables is driven entirely by the editable events
metadata. See :ref:`annotate_events_metadata`.

.. code-block:: python

    >>> from neuroconv.datainterfaces import OpenEphysBinaryEventsInterface

    >>> folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "v0.6.x_neuropixels_missing_folders"

    >>> OpenEphysBinaryEventsInterface.get_stream_names(folder_path=folder_path)
    ['Record Node 101#NI-DAQmx-103.PXIe-6341', 'Record Node 101#Neuropix-PXI-100.ProbeB']

    >>> interface = OpenEphysBinaryEventsInterface(
    ...     folder_path=folder_path,
    ...     stream_name="Record Node 101#NI-DAQmx-103.PXIe-6341",
    ... )

    >>> # session_start_time is read from the settings file the GUI wrote for this experiment
    >>> metadata = interface.get_metadata()
    >>> # Say what the lines were wired to; the file only knows their numbers.
    >>> metadata["Events"]["open_ephys_events"]["event_types"]["line1"]["event_name"] = "sync_pulse"
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)

.. seealso::

    - :doc:`../recording/openephys` to convert the Open Ephys extracellular electrophysiology recording
      these events were recorded alongside.
