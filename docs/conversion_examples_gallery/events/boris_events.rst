BORIS Events data conversion
----------------------------

Install NeuroConv with the additional dependencies necessary for reading BORIS data.

.. code-block:: bash

    pip install "neuroconv[boris_events]"

BORIS records behavior a person scored by hand against video, audio or a live session. A ``.boris`` file
is one JSON document holding the coding scheme, the subjects and every observation with its events. An
observation is one scoring session, so a file usually holds several and this interface takes one by name.

A behavior's kind is declared in the coding scheme rather than marked on the rows. A point behavior
occupies one row; a state behavior occupies two, a start and a stop, which pair on subject plus code in
order of appearance, so the coding scheme is what says which of the two a row belongs to.

Convert BORIS Events data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use :py:class:`~neuroconv.datainterfaces.events.boris.boriseventsdatainterface.BORISEventsInterface`.
Every behavior the scheme declares becomes an event type and all of them are written into one
``pynwb.event.EventsTable`` named after the observation, with ``subject`` and ``comment`` carried per
event. A behavior may also declare modifier slots, the qualifiers a coder answers each time they score it
(``Walking`` asking for a speed and a direction), and each slot gets its own column named after it. The
scheme itself is written as an ``ndx-ethogram`` ``Ethogram`` catalogue in the ``behavior`` processing
module, where ``modifier_slots`` names the columns each behavior's slots write into and
``modifier_slot_values`` the menu each one offers, and the closed state bouts as an ``EthogramBouts``
table beside it.

.. code-block:: python

    >>> from neuroconv.datainterfaces import BORISEventsInterface

    >>> file_path = BEHAVIOR_DATA_PATH / "boris" / "json_project" / "version_7_0" / "media_and_live_observations" / "two_players_multi_subject_and_an_unclosed_bout.boris"

    >>> # A project holds many observations, so pick one by name.
    >>> BORISEventsInterface.get_observation_names(file_path=file_path)[:3]
    ['offset positif', 'offset neg', 'observation #1']

    >>> interface = BORISEventsInterface(file_path=file_path, observation_name="observation #1", verbose=False)

    >>> # Every behavior the scheme declares is an event type, including ones nothing was scored against.
    >>> metadata = interface.get_metadata()
    >>> sorted(metadata["Events"]["boris"]["event_types"])
    ['m', 'p', 'q', 'r', 's']

    >>> # The observation's date is the session start, so it does not have to be supplied.
    >>> metadata["NWBFile"]["session_start_time"]
    datetime.datetime(2016, 11, 27, 1, 57, 26)

    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)

A behavior nothing was scored against is written as a zero-row contribution rather than dropped, since
the vocabulary is part of the record. A state bout that opens and never closes keeps a ``NaN`` duration,
which happens whenever a coder misses a stop in a live session and cannot be repaired afterwards.

A BORIS subject is an animal being scored and one observation routinely carries several, so it cannot map
onto the file's single ``Subject`` and is written as a per-event column instead. BORIS writes an event
attributed to nobody two ways, as the empty string and as the literal ``No focal subject``, and both are
read as nobody.

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as what a behavior code stands
for beyond the name a coder typed, or the operational definition a scheme's author never wrote down.
Follow :ref:`the events how-to <annotate_events_metadata>` for a modality-relevant guide to adding this
extra metadata, which makes the data more useful for future users and for the community as a whole.
