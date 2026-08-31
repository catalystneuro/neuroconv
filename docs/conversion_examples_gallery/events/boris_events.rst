BORIS Events data conversion
----------------------------

Install NeuroConv with the additional dependencies necessary for reading BORIS data.

.. code-block:: bash

    pip install "neuroconv[boris_events]"

BORIS records behavior a person scored by hand against video, audio or a live session. A ``.boris`` file
is one JSON document holding the coding scheme, the subjects and every observation with its events. The
NeuroConv interface converts a single scoring session.

Convert BORIS Events data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use :py:class:`~neuroconv.datainterfaces.events.boris.boriseventsdatainterface.BORISEventsInterface`.
Every behavior the scheme declares becomes an event type, and all of them are written into one
``pynwb.event.EventsTable`` named after the observation. How the behaviors map onto tables, all into one
by default or a table each, is driven entirely by the editable events metadata; see
:ref:`annotate_events_metadata` for the format.

The coding scheme itself is written as an ``ndx-ethogram`` ``Ethogram`` catalogue in the ``behavior``
processing module, and the closed state bouts as an ``EthogramBouts`` table beside it.

.. code-block:: python

    >>> from neuroconv.datainterfaces import BORISEventsInterface

    >>> file_path = BEHAVIOR_DATA_PATH / "boris" / "json_project" / "version_7_0" / "media_and_live_observations" / "two_players_multi_subject_and_an_unclosed_bout.boris"

    >>> # A project holds many observations, so pick one by name.
    >>> BORISEventsInterface.get_observation_names(file_path=file_path)[:3]
    ['offset positif', 'offset neg', 'observation #1']

    >>> interface = BORISEventsInterface(file_path=file_path, observation_name="observation #1", verbose=False)

    >>> metadata = interface.get_metadata()

    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)

A behavior nothing was scored against is written as a zero-row contribution rather than dropped, since
the vocabulary is part of the record. A state bout that opens and never closes keeps a ``NaN`` duration,
which happens whenever a coder misses a stop in a live session and cannot be repaired afterwards.

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as what a behavior code stands
for beyond the name a coder typed, or the operational definition a scheme's author never wrote down.
Follow :ref:`the events how-to <annotate_events_metadata>` for a modality-relevant guide to adding this
extra metadata, which makes the data more useful for future users and for the community as a whole.
