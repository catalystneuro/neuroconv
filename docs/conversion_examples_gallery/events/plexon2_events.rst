.. _plexon2-events-conversion:

Plexon2 Events Conversion
-------------------------

Use :py:class:`~neuroconv.datainterfaces.ecephys.plexon.plexon2eventsinterface.Plexon2EventsInterface`
to convert individual digital inputs and strobed words in a PL2 file. The events interface
works with a base NeuroConv install, including on systems without Wine. By default, it writes
one events table for each supported channel that recorded events anywhere in the file. The
tables keep timestamps on the same clock as the continuous recording. A strobed channel
also keeps every captured value in the ``strobed_word`` column.

.. code-block:: python

    >>> from datetime import timezone
    >>> from pynwb import NWBHDF5IO
    >>> from neuroconv.datainterfaces import Plexon2EventsInterface

    >>> file_path = (
    ...     ECEPHY_DATA_PATH / "plexon" / "pl2" / "trode_layout" / "tetrode"
    ...     / "spikes_wideband_field_potentials_auxiliary_and_events.pl2"
    ... )
    >>> interface = Plexon2EventsInterface(file_path=file_path)
    >>> interface.get_event_type_source_ids()
    ['EVT01', 'EVT02', 'EVT03', 'Strobed']

    >>> metadata = interface.get_metadata()
    >>> # Replace UTC with the acquisition site's timezone for your recording.
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> metadata["NWBFile"]["session_start_time"] = session_start_time.replace(tzinfo=timezone.utc)
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)
    >>> with NWBHDF5IO(path_to_save_nwbfile, mode="r") as io:
    ...     strobed = io.read().get_events_table("Strobed")
    ...     print(strobed["strobed_word"][:].tolist())
    [65281, 65282, 65283, 65284]

The channel inventory includes silent channels. Use an extraction entry to select a
particular source, or select particular captured words. Requesting a silent channel produces
an empty table. Discovery also lists keyboard markers, recording-control events, and CinePlex
channels when their headers are present.

.. code-block:: python

    >>> sources = Plexon2EventsInterface.get_available_event_sources(file_path=file_path)
    >>> "EVT04" in sources
    True
    >>> selected = Plexon2EventsInterface(
    ...     file_path=file_path,
    ...     event_extraction_configuration={
    ...         "strobes": {
    ...             "source": "Strobed",
    ...             "separation": {"by_payload_fields": ["strobed_word"], "select": [65281]},
    ...         }
    ...     },
    ... )
    >>> selected.get_event_times("strobes_65281").tolist()
    [84.161475]
