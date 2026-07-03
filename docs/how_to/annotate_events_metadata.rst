.. _annotate_events_metadata:

How to Annotate Discrete Events Metadata
========================================

This guide provides instructions for annotating discrete-event data (TTL lines, strobes, epocs,
markers) using NeuroConv's dict-based events metadata format.


.. _annotate_events_single_interface:

How to Annotate Events from a Single Interface
----------------------------------------------

In the simplest case one interface reads one source. Construct it and convert with no metadata
editing at all; the interface extracts everything needed for a faithful file.

.. code-block:: python

    from neuroconv.datainterfaces import TDTEventsInterface

    interface = TDTEventsInterface(folder_path="path/to/tank", metadata_key="behavioral_session")
    nwbfile = interface.create_nwbfile()

For a tank with two epoc stores, ``PtAB`` (port-entry codes) and ``PC0_`` (a reward marker), this
writes one ``EventsTable`` per store, **named after the store**, with the raw values written as-is
and no value labels:

.. code-block:: text

    PtAB  (EventsTable in /events; the table is named after the store's event_type_source_id)
    ┌───────────┬────────┐
    │ timestamp │ strobe │   <- the value column, named after its field_source_id; raw codes, no MeaningsTable
    ├───────────┼────────┤
    │    12.084 │  64959 │
    │    13.553 │  65535 │
    │       ... │    ... │
    └───────────┴────────┘

    PC0_  (EventsTable; a bare marker, so timestamps only)
    ┌───────────┐
    │ timestamp │
    ├───────────┤
    │     8.500 │
    │    19.310 │
    │       ... │
    └───────────┘

This is already correct: every event, every timestamp, every raw value is preserved. What it lacks
is *meaning*, the table is named ``PtAB``, its value column ``strobe``, and the code ``64959`` has no human label.
Annotation supplies that, and it is just editing the dict ``get_metadata()`` seeds. Each recipe below
edits that dict; apply the ones you need, then pass the result to ``create_nwbfile``.

**Inspect what the interface extracted.** Print the seeded dict to see the event types the
interface found (each keyed by its ``event_type_source_id``), the seeded defaults, and the value
vocabularies discovered from the data:

.. code-block:: python

    metadata = interface.get_metadata()
    print(metadata["Events"])

.. code-block:: python

    {
        "behavioral_session": {                   # the interface's metadata_key
            "event_types": {
                "PtAB": {                         # one entry per event type found (its event_type_source_id)
                    "table_metadata_key": "PtAB",  # seeded to its own table
                    "columns": {                  # value columns, keyed by field_source_id
                        "strobe": {               # the strobe value field
                            "column_name": "strobe",   # seeded to the field_source_id
                            "column_categories": {     # discovered vocabulary; labels/meanings for you to edit
                                "labels":   {64959: "64959", 65023: "65023", 65535: "65535"},
                                "meanings": {64959: "", 65023: "", 65535: ""},
                            },
                        },
                    },
                },
                "PC0_": {                         # constant value -> a bare marker (timestamps only)
                    "table_metadata_key": "PC0_",
                    "columns": {},                # no value columns
                },
            },
        },
        "EventTables": {                          # one seeded table per event type; rename or describe here
            "PtAB": {"table_name": "PtAB", "description": "Events from TDT epoc store 'PtAB'."},
            "PC0_": {"table_name": "PC0_", "description": "Events from TDT epoc store 'PC0_'."},
        },
    }

**Rename an event column.** ``column_name`` is the column header in the output table, seeded to the
``field_source_id``. Reach the value column through its event type and rename it:

.. code-block:: python

    column = metadata["Events"]["behavioral_session"]["event_types"]["PtAB"]["columns"]["strobe"]
    column["column_name"] = "choice"

The column header changes; the values are still the raw codes (this edit only renamed the column):

.. code-block:: text

    PtAB  (table not renamed yet)
    ┌───────────┬────────┐
    │ timestamp │ choice │
    ├───────────┼────────┤
    │    12.084 │  64959 │
    │    13.553 │  65535 │
    │       ... │    ... │
    └───────────┴────────┘

**Label categorical values.** For a code-like column, ``column_categories["labels"]`` maps each raw
value the hardware emitted to the display text written in its place:

.. code-block:: python

    column["column_categories"]["labels"] = {64959: "left", 65023: "center", 65535: "right"}

The cells now show the labels instead of the raw codes:

.. code-block:: text

    PtAB
    ┌───────────┬────────┐
    │ timestamp │ choice │
    ├───────────┼────────┤
    │    12.084 │ left   │
    │    13.553 │ right  │
    │       ... │ ...    │
    └───────────┴────────┘

**Describe what each value means.** ``column_categories["meanings"]`` gives each label a longer
description. The descriptions become a ``MeaningsTable`` that is **contained in the events table**
(in its ``meanings_tables`` group), named after the column it describes (``choice_meanings``):

.. code-block:: python

    column["column_categories"]["meanings"] = {
        64959: "Subject chose the left port",
        65023: "Subject chose the center port",
        65535: "Subject chose the right port",
    }

The ``choice`` column is unchanged; the events table now holds a ``choice_meanings`` MeaningsTable
describing each value:

.. code-block:: text

    PtAB  (EventsTable)
    ┌───────────┬────────┐
    │ timestamp │ choice │
    ├───────────┼────────┤
    │    12.084 │ left   │
    │    13.553 │ right  │
    │       ... │ ...    │
    └───────────┴────────┘
       meanings_tables/
       choice_meanings  (MeaningsTable, describes the choice column)
       ┌────────┬───────────────────────────────┐
       │ value  │ meaning                       │
       ├────────┼───────────────────────────────┤
       │ left   │ Subject chose the left port   │
       │ center │ Subject chose the center port │
       │ right  │ Subject chose the right port  │
       └────────┴───────────────────────────────┘

**Rename or describe the output table.** Each event type writes to the table named by its
``table_metadata_key``, seeded to a per-event-type entry in ``EventTables``. Edit that entry to rename or
describe the table:

.. code-block:: python

    metadata["Events"]["EventTables"]["PtAB"]["table_name"] = "Choices"
    metadata["Events"]["EventTables"]["PtAB"]["description"] = "Subject's choice (left, center, right)."

The table is now named ``Choices``. The final state is the events table with its contained
``choice_meanings`` MeaningsTable:

.. code-block:: text

    Choices  (EventsTable)
    ┌───────────┬────────┐
    │ timestamp │ choice │
    ├───────────┼────────┤
    │    12.084 │ left   │
    │    13.553 │ right  │
    │       ... │ ...    │
    └───────────┴────────┘
       meanings_tables/
       choice_meanings  (MeaningsTable)
       ┌────────┬───────────────────────────────┐
       │ value  │ meaning                       │
       ├────────┼───────────────────────────────┤
       │ left   │ Subject chose the left port   │
       │ center │ Subject chose the center port │
       │ right  │ Subject chose the right port  │
       └────────┴───────────────────────────────┘

**Apply the edits.** Pass the edited metadata to the conversion:

.. code-block:: python

    nwbfile = interface.create_nwbfile(metadata=metadata)

The events are unchanged from the first run, same timestamps and same occurrences; the edits only
renamed the table and column, replaced the displayed codes with labels, and added the contained
``choice_meanings`` MeaningsTable. Annotation never alters the events themselves, it makes them
legible.

**Write a continuous (numeric) column.** When a column carries a self-describing measurement rather
than codes (e.g. a TDT ``Freq`` store of stimulus frequencies in Hz), omit ``column_categories``
entirely and the raw numbers are written as a plain numeric column. Carry the unit in the
``column_name`` (e.g. ``"frequency_hz"``). A bare marker like ``PC0_`` carries no value at all: its
``columns`` is empty, so it is already timestamps-only and needs no edit of this kind.


.. _annotate_events_shared_table:

How to Write Multiple Event Types to a Single EventsTable
---------------------------------------------------------

In :ref:`annotate_events_single_interface` we annotated the tank's events. Give the reward marker its
own ``Rewards`` table the same way (rename its ``EventTables`` entry) and the interface writes **two
clean, separate tables**:

.. code-block:: text

    Choices  (EventsTable)        Rewards  (EventsTable)
    ┌───────────┬────────┐        ┌───────────┐
    │ timestamp │ choice │        │ timestamp │
    ├───────────┼────────┤        ├───────────┤
    │    12.084 │ left   │        │     8.500 │
    │    13.553 │ right  │        │    19.310 │
    │       ... │ ...    │        │       ... │
    └───────────┴────────┘        └───────────┘

That is fine when the events are genuinely separate kinds. But sometimes you want the different event
types of one interface in **one** table, for semantic grouping or to simplify a downstream read.
Point each event type's ``table_metadata_key`` at one shared ``EventTables`` entry:

.. code-block:: python

    # Continuing with the annotated metadata (the strobe column is renamed to "choice" and labeled).

    # Define the shared table once.
    metadata["Events"]["EventTables"]["behavior"] = {
        "table_name": "BehavioralEvents",
        "description": "Choices and rewards in one table.",
    }

    # Point both event types at it instead of their own tables.
    event_types = metadata["Events"]["behavioral_session"]["event_types"]
    event_types["PtAB"]["table_metadata_key"] = "behavior"   # the choice event type
    event_types["PC0_"]["table_metadata_key"] = "behavior"   # the reward marker

    nwbfile = interface.create_nwbfile(metadata=metadata)

Both event types now land in one ``BehavioralEvents`` table, one row per event, ordered by
``timestamp``. Because the rows come from different event types, the shared table carries an
``event_type`` column naming each row's type by its ``event_metadata_key``, and each event type
contributes only the value columns it carries: the ``PtAB`` event type adds a ``choice`` column,
while the ``PC0_`` marker is a bare timestamp and adds no value column. A reward row is therefore
identified by ``event_type = "PC0_"`` with the ``choice`` cell empty:

.. code-block:: text

    BehavioralEvents  (EventsTable)
    ┌───────────┬────────────┬────────┐
    │ timestamp │ event_type │ choice │
    ├───────────┼────────────┼────────┤
    │     8.500 │ PC0_       │        │   <- a bare marker: identified by event_type, no choice value
    │    12.084 │ PtAB       │ left   │
    │    13.553 │ PtAB       │ right  │
    │    19.310 │ PC0_       │        │
    │       ... │ ...        │ ...    │
    └───────────┴────────────┴────────┘

The ``event_type`` column is what makes sharing a table safe: without it a bare marker (which adds no
value column) would be an all-blank row, indistinguishable from any other, and its identity would be
lost. With it, every row knows its type regardless of which value columns it fills. The ``choice``
column keeps its ``choice_meanings`` MeaningsTable, now contained in ``BehavioralEvents``. The
``event_type`` value is each row's ``event_metadata_key`` (the source's own id, ``PtAB`` / ``PC0_``),
not a renamable label; to have a bare marker read under a friendlier name, keep it in its own table
(named via ``EventTables``) rather than merging.

