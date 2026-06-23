.. _events_metadata_structure:

Events Metadata Structure
=========================

This document describes the dict-based events metadata system in NeuroConv, used by the
discrete-events interfaces (TTL lines, strobes, epocs, markers). It is intended as a reference for
developers contributing new events interfaces or modifying existing ones, and to document the design
decisions behind the format.

A discrete event is a timestamp with an optional payload (a code, a category, a measurement),
produced by an acquisition system such as a TDT store, a NIDQ line, or a marker channel. A single
source file may contain more than one **event type** (a licking behavior, a frame start, a photodiode
turning on), so an interface can expose multiple event types. The source format (or its reader)
identifies each event type by an **event_type_id**, a label or a numeric code such as a TDT store
name (``PtAB``) or a NIDQ line (``XD0``). And an experiment may record events with several
acquisition systems at once, so a conversion can run multiple events interfaces together. The purpose of the events metadata dict is to let the user specify how the data and metadata is
written under such various configurations.

For user-facing instructions on annotating events, see :ref:`annotate_events_metadata`.


Design Principles
-----------------

The events metadata system follows the same core principles as the ophys and ecephys systems (see
:ref:`ophys_metadata_structure`), specialized to discrete events:

1. **Dictionary-Based Organization.** Everything related to events is written under
   ``metadata["Events"]`` and uses a dict-based organization at every level. All the event types
   coming from one interface live under the same namespace, its ``metadata_key``, which lets several
   interfaces run in one conversion without their metadata clashing (and is consistent with the rest
   of the NeuroConv metadata). Within each interface there is one ``event_metadata_key`` per event
   type (one for licking, another for frame start), which lets every event type be referenced and
   customized individually. Each ``event_metadata_key`` defaults to its ``event_type_id``.

   .. code-block:: python

       metadata["Events"] = {
           "behavioral_session": {                       # an interface, keyed by its metadata_key
               "event_columns": {
                   "licking": {                          # an event type, keyed by its event_metadata_key
                       "column_name": "lick",
                       "description": "Lick detections.",
                       "table_metadata_key": "behavior",
                   },
                   "frame_start": {                      # a second event type in the same interface
                       "column_name": "frame_start",
                       "description": "Imaging frame-start pulses.",
                       "table_metadata_key": "frame_start",   # write this event into this table
                   },
               },
           },
       }

   Finally, events are written to tables, and each table is identified by a ``table_metadata_key``.
   That key gives every output table an identity so tables can be referenced without clashing; on
   each event column (above) it indicates which table that event is written into.

2. **EventTables are a top-level entry, one table per event type by default.** Each output table's
   name and description are specified at the top level of ``metadata["Events"]``, under the reserved
   ``EventTables`` key, separate from any interface's block:

   .. code-block:: python

       metadata["Events"]["EventTables"] = {
           "behavior":    {"table_name": "BehavioralEvents", "description": "Licking events."},
           "frame_start": {"table_name": "FrameStart",       "description": "Imaging frame-start pulses."},
       }

   ``EventTables`` is shared across interfaces: because it sits at the top level and not under any
   ``metadata_key``, a column from any interface can route into any table. By default every event
   type creates its own single-column table, so a single interface may write more than one table.
   Two cases put several columns in one table: an explicit **share** (point columns at the same
   ``table_metadata_key``), and the one **exception** where it happens automatically, an event type
   with a multi-value payload. Both are detailed in :ref:`The table_metadata_key
   <events_handling_tables>`.

3. **Categorical labels and the MeaningsTable** are controlled through the event column entry,
   ``metadata["Events"][metadata_key]["event_columns"][event_metadata_key]["column_categories"]``:

   .. code-block:: python

       column = metadata["Events"]["behavioral_session"]["event_columns"]["licking"]
       column["column_categories"] = {
           "labels":   {1: "left", 2: "right"},                 # remap each raw source value for display
           "meanings": {1: "left lick", 2: "right lick"},       # a description per value (the MeaningsTable)
       }

   When the data is categorical, the raw values the source emits can be remapped here, via ``labels``,
   to something more meaningful for the end user, and ``meanings`` supplies a description per value
   (which becomes the ``MeaningsTable``). The column itself ends up in the ``EventsTable`` keyed by
   that event's ``table_metadata_key``.

Metadata Structure Overview
---------------------------

The complete events metadata structure, with two interfaces (a TDT tank and a SpikeGLX NIDQ stream),
each contributing two event columns, and a mix of shared and own-table layouts. Store names and
values are real: ``PtAB`` port codes and the constant-value ``PC0_`` marker are from TDT demo tanks.

