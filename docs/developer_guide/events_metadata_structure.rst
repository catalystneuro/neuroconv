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
turning on), so an interface can expose multiple event types; and an experiment may record events
with several acquisition systems at once, so a conversion can run multiple events interfaces
together. The purpose of the events metadata dict is to let the user specify how the data and
metadata is written under such various configurations.

For user-facing instructions on annotating events, see :ref:`annotate_events_metadata`.

Throughout this document, ``event_type_id`` means whatever the source format (or its reader) uses to
identify a type of event (licking, a camera frame onset, a reward). It may be a human-readable
label, an internal numeric code, or a store or line name (e.g. a TDT store ``PtAB``, a NIDQ line
``XD0``); its form varies by format.

Design Principles
-----------------

The events metadata system follows the same core principles as the ophys and ecephys systems (see
:ref:`ophys_metadata_structure`), specialized to discrete events:

1. **Dictionary-Based Organization.** Everything lives under ``metadata["Events"]``, dict-keyed at
   every level: each interface is namespaced by its ``metadata_key``, each event type within it by
   its ``event_metadata_key`` (defaulting to the source's ``event_type_id``) under an ``event_types``
   block, and each event type names the output table it joins via ``table_metadata_key``. Keying every level lets several interfaces
   run in one conversion without clashing, and is consistent with the rest of the NeuroConv metadata.

   .. code-block:: python

       metadata["Events"] = {
           "behavioral_session": {                       # an interface, keyed by its metadata_key
               "event_types": {
                   "licking": {                          # an event type, keyed by its event_metadata_key
                       "table_metadata_key": "behavior",   # the table this event type is written into
                       "columns": {                      # value columns, keyed by field_id
                           "port": {"column_name": "lick", "description": "Lick detections."},
                       },
                   },
                   "frame_start": {                      # a second event type in the same interface
                       "table_metadata_key": "frame_start",
                       "columns": {},                    # a bare marker: timestamps only
                   },
               },
           },
       }

   The three keys are detailed in :ref:`The metadata_key Parameter <events_metadata_key_param>`,
   :ref:`The event_metadata_key <events_event_metadata_key>`, and :ref:`The table_metadata_key
   <events_handling_tables>`.

2. **EventTables are top-level and shared.** Output tables are declared in a global ``EventTables``
   block at the top level of ``metadata["Events"]`` (not under any interface), so any event type from
   any interface can route into any table. By default each event type gets its own table. See
   :ref:`The table_metadata_key <events_handling_tables>`.

3. **Categorical values and the MeaningsTable.** A categorical column's value vocabulary , the
   ``labels`` shown for each raw value and the ``meanings`` that become a ``MeaningsTable`` , is set
   per column via ``column_categories``. See :ref:`The event_metadata_key <events_event_metadata_key>`.

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
            "event_types": {
                "PtAB": {                             # one entry per event_type_id (a TDT epoc store code)
                    "table_metadata_key": "port_entries",   # this event type is written to this table
                    "columns": {
                        "strobe": {                   # one value column, keyed by field_id
                            "column_name": "port_entry",
                            "description": "Nose-poke port entry, coded by port.",
                            "column_categories": {
                                # keys are the raw strobe values the hardware latched (TDT port codes)
                                "labels":   {64959: "left", 65023: "center", 65535: "right"},
                                "meanings": {64959: "left port entry", 65023: "center port entry", 65535: "right port entry"},
                            },
                        },
                    },
                },
                "PC0_": {                             # a second store: a bare marker (constant strobe value 1.0)
                    "table_metadata_key": "behavior",       # this event type is written to this table
                    "columns": {},                    # timestamps only
                },
            },
        },

        "nidq_session": {                            # interface 2 (a SpikeGLX NIDQ stream)
            "event_types": {
                "XD1": {                              # a digital line read as a bare marker
                    "table_metadata_key": "behavior",       # this event type is written to this table
                    "columns": {},
                },
                "XD0": {
                    "table_metadata_key": "camera_frames",  # this event type is written to this table
                    "columns": {},
                },
            },
        },
    }


.. _events_metadata_key_param:

The metadata_key Parameter
--------------------------

Events interfaces accept a ``metadata_key`` string parameter that selects the interface's ``event_types``
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
includes the namespace: ``metadata["Events"][metadata_key]["event_types"][...]``.

An interface's event types are nested inside an ``event_types`` block (rather than sitting directly
under the ``metadata_key``), which reserves the per-interface block so another kind of per-interface
data could be added alongside the event types in the future without reshaping the dict.


.. _events_event_metadata_key:

The event_metadata_key
----------------------

Inside an interface's ``event_types`` block, each event type is keyed by an ``event_metadata_key``,
which defaults to its ``event_type_id``. It is **what you use to reach and edit one event type's
metadata**, and its entry holds the type's table routing and its value columns:

.. code-block:: python

    metadata["Events"]["behavioral_session"]["event_types"]["licking"] = {
        "table_metadata_key": "behavior",       # which table this event type is written into
        "columns": {                            # value columns, keyed by field_id
            "port": {
                "column_name": "lick",          # the column header in the output table
                "description": "Lick detections, left or right port.",
                "column_categories": {          # present only for a categorical column
                    "labels":   {1: "left", 2: "right"},
                    "meanings": {1: "left lick", 2: "right lick"},
                },
            },
        },
    }

An entry holds two fields:

- ``table_metadata_key`` , which output table the event type is written into (see :ref:`The
  table_metadata_key <events_handling_tables>`).
- ``columns`` , the value columns of the event type, keyed by ``field_id``. The absence of the column entry indicates
 a timestamps-only event whereas column is used for events with payload.

Each column entry holds:

- ``column_name`` , the column header in the output table (default: the source's field label if it
  carries one, else the ``field_id``).
- ``description`` , a free-text description of the column, written as its ``VectorData`` description
  in the output table (default: a generic description naming the source).
- ``column_categories`` , the column's value vocabulary (see below); present only for a categorical
  column.

The column's value vocabulary is ``column_categories``:

- **Presence means categorical.** ``column_categories = {labels, meanings}`` declares the column's
  values. The **keys of both maps are the raw values the source emits** (a TDT strobe value, a
  decoded code, a line state, e.g. the port codes ``64959/65023/65535`` above). ``labels`` map each
  raw value to a display label, and ``meanings`` map each raw value to a description. Both are
  optional.
- **Absence means not categorical.** Omit ``column_categories`` and a numeric column is continuous
  (raw values written as a plain numeric column) and a string column is free-text.

.. _events_handling_tables:

The table_metadata_key
----------------------

The third key, ``table_metadata_key``, identifies an output table. Unlike the other two keys (which
*nest* the columns under them), this one is a **reference**: each event column names, in its
``table_metadata_key`` field, the table it is written into.

The tables themselves are declared in the global ``EventTables`` block, at the top level of
``metadata["Events"]`` (separate from any interface's block):

.. code-block:: python

    metadata["Events"]["EventTables"] = {
        "behavior":    {"table_name": "BehavioralEvents", "description": "Licking events."},
        "frame_start": {"table_name": "FrameStart",       "description": "Imaging frame-start pulses."},
    }

``EventTables`` is the only reserved
key under ``metadata["Events"]`` (every other top-level key is an interface ``metadata_key``). Each
entry's ``table_name`` is the NWB object name (CamelCase) of the output ``EventsTable``; the entry's
key is its ``table_metadata_key``, a plain id used only to reference the table from columns. This
metadata contract is fixed; the object the writer produces from it is covered in the migration
section below.

By default ``get_metadata()`` seeds one ``table_metadata_key`` per event type, so each event type
gets its own table and the common cases need no edits. To put several event types in one table
instead, **share by linking**: point each one's ``table_metadata_key`` at one shared
``EventTables`` entry (define it if it is not a seeded default); see
:ref:`annotate_events_shared_table` for a worked example. The same edit shares a table across
interfaces, since the table block is global. The writer then pools the shared types' events into one
**time-sorted** table and adds an ``event_type`` discriminator column naming each row's event type,
so a bare marker (which adds no value column) keeps its identity; each event type contributes only
the value columns it carries, filled on its own rows and empty on the others.

.. _events_multi_value:

Handling events with multiple values per event
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In most acquisition systems an event is either a **pure timestamp** (a bare marker, e.g. a TTL pulse
or a reward) or a timestamp with a **single value** (a code or label, e.g. a port code). Both write
straightforwardly. Every event table has a built-in ``timestamp`` column, so a pure timestamp needs
no value column at all, it is just an ``EventsTable`` with its ``timestamp`` column and nothing else
(empty ``columns``). A single value adds one value column alongside ``timestamp`` (one ``columns``
entry).

Some events, though, carry **more than one value per occurrence** (a structured payload, e.g. a
Spike2 TextMark tagged with both a numeric ``marker`` code and a ``text`` string). Here each field is
its own ``columns`` entry, keyed by its ``field_id`` (the field name when the source provides
one, otherwise a numeric index), all under the one event type:

.. code-block:: python

    # one event type, two fields -> two columns on one table
    "TextMark": {
        "table_metadata_key": "textmark",
        "columns": {
            "marker": {"column_name": "marker"},
            "text":   {"column_name": "text"},
        },
    }

Because the fields come from the *same* event, they share its timestamps and the columns sit on the
same rows of one table. Each field is named and described independently (its own ``column_name`` /
``description`` / ``column_categories``).


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