By default each event type stays in its own table (no ``event_type`` column needed, since the table
*is* the type); you share a table when the grouping is worth it, and the writer adds the
``event_type`` column to keep the rows distinguishable.

Putting event types from *different* interfaces into one table works exactly the same way and is
shown next; the only difference is the columns live under different ``metadata_key`` s.


How to Annotate Multiple Events Interfaces
------------------------------------------

A single conversion often runs several event interfaces, here a TDT tank and a SpikeGLX NIDQ stream,
wired together in an ``NWBConverter``. Each interface gets its own ``metadata_key``, and that key is
what keeps them apart: two sources can expose the **same** ``event_type_source_id`` (two tanks both with a
store ``PtAB``, two boards both with a line ``XD0``), and the ``metadata_key`` namespaces each
interface's ``event_types`` block so those identical ids never clash.

.. code-block:: python

    from neuroconv.datainterfaces import TDTEventsInterface, SpikeGLXNIDQInterface
    from neuroconv import NWBConverter

    tdt_interface = TDTEventsInterface(folder_path="path/to/tank", metadata_key="tdt")

    # Signal-encoded interfaces also take an events-extraction config at construction
    # (which lines/levels, and how to read them); elided here to keep the focus on metadata.
    nidq_interface = SpikeGLXNIDQInterface(file_path="path/to/run.nidq.bin", metadata_key="nidq")

    converter = NWBConverter(data_interfaces={"tdt": tdt_interface, "nidq": nidq_interface})
    metadata = converter.get_metadata()

    # Each interface's event types live under its own metadata_key, so identical event_type_source_ids
    # from different interfaces never collide: metadata["Events"]["tdt"] vs ["nidq"].
    metadata["Events"]["tdt"]["event_types"]["PtAB"]["columns"]["strobe"]["column_name"] = "choice"
    # XD0 is a bare marker (no value column); name it by renaming its table instead.
    metadata["Events"]["EventTables"]["XD0"]["table_name"] = "CameraFrames"

