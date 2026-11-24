Plexon Recording Conversion
---------------------------

Install NeuroConv with the additional dependencies necessary for reading Plexon acquisition data.

.. code-block:: bash

    pip install "neuroconv[plexon]"

Convert Plexon recording data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.plexon.plexondatainterface.PlexonRecordingInterface`. Currently, only .plx is supported.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import PlexonRecordingInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/plexon/4chDemoPLX.plx"
    >>> # Change the file_path to the location in your system
    >>> interface = PlexonRecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

.. _plexon_recorded_events:

Recorded events
^^^^^^^^^^^^^^^

Use :py:class:`~neuroconv.datainterfaces.ecephys.plexon.plexoneventsinterface.PlexonEventsInterface`
to convert the individual digital inputs and strobed words recorded in the same PLX file.
By default, each populated experimental event channel gets its own table. The
``strobed_word`` column holds the full unsigned 16-bit value captured at each strobe.

.. code-block:: python

    >>> from pynwb import NWBHDF5IO
    >>> from neuroconv.datainterfaces import PlexonEventsInterface
    >>>
    >>> file_path = (
    ...     ECEPHY_DATA_PATH / "plexon" / "plx" / "trode_layout" / "tetrode"
    ...     / "spikes_wideband_field_potentials_and_events.plx"
    ... )
    >>> interface = PlexonEventsInterface(file_path=file_path)
    >>> interface.get_event_type_source_ids()
    ['EVT01', 'EVT02', 'EVT03', 'Strobed']
    >>> metadata = interface.get_metadata()
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> events_path = output_folder / "plexon_events.nwb"
    >>> interface.run_conversion(nwbfile_path=events_path, metadata=metadata)
    >>> with NWBHDF5IO(events_path, mode="r") as io:
    ...     print(io.read().events["Strobed"]["strobed_word"][:].tolist())
    [65281, 65282, 65283, 65284]

Use ``get_available_event_sources(file_path)`` to find the channel names recorded in
the header, including silent channels. To request specific words from ``Strobed``,
split the channel by ``strobed_word`` and pass the values in ``select``. Omit ``select``
to convert one type per distinct captured word.

.. code-block:: python

    >>> interface = PlexonEventsInterface(
    ...     file_path=file_path,
    ...     event_extraction_configuration={
    ...         "strobes": {
    ...             "source": "Strobed",
    ...             "separation": {"by_payload_fields": ["strobed_word"], "select": [65281]},
    ...         },
    ...     },
    ... )
    >>> interface.get_event_times("strobes_65281").tolist()
    [0.681975]
    >>> metadata = interface.get_metadata()
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> interface.run_conversion(nwbfile_path=output_folder / "selected_plexon_events.nwb", metadata=metadata)
