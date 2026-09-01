BORIS data conversion
---------------------

Install NeuroConv with the additional dependencies necessary for reading BORIS data.

.. code-block:: bash

    pip install "neuroconv[boris]"

BORIS records behavior a person scored by hand against video, audio or a live session. A ``.boris`` file
is one JSON document holding the ethogram, the subjects involved and every observation with its events. The
NeuroConv interface converts a single scoring session.

Convert BORIS data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~

Use :py:class:`~neuroconv.datainterfaces.behavior.boris.borisdatainterface.BORISInterface`.
Every behavior the ethogram declares becomes an event type, and all of them are written into one
``pynwb.event.EventsTable`` named after the observation. How the behaviors map onto tables, all into one
by default or a table each, is driven entirely by the editable events metadata.

The ethogram in ``behaviors_conf`` is written as an ``ndx-ethogram`` ``Ethogram`` in the ``behavior``
processing module. Beside it goes an ``ndx-ethogram`` ``EthogramBouts`` table holding one row per closed
bout, a bout being an occurrence of a behavior whose ethogram ``type`` is ``State event`` rather than
``Point event``. Point events and bouts the coder never closed stay in the events table only.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import BORISInterface

    >>> file_path = BEHAVIOR_DATA_PATH / "boris" / "json_project" / "version_7_0" / "media_and_live_observations" / "two_players_multi_subject_and_an_unclosed_bout.boris"

    >>> # A project holds many observations, so pick one by name.
    >>> BORISInterface.get_observation_names(file_path=file_path)[:3]
    ['offset positif', 'offset neg', 'observation #1']

    >>> interface = BORISInterface(file_path=file_path, observation_name="observation #1", verbose=False)

    >>> metadata = interface.get_metadata()

    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)

    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)

A state bout that opens and never closes keeps a ``NaN`` duration, which happens whenever a coder misses
a stop in a live session and cannot be repaired afterwards.

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as what a particular modifier
value stands for, since BORIS describes a modifier set but never the answers it offers, or the apparatus
the session was scored against.
Follow :ref:`the events how-to <annotate_events_metadata>` for a modality-relevant guide to adding this
extra metadata, which makes the data more useful for future users and for the community as a whole.