So far each event type keeps its own default table, giving separate tables per interface. Sharing a
table **across** interfaces works exactly like sharing within one (above): point each event type's
``table_metadata_key`` at a shared ``EventTables`` entry. The only difference is the event types live
under different ``metadata_key`` s; the shared ``EventTables`` block is global, so event types from any
interface can route into it.

.. code-block:: python

    # A shared table for events from both interfaces.
    metadata["Events"]["EventTables"]["behavior"] = {
        "table_name": "BehavioralEvents",
        "description": "Rewards (TDT) and licks (NIDQ) sharing one table across interfaces.",
    }

    # A TDT reward marker and a NIDQ lick line, both bare markers, routed into the one shared table.
    metadata["Events"]["tdt"]["event_types"]["PC0_"]["table_metadata_key"] = "behavior"
    metadata["Events"]["nidq"]["event_types"]["XD1"]["table_metadata_key"] = "behavior"

    converter.run_conversion(nwbfile_path="session.nwb", metadata=metadata)

Both event types land in one ``BehavioralEvents`` table. As with sharing within a single interface,
the shared table carries an ``event_type`` column naming each row's type by its ``event_metadata_key``,
and each type contributes only the value columns it has. Both ``PC0_`` and ``XD1`` here are bare
markers (timestamps only, no value), so they add no value column at all, the table is just timestamps
tagged by type:

.. code-block:: text

    BehavioralEvents  (EventsTable)
    ┌───────────┬────────────┐
    │ timestamp │ event_type │
    ├───────────┼────────────┤
    │     8.500 │ PC0_       │   <- from the TDT interface
    │    11.200 │ XD1        │   <- from the NIDQ interface
    │    19.310 │ PC0_       │
    │       ... │ ...        │
    └───────────┴────────────┘

If a shared type did carry a value (e.g. a labeled choice), it would add its own column, filled only
on its rows, exactly as in the single-interface case above.

If you have a use case not covered here, please open an issue at `NeuroConv GitHub Issues
<https://github.com/catalystneuro/neuroconv/issues>`_.