.. code-block:: python

    metadata["Events"] = {

        "EventTables": {                              # GLOBAL: the output tables, shared across interfaces
            "port_entries": {
                "table_name": "PortEntries",          # the NWB object name (CamelCase)
                "description": "Nose-poke port entries.",
            },
            "behavior": {
                "table_name": "BehavioralEvents",
                "description": "Rewards and licks sharing one table across interfaces.",
            },
            "camera_frames": {
                "table_name": "CameraFrames",
                "description": "Camera exposure pulses.",
            },
        },

        "tdt_session": {                              # interface 1 (a TDT tank), keyed by its metadata_key
            "event_columns": {
                "PtAB": {                             # one entry per event_type_id (a TDT epoc store code)
                    "column_name": "port_entry",
                    "description": "Nose-poke port entry, coded by port.",
                    "column_categories": {
                        # keys are the raw strobe values the hardware latched (TDT port codes)
                        "labels":   {64959: "left", 65023: "center", 65535: "right"},
                        "meanings": {64959: "left port entry", 65023: "center port entry", 65535: "right port entry"},
                    },
                    "table_metadata_key": "port_entries",   # this column is written to this table
                },
                "PC0_": {                             # a second store: a bare marker (constant strobe value 1.0)
                    "column_name": "reward",
                    "description": "Reward delivery.",
                    "table_metadata_key": "behavior",       # this column is written to this table
                },
            },
        },

        "nidq_session": {                            # interface 2 (a SpikeGLX NIDQ stream)
            "event_columns": {
                "XD1": {                              # a digital line read as a bare marker
                    "column_name": "lick",
                    "description": "Lick spout contact.",
                    "table_metadata_key": "behavior",       # this column is written to this table
                },
                "XD0": {
                    "column_name": "camera_frame",
                    "description": "Camera exposure pulse.",
                    "table_metadata_key": "camera_frames",  # this column is written to this table
                },
            },
        },
    }


The metadata_key Parameter
--------------------------

Events interfaces accept a ``metadata_key`` string parameter that selects the interface's ``event_columns``
block. It is **keyword-only** and defaults to ``None``.

.. code-block:: python

    class SomeEventsInterface(BaseDataInterface):
        def __init__(self, *, metadata_key: Optional[str] = None, **source_data):
            self.metadata_key = metadata_key
            ...

When ``None``, the interface derives a unique, source-derived snake_case key from the source (the
tank or block name), so even two instances of the *same* interface in one converter get distinct
keys with zero configuration. This is more robust than a hardcoded default (a fixed
``"SpikeGLXNIDQ"`` would collide the moment two NIDQ interfaces share a converter). An explicit
value lets the caller pick a stable, readable name, or deliberately reuse a key.

Its **role is disambiguation across interfaces**: every interface's columns live under its own
``metadata_key``, so two interfaces can expose the same ``event_type_id`` (two tanks both with a
store ``PtAB``, two boards both with a line ``XD0``) and never collide, because the full address
includes the namespace: ``metadata["Events"][metadata_key]["event_columns"][...]``.

An interface's event types are nested inside an ``event_columns`` block (rather than sitting directly
under the ``metadata_key``). This makes it concrete that they are written as columns of an events
table, and it reserves the per-interface block so another kind of per-interface data could be added
alongside the columns in the future without reshaping the dict.


The event_metadata_key
----------------------

Inside an interface's block, each event type (one event column) is keyed by an
``event_metadata_key``, which defaults to its ``event_type_id``. It is **what you use to reach and
edit one event type's metadata**, and one entry holds everything about that event type's column:

.. code-block:: python

    metadata["Events"]["behavioral_session"]["event_columns"]["licking"] = {
        "column_name": "lick",                  # the column header in the output table
        "description": "Lick detections, left or right port.",
        "column_categories": {                  # present only for a categorical column
            "labels":   {1: "left", 2: "right"},
            "meanings": {1: "left lick", 2: "right lick"},
        },
        "table_metadata_key": "behavior",       # which table this column is written into
    }

The fields:

- ``column_name`` , the column header in the output table (default: the source's label if it carries
  one, else the ``event_type_id``).
- ``description`` , a free-text description of the event type, written as the column's
  ``VectorData`` description in the output table (default: a generic description naming the source).
- ``column_categories`` , the column's value vocabulary (see below); present only for a categorical
  column.
- ``table_metadata_key`` , which output table the column joins (see :ref:`The table_metadata_key
  <events_handling_tables>`).

The column's value vocabulary is ``column_categories``:

