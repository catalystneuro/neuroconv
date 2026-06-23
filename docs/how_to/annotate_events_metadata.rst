.. _annotate_events_metadata:

How to Annotate Discrete Events Metadata
========================================

This guide provides instructions for annotating discrete-event data (TTL lines, strobes, epocs,
markers) using NeuroConv's dict-based events metadata format. For the structure of the events
metadata dict and what each field means, see :ref:`events_metadata_structure`.


How to Annotate a Single Events Interface
-----------------------------------------

In the simplest case one interface reads one source. Start by constructing the interface and
converting with no metadata editing at all: the interface extracts everything needed for a faithful
file.

.. code-block:: python

    from neuroconv.datainterfaces import TDTEventsInterface

    interface = TDTEventsInterface(folder_path="path/to/tank", metadata_key="behavioral_session")
    nwbfile = interface.create_nwbfile()

For a tank with two epoc stores, ``PtAB`` (port-entry codes) and ``PC0_`` (a reward marker), this
writes one ``EventsTable`` per store, **named after the store**, with the raw values written as-is
and no value labels:

.. code-block:: text

    PtAB  (EventsTable in /acquisition; table and column both named after the store's event_type_id)
    ┌───────────┬───────┐
    │ timestamp │  PtAB │   <- column named after the event_type_id; raw codes, no MeaningsTable
    ├───────────┼───────┤
    │    12.084 │ 64959 │
    │    13.553 │ 65535 │
    │       ... │   ... │
    └───────────┴───────┘

    PC0_  (EventsTable; a bare marker, so timestamps only)
    ┌───────────┐
    │ timestamp │
    ├───────────┤
    │     8.500 │
    │    19.310 │
    │       ... │
    └───────────┘

This is already correct: every event, every timestamp, every raw value is preserved. What it lacks
is *meaning*: the table and column are named ``PtAB``, and the code ``64959`` has no human label.
Annotation adds those, and annotation is just editing the dict the interface seeds. Print it to see
the event streams it found (each keyed by its ``event_type_id``), the seeded defaults, and the value
vocabularies discovered from the data:

.. code-block:: python

    metadata = interface.get_metadata()
    print(metadata["Events"])

It returns roughly this (values illustrative):

.. code-block:: python

    {
        "behavioral_session": {                  # the interface's metadata_key
            "event_columns": {
                "PtAB": {                         # one entry per discovered event stream (its event_type_id)
                    "column_name": "PtAB",        # seeded default = the event_type_id itself
                    "column_categories": {
                        # keys seeded from the raw values actually observed in the data;
                        # labels/meanings start as the raw value stringified, for you to edit
                        "labels":   {64959: "64959", 65023: "65023", 65535: "65535"},
                        "meanings": {64959: "", 65023: "", 65535: ""},
                    },
                    "table_metadata_key": "PtAB",  # seeded default = its own table (named after the event_type_id)
                },
                "PC0_": {
                    "column_name": "PC0_",
                    # no column_categories: PC0_ carries a single constant value, so it is
                    # seeded as a bare marker (timestamps only), not a categorical column
                    "table_metadata_key": "PC0_",
                },
            },
        },
        # EventTables is seeded with one default entry per column (each named after its event_type_id),
        # since each column's table_metadata_key defaults to its own table. Shown so you can
        # rename or describe them; you only add entries when several columns should share one table (see the next section).
        "EventTables": {
            "PtAB": {"table_name": "PtAB", "description": "Events from TDT epoc store 'PtAB'."},
            "PC0_": {"table_name": "PC0_", "description": "Events from TDT epoc store 'PC0_'."},
        },
    }

What each field is, and what ``get_metadata()`` seeds versus leaves to you:

- **The** ``metadata_key`` **block** (``"behavioral_session"``) holds this interface's columns.
  Named by the ``metadata_key`` you passed (or a source-derived default); it exists so identical
  ``event_type_id`` s from two interfaces never collide.
- ``event_columns``: one entry per event stream the interface found (``PtAB``, ``PC0_``). **The
  interface seeds these**; you edit the discovered ones, you do not add columns. The key is the
  ``event_type_id``.
- ``column_name``: the column's human-readable name. **Seeded to the** ``event_type_id``; rename it
  (``"port_entry"``).
- ``column_categories``: present only for a code-like field with several values. **The keys are the
  raw values the hardware emitted** (``64959/65023/65535``), discovered from the data; ``labels``
  (display text) and ``meanings`` (descriptions) are **seeded blank for you to fill in**. Omit the
  whole block to make the column continuous (a plain numeric column).
- ``table_metadata_key`` **and its** ``EventTables`` **entry**: the column's output table. **Seeded
  to its own** ``event_type_id`` (one table per column). Change it only to make columns share a
  table (next section).

Now edit: rename the column and curate its vocabulary, then convert again.

.. code-block:: python

    column = metadata["Events"]["behavioral_session"]["event_columns"]["PtAB"]

    column["column_name"] = "port_entry"
    column["column_categories"]["labels"] = {64959: "left", 65023: "center", 65535: "right"}
    column["column_categories"]["meanings"] = {
        64959: "left port entry",
        65023: "center port entry",
        65535: "right port entry",
    }

    # Optionally rename the output table too (edit its seeded EventTables entry):
    metadata["Events"]["EventTables"]["PtAB"]["table_name"] = "PortEntries"
    metadata["Events"]["EventTables"]["PtAB"]["description"] = "Nose-poke port entries."

    nwbfile = interface.create_nwbfile(metadata=metadata)

For a **continuous** column (a self-describing value, e.g. a TDT ``Freq`` store carrying stimulus
frequencies in Hz), omit ``column_categories`` entirely: the raw numbers are written as a plain
numeric column. Carry the unit in the ``column_name`` (e.g. ``"frequency_hz"``).

Converting again, the same ``PtAB`` events now write to a **renamed table with a labeled column**;
compare this to the bare output from the first run above:

.. code-block:: text

    PortEntries  (EventsTable in /acquisition; table_name now "PortEntries", was "PtAB")
    ┌───────────┬────────────┐
    │ timestamp │ port_entry │   <- column_name now "port_entry", was "PtAB"
    ├───────────┼────────────┤
    │    12.084 │      64959 │   <- raw codes unchanged; meaning now attached via the table below
    │    13.553 │      65535 │
    │       ... │        ... │
    └───────────┴────────────┘
            port_entry  ->  MeaningsTable   { 64959: "left port entry",
                                              65023: "center port entry",
                                              65535: "right port entry" }   (from column_categories.meanings)

So the **raw data is identical to the first run**: the edits changed only the table name, the column
name, and added the ``MeaningsTable`` (value to meaning). Annotation never alters the events
themselves; it makes them legible. A bare marker (``PC0_``) is unchanged by this edit (no
``column_categories`` to curate); a continuous column would gain a numeric column and no
``MeaningsTable``.


How to Share One Table Across Several Columns
---------------------------------------------

Still within one interface. First, see the default. With no sharing edits, each event stream keeps
the table ``get_metadata()`` seeded for it, one table per ``event_type_id``, so the two-store tank
from above writes **two separate tables**:

.. code-block:: text

    PortEntries  (EventsTable)        PC0_  (EventsTable)
    ┌───────────┬────────────┐        ┌───────────┐
    │ timestamp │ port_entry │        │ timestamp │
    ├───────────┼────────────┤        ├───────────┤
    │    12.084 │      64959 │        │     8.500 │
    │    13.553 │      65535 │        │    19.310 │
    │       ... │        ... │        │       ... │
    └───────────┴────────────┘        └───────────┘

That is fine when the event streams are genuinely separate kinds of event. But often several of a
tank's stores belong **together**: say the ``port_entry`` codes and the ``reward`` marker are both
behavioral events you want in one table. Sharing is one edit: point each column's
``table_metadata_key`` at a shared ``EventTables`` entry.

.. code-block:: python

    metadata = interface.get_metadata()

    # Define the shared table once (or reuse a seeded entry and rename it).
    metadata["Events"]["EventTables"]["behavior"] = {
        "table_name": "BehavioralEvents",
        "description": "Port entries and rewards in one shared table.",
    }

    # Point both columns at it instead of their own default tables.
    columns = metadata["Events"]["behavioral_session"]["event_columns"]
    columns["PtAB"]["column_name"] = "port_entry"
    columns["PtAB"]["table_metadata_key"] = "behavior"
    columns["PC0_"]["column_name"] = "reward"
    columns["PC0_"]["table_metadata_key"] = "behavior"

    nwbfile = interface.create_nwbfile(metadata=metadata)

Both columns now land in one ``BehavioralEvents`` table. Because the two event streams have
*different* timestamps (a port entry and a reward happen at different moments), sharing a table gives
a **wide** table: one column per event stream, with a value only in the rows where that event stream
fired and blanks elsewhere:

.. code-block:: text

    BehavioralEvents  (EventsTable in /acquisition)
    ┌───────────┬────────────┬────────┐
    │ timestamp │ port_entry │ reward │
    ├───────────┼────────────┼────────┤
    │     8.500 │            │      X │   <- a reward event: only the reward column is set
    │    12.084 │      64959 │        │   <- a port entry: only port_entry is set
    │    13.553 │      65535 │        │
    │    19.310 │            │      X │
    │       ... │        ... │    ... │
    └───────────┴────────────┴────────┘

That sparse, wide shape is the natural result of a shared table whose event streams do not share
rows. Reshaping it into a **tidy** table (one row per event, the event stream's identity moved into
an ``event_type`` column) is a separate conversion option, not part of the metadata. Sharing a table
across columns from *different* interfaces works exactly the same way and is shown next; the only
difference is the
columns live under different ``metadata_key`` s.


How to Annotate Multiple Events Interfaces
------------------------------------------

A single conversion often runs several event interfaces, here a TDT tank and a SpikeGLX NIDQ stream,
wired together in an ``NWBConverter``. Each interface gets its own ``metadata_key``, and that key is
what keeps them apart: two sources can expose the **same** ``event_type_id`` (two tanks both with a
store ``PtAB``, two boards both with a line ``XD0``), and the ``metadata_key`` namespaces each
interface's ``event_columns`` block so those identical ids never clash.

.. code-block:: python

    from neuroconv.datainterfaces import TDTEventsInterface, SpikeGLXNIDQInterface
    from neuroconv import NWBConverter

    tdt_interface = TDTEventsInterface(folder_path="path/to/tank", metadata_key="tdt")

    # Signal-encoded interfaces also take an events-extraction config at construction
    # (which lines/levels, and how to read them); elided here to keep the focus on metadata.
    nidq_interface = SpikeGLXNIDQInterface(file_path="path/to/run.nidq.bin", metadata_key="nidq")

    converter = NWBConverter(data_interfaces={"tdt": tdt_interface, "nidq": nidq_interface})
    metadata = converter.get_metadata()

    # Each interface's columns live under its own metadata_key, so identical event_type_ids
    # from different interfaces never collide: metadata["Events"]["tdt"] vs ["nidq"].
    metadata["Events"]["tdt"]["event_columns"]["PtAB"]["column_name"] = "port_entry"
    metadata["Events"]["nidq"]["event_columns"]["XD0"]["column_name"] = "camera_frame"

So far each column keeps its own default table, giving separate tables per interface. Sharing a
table **across** interfaces works exactly like sharing within one (above): point each column's
``table_metadata_key`` at a shared ``EventTables`` entry. The only difference is the columns live
under different ``metadata_key`` s; the shared ``EventTables`` block is global, so columns from any
interface can route into it.

.. code-block:: python

    # A shared table for events from both interfaces.
    metadata["Events"]["EventTables"]["behavior"] = {
        "table_name": "BehavioralEvents",
        "description": "Rewards (TDT) and licks (NIDQ) sharing one table across interfaces.",
    }

    # A TDT reward marker and a NIDQ lick line, routed into the one shared table.
    metadata["Events"]["tdt"]["event_columns"]["PC0_"]["column_name"] = "reward"
    metadata["Events"]["tdt"]["event_columns"]["PC0_"]["table_metadata_key"] = "behavior"
    metadata["Events"]["nidq"]["event_columns"]["XD1"]["column_name"] = "lick"
    metadata["Events"]["nidq"]["event_columns"]["XD1"]["table_metadata_key"] = "behavior"

    converter.run_conversion(nwbfile_path="session.nwb", metadata=metadata)
    # -> one BehavioralEvents table holding the reward and lick columns from the two interfaces.

As with a single-interface shared table, the result is a wide table (one column per source, sparse across
rows since the event streams have different timestamps); the tidy reshape is a separate conversion
option.

If you have a use case not covered here, please open an issue at `NeuroConv GitHub Issues
<https://github.com/catalystneuro/neuroconv/issues>`_.