- **Presence means categorical.** ``column_categories = {labels, meanings}`` declares the column's
  values. The **keys of both maps are the raw values the source emits** (a TDT strobe value, a
  decoded code, a line state, e.g. the port codes ``64959/65023/65535`` above). ``labels`` map each
  raw value to the cell text written now (the interim ``LabeledEvents.labels``), and ``meanings``
  map each raw value to a description (the ``MeaningsTable``, at the NWBEP001 migration). Both are
  optional.
- **Absence means not categorical.** Omit ``column_categories`` and a numeric column is continuous
  (raw values written as a plain numeric column) and a string column is free-text.

.. _events_handling_tables:

The table_metadata_key
----------------------

The third key, ``table_metadata_key``, identifies an output table. Unlike the other two keys (which
*nest* the columns under them), this one is a **reference**: each event column names, in its
``table_metadata_key`` field, the table it is written into.

The tables themselves live in the global ``EventTables`` block. ``EventTables`` is the only reserved
key under ``metadata["Events"]`` (every other top-level key is an interface ``metadata_key``). Each
entry's ``table_name`` is the NWB object name (CamelCase) of the output ``EventsTable``; the entry's
key is its ``table_metadata_key``, a plain id used only to reference the table from columns. This
metadata contract is fixed; the object the writer produces from it is covered in the migration
section below.

A column joins a table by naming it in its ``table_metadata_key`` field. This is the third and last
key, and the full path from an ``event_type_id`` to an output table runs through all three:

.. code-block:: text

    metadata["Events"]
        |
        |-- "tdt_session"                 <- metadata_key       (which interface's block)
        |     `-- "event_columns"
        |           `-- "PtAB"            <- event_metadata_key (which column; = the event_type_id)
        |                 |-- "column_name": "port_entry"
        |                 `-- "table_metadata_key": "port_entries"  --,
        |                                                             |  (the join: this column
        `-- "EventTables"                                            |   names the table it enters)
              `-- "port_entries"          <- table_metadata_key  <---'
                    |-- "table_name": "PortEntries"   (the NWB object name)
                    `-- "description": ...

The first two keys are *containment* (the column lives inside the interface's block); the third is a
*reference* (the column points sideways to a global table). That one reference is the whole sharing
mechanism. Unlike ophys ``MicroscopySeries`` (which carries ``imaging_plane_metadata_key`` to point
at its plane), an ``EventTables`` entry does **not** list its member columns; each column names the
table it joins. The relationship is many-to-one, so the link lives on the column, not the table.
Because ``EventTables`` is global (not nested under any ``metadata_key``), a column from any
interface can route into any table, which is the cross-interface sharing mechanism.

By default ``get_metadata()`` seeds one ``table_metadata_key`` per event type, so each event type
gets its own table and the common cases need no edits. To put several event types in one table
instead, **share by linking**: point each column's ``table_metadata_key`` at one shared
``EventTables`` entry (define it if it is not a seeded default). The same edit shares a table across
interfaces, since the table block is global. Because the shared types have different timestamps, the
result is a **wide, non-tidy table** (one column per type, sparse across rows); reshaping it into a
tidy table (one row per event, the type in an ``event_type`` column) is a separate conversion
option, not part of this metadata. See :ref:`annotate_events_metadata` for the worked example.

.. _events_multi_value:

The exception: multiple values per event
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sharing is usually the user *choosing* to put several event types in one table. There is one case
where several columns share a table **automatically**: an event type with a multi-value payload (a
structured event, e.g. one tagged with both a code and a text). Each field becomes **its own**
``event_columns`` entry, with its own ``event_metadata_key`` (the field name when the source
provides one, otherwise a numeric index), and the entries are seeded with the **same**
``table_metadata_key`` so they are written as side-by-side columns of one table:

.. code-block:: python

    # one event type, two fields -> two entries, same table
    "event_columns": {
        "marker": {"column_name": "marker", "table_metadata_key": "textmark"},
        "text":   {"column_name": "text",   "table_metadata_key": "textmark"},
    }

Unlike a user-chosen shared table, the fields come from the *same* event, so they share its
timestamps and the columns sit on the same rows, the table is tidy by construction, not
wide-and-sparse. Each field is named
and described independently (its own ``column_name`` / ``description`` / ``column_categories``). The
common single-field case is just the N=1 instance: one entry, one column.


When Objects Are Created
------------------------

The ``EventTables`` *entries* exist in the metadata dict from the start: ``get_metadata()`` seeds
one default entry per column (Principle 5), and the user may add more. The NWB table *objects* are
created from those entries at ``add_to_nwbfile`` time. The rules mirror the ophys/ecephys pipelines:

1. **Only referenced tables are written.** An ``EventTables`` entry that no column points at is not
   turned into an object. The default entries are always referenced (each seeded column points at
   its own), so they are written; this rule prunes the *extra* entries a shared configuration may
   predefine but a given session does not use.
2. **Defaults are seeded, not conjured.** ``get_metadata()`` already put one ``EventTables`` entry
   per column and set each column's ``table_metadata_key`` to it, so a zero-config run produces one
   table per column with no write-time invention. (To rename or describe a default table, edit its
   seeded ``EventTables`` entry; the user never has to create the default ones.)
3. **Shared tables are created once.** When several columns point at one ``table_metadata_key``, the
   table is created by whichever interface writes first, and later columns append to it.

Table keys are independent of any interface's ``metadata_key``: a ``table_metadata_key`` such as
``"behavior"`` need not match any interface's key. No interface owns a table; it is created at write
time by whichever column first references it. As with the ophys shared-YAML workflow, this lets a
single shared configuration hold all output tables for a project, with the per-session conversion
code setting ``table_metadata_key`` references to choose which columns share which table.


Migration: from ndx-events 0.2.x to fully released NWBEP001
-----------------------------------------------------------

The metadata contract above is the **target**, shaped for the native NWBEP001 ``EventsTable``. The
interim writer runs against ``ndx-events`` 0.2.x, which is far less expressive, so part of the
contract is exercised today and part is forward-looking. Only the writer changes at migration; this
metadata dict never does.

**What the current (ndx-events 0.2.x) writer does.** It writes **one container per column** into
``/acquisition``, not a shared table, and keeps only what 0.2.x can represent (timestamps and a
label legend), ignoring the richer payload:

- A categorical column (``column_categories`` present) becomes a ``LabeledEvents``: the raw values
  are recoded to dense ints in ``LabeledEvents.data``, and ``labels`` become
  ``LabeledEvents.labels``. The ``meanings`` entry has no native home yet, so it is appended to the
  object ``description`` as a stopgap.
- A bare marker (no ``column_categories``) becomes an ``Events`` (timestamps only).

Metadata used now, and how its meaning shifts at migration:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - field
     - now (``ndx-events`` 0.2.x)
     - at migration (NWBEP001 ``EventsTable``)
   * - ``column_name``
     - the **object name** of the per-column ``LabeledEvents``/``Events`` (each column is its own container)
     - a real **column** in a shared ``EventsTable``
   * - ``description``
     - the per-column object's ``description`` (with ``meanings`` appended to it as a stopgap, see below)
     - the column's ``VectorData`` description in the shared ``EventsTable``
   * - ``column_categories.labels``
     - ``LabeledEvents.labels`` (the string legend)
     - the categorical column's cell values
   * - ``column_categories.meanings``
     - **appended to the column's** ``description`` as a stopgap (no table for them yet)
     - a real ``MeaningsTable`` linked to the column
   * - ``table_metadata_key``
     - **inert**: each column is its own container, so sharing one table across several columns is a no-op (the routing is recorded but not realized)
     - selects the shared ``EventsTable`` the column joins (real table sharing)

Forward-looking parts (in the contract, but not meaningful on 0.2.x):

- **Table sharing.** ``table_metadata_key`` directing several columns into one table has no effect
  on 0.2.x (there is no shared table; columns stay separate containers). It is recorded for the
  future and becomes real at migration.
- ``meanings`` **as a MeaningsTable.** Today they only ride along in the object ``description``
  text.
- **Durations.** ``LabeledEvents``/``Events`` have no duration slot, so durated events are written
  as onsets only; a ``DurationVectorData`` column appears at migration.
- **Continuous payloads.** 0.2.x has no flat numeric-per-event column: ``Events`` carries no values
  and ``LabeledEvents.data`` holds only unsigned-integer indices into the text ``labels`` (the spec
  dtype of ``labels`` is ``text``). So a continuous column (e.g. a frequency in Hz) is written as a
  ``LabeledEvents`` with **its values stringified**, one label per distinct value. This is lossy and
  semantically off (a measurement written as if it were a category), but the value is *present in the
  file* and recoverable, which is preferable to dropping it. The typed value is also kept on the
  internal representation, so at migration the same conversion writes it as a real numeric column in
  the ``EventsTable`` (no string round-trip needed).

At the NWBEP001 migration the per-column containers collapse into the columns and rows of shared
``EventsTable`` s, ``meanings`` graduate to ``MeaningsTable`` s, durations and continuous values get
real columns, and ``table_metadata_key`` sharing finally produces single shared tables, all by
swapping the writer, with the metadata dict unchanged.
