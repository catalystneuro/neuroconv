.. _events_metadata_structure:

Events Metadata Structure
=========================

This document describes the architecture of the dict-based events metadata system in NeuroConv, used by the discrete-events interfaces (TTL lines, strobes, epocs, markers). It is intended for developers who are contributing new events interfaces or modifying existing ones.

For user-facing documentation on how to annotate events, see :ref:`annotate_events_metadata`.

A discrete event is a timestamp with an optional payload (a code, a category, a measurement), produced by a source stream (a TDT store, a NIDQ line, a marker channel). This document is about the metadata dict that names those events and says which output table each one is written into; it is not about reading the bytes (the interface's job). Two ideas carry the whole format: each event source becomes one **event column** keyed by its ``event_type_id``, and columns are routed, one or many, into shared **output tables**.


Design Principles
-----------------

The events metadata system follows the same core principles as the ophys and ecephys systems (see :ref:`ophys_metadata_structure`), specialized to discrete events:

1. **Dictionary-Based Organization.** The dict is keyed at every level, so a component is reached by name. A source produces one or more event streams, each a series of ``(timestamp, value)`` pairs (a TDT store, a NIDQ line, a marker channel), and each stream becomes one event column addressed by two keys: the ``metadata_key`` (the interface's namespace, so two interfaces' streams never collide) and, inside it, the ``event_metadata_key`` (the handle you use to reach and edit that stream's metadata, defaulting to the source's ``event_type_id``, e.g. the TDT store ``PtAB`` or the NIDQ line ``XD0``). Output tables are keyed by a separate ``table_metadata_key``.

   .. code-block:: python

       # metadata_key = which interface; event_metadata_key = which event stream's column within it
       metadata["Events"][metadata_key]["event_columns"][event_metadata_key]["column_name"] = "port_entry"

2. **Consistent metadata_key Across Interfaces.** Every events interface uses a single ``metadata_key`` that namespaces its ``event_columns`` block, so identical ``event_type_id`` s coming from different interfaces (two TDT tanks both exposing ``PtAB``; two NIDQ boards both exposing ``XD0``) never collide. This matches the ophys/ecephys convention.

3. **Explicit References.** Each event column declares which output table it joins via a ``table_metadata_key`` field pointing at a global ``EventTables`` entry. This single reference is how grouping (within or across interfaces) is expressed.

4. **Global EventTables.** Output tables are stored in a global block (``metadata["Events"]["EventTables"]``), shared across interfaces, the events analogue of top-level ``Devices``. Because the tables are global, any interface's column can route into any table, which is the mechanism for pooling events from several interfaces into one table.

5. **Provenance-First get_metadata().** ``get_metadata()`` returns what is extracted or derived from the source: the enumerated ``event_type_id`` s (one event column each) and the seeded defaults. Every default that is *derivable* is present in the dict, so the user sees and edits it rather than discovering hidden write-time behavior: ``column_name`` defaults to the source's label if it carries one, else the ``event_type_id``; ``column_categories.labels`` keys are seeded from the observed raw values; each column's ``table_metadata_key`` defaults to its own ``event_type_id``, and the matching default ``EventTables`` entry (one table per column, named after the source) is seeded too, so a column never points at a table that is not in the dict. What ``get_metadata()`` does not decide is any layout that depends on a user choice (pooling columns into one table); that is the user's edit, applied before write.


Metadata Structure Overview
---------------------------

The complete events metadata structure, with two interfaces (a TDT tank and a SpikeGLX NIDQ stream), each contributing two event columns, and a mix of pooled and own-table grouping. Store names and values are real: ``PtAB`` port codes and the constant-value ``PC0_`` marker are from TDT demo tanks.

.. code-block:: python

    metadata["Events"] = {

        "EventTables": {                              # GLOBAL: the output tables, shared across interfaces
            "port_entries": {
                "table_name": "PortEntries",          # the NWB object name (CamelCase)
                "description": "Nose-poke port entries.",
            },
            "behavior": {
                "table_name": "BehavioralEvents",
                "description": "Rewards and licks, pooled across interfaces.",
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
                    "column_categories": {
                        # keys are the raw strobe values the hardware latched (TDT port codes)
                        "labels":   {64959: "left", 65023: "center", 65535: "right"},
                        "meanings": {64959: "left port entry", 65023: "center port entry", 65535: "right port entry"},
                    },
                    "table_metadata_key": "port_entries",   # this column is written to this table
                },
                "PC0_": {                             # a second store: a bare marker (constant strobe value 1.0)
                    "column_name": "reward",
                    "table_metadata_key": "behavior",       # this column is written to this table
                },
            },
        },

        "nidq_session": {                            # interface 2 (a SpikeGLX NIDQ stream)
            "event_columns": {
                "XD1": {                              # a digital line read as a bare marker
                    "column_name": "lick",
                    "table_metadata_key": "behavior",       # this column is written to this table
                },
                "XD0": {
                    "column_name": "camera_frame",
                    "table_metadata_key": "camera_frames",  # this column is written to this table
                },
            },
        },
    }

This layout shows the two grouping patterns the dict format expresses, side by side:

- **One table per column (default).** ``PtAB`` and ``XD0`` each point their ``table_metadata_key`` at their own ``EventTables`` entry (``port_entries``, ``camera_frames``). Zero config gives this: one table per column, named after the source.
- **Several columns pooled into one table (merge).** ``PC0_`` (the TDT reward marker) and ``XD1`` (the NIDQ lick line) both point their ``table_metadata_key`` at the shared ``behavior`` entry, so they land in one ``BehavioralEvents`` table. They come from *different* interfaces, which works because ``EventTables`` is global. This is the only edit needed to merge; reshaping the resulting wide table into a tidy one is a separate conversion option.


The metadata_key Parameter
--------------------------

Events interfaces accept a ``metadata_key`` parameter that selects the interface's ``event_columns`` block. It is **keyword-only** and defaults to ``None``.

.. code-block:: python

    class SomeEventsInterface(BaseDataInterface):
        def __init__(self, *, metadata_key: Optional[str] = None, **source_data):
            self.metadata_key = metadata_key
            ...

When ``None``, the interface derives a unique, source-derived snake_case key from the source (the tank or block name), so even two instances of the *same* interface in one converter get distinct keys with zero configuration. This is more robust than a hardcoded default (a fixed ``"SpikeGLXNIDQ"`` would collide the moment two NIDQ interfaces share a converter). An explicit value lets the caller pick a stable, readable name, or deliberately reuse a key.

Its **role is disambiguation across interfaces**: every interface's columns live under its own ``metadata_key``, so two interfaces can expose the same ``event_type_id`` (two tanks both with a store ``PtAB``, two boards both with a line ``XD0``) and never collide, because the full address includes the namespace: ``metadata["Events"][metadata_key]["event_columns"][...]``.

Inside that block, each column is keyed by an ``event_metadata_key``, which defaults to the source's ``event_type_id``. The ``event_metadata_key`` is **what you use to reach and edit one event stream's metadata** (its ``column_name``, value vocabulary, target table).

column_name and column_categories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each entry describes one column, named by ``column_name`` (default the source's label if it carries one, else the ``event_type_id``). The column's value vocabulary is ``column_categories``:

- **Presence means categorical.** ``column_categories = {labels, meanings}`` declares the column's values. The **keys of both maps are the raw values the source emits** (a TDT strobe value, a decoded code, a line state, e.g. the port codes ``64959/65023/65535`` above). ``labels`` map each raw value to the cell text written now (the interim ``LabeledEvents.labels``), and ``meanings`` map each raw value to a description (the ``MeaningsTable``, at the NWBEP001 migration). Both are optional.
- **Absence means not categorical.** Omit ``column_categories`` and a numeric column is continuous (raw values written as a plain numeric column) and a string column is free-text. A continuous column's unit currently rides in the ``column_name`` (e.g. ``frequency_hz``), pending an upstream ``unit`` attribute on numeric ``VectorData``.

``column_categories`` is the format-agnostic generalization of NIDQ's ``labels_map``. It is durable across the writer migration: ``LabeledEvents.labels`` now, a ``MeaningsTable`` later.

Multiple values per event
~~~~~~~~~~~~~~~~~~~~~~~~~~

An event can carry more than one value (a structured payload, e.g. an event tagged with both a code and a text). The convention: ``get_metadata()`` returns **one** ``event_columns`` **entry per field**, all under the **same** ``event_metadata_key`` 's stream. The fields share the event's timestamps, so they sit on the same rows, one row per event, the fields side by side as columns of one table. Each field is named and described independently (its own ``column_name`` / ``column_categories``), but they are never split into separate objects per value, and by default they route to one table together (see :ref:`the next section <events_handling_tables>`). The common single-field case is just the N=1 instance: one field, one column.


.. _events_handling_tables:

Handling Tables
---------------

Output tables live in the global ``EventTables`` block. ``EventTables`` is the only reserved key under ``metadata["Events"]`` (every other top-level key is an interface ``metadata_key``). Each entry's ``table_name`` is the NWB object name (CamelCase); the entry's key is its ``table_metadata_key``, a plain id. The written object is version-specific: an ``ndx-events`` 0.2.x container (``Events`` / ``LabeledEvents``) on the interim writer, a native ``EventsTable`` after the NWBEP001 migration. Only the writer changes; this metadata contract does not.

A column joins a table by naming it in its ``table_metadata_key`` field. This is the third and last key, and the full path from an ``event_type_id`` to an output table runs through all three:

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

The first two keys are *containment* (the column lives inside the interface's block); the third is a *reference* (the column points sideways to a global table). That one reference is the whole grouping mechanism. Unlike ophys ``MicroscopySeries`` (which carries ``imaging_plane_metadata_key`` to point at its plane), an ``EventTables`` entry does **not** list its member columns; each column names the table it joins. The relationship is many-to-one, so the link lives on the column, not the table. Because ``EventTables`` is global (not nested under any ``metadata_key``), a column from any interface can route into any table , which is the cross-interface merge mechanism.

**Defaults, and what they imply for tables.** ``get_metadata()`` seeds the dict so the common cases need no edits:

- **An interface with multiple values per one event** , those fields share one ``event_metadata_key`` and are seeded to **one** ``table_metadata_key``, so they land together in a single table (one row per event, the fields as columns). Tidy by construction.
- **An interface with multiple event types** , each type gets its own ``event_metadata_key`` and, by default, its own ``table_metadata_key``, so you get **one table per event type**.

In that second case you may want several types in one table instead. **Merge by linking**: point each column's ``table_metadata_key`` at one shared ``EventTables`` entry (define it if it is not a seeded default). The same edit pools columns across interfaces, since the table block is global. Because the merged types have different timestamps, the result is a **wide, non-tidy table** (one column per type, sparse across rows); reshaping it into a tidy table (one row per event, the type in an ``event_type`` column) is a separate conversion option, not part of this metadata. See :ref:`annotate_events_metadata` for the worked merge.


When Objects Are Created
------------------------

The ``EventTables`` *entries* exist in the metadata dict from the start: ``get_metadata()`` seeds one default entry per column (Principle 5), and the user may add more. The NWB table *objects* are created from those entries at ``add_to_nwbfile`` time. The rules mirror the ophys/ecephys pipelines:

1. **Only referenced tables are written.** An ``EventTables`` entry that no column points at is not turned into an object. The default entries are always referenced (each seeded column points at its own), so they are written; this rule prunes the *extra* entries a shared configuration may predefine but a given session does not use.
2. **Defaults are seeded, not conjured.** ``get_metadata()`` already put one ``EventTables`` entry per column and set each column's ``table_metadata_key`` to it, so a zero-config run produces one table per column with no write-time invention. (To rename or describe a default table, edit its seeded ``EventTables`` entry; the user never has to create the default ones.)
3. **Shared tables are created once.** When several columns point at one ``table_metadata_key``, the table is created by whichever interface writes first, and later columns append to it.

Table keys are independent of any interface's ``metadata_key``: a ``table_metadata_key`` such as ``"behavior"`` need not match any interface's key. No interface owns a table; it is created at write time by whichever column first references it. As with the ophys shared-YAML workflow, this lets a single shared configuration hold all output tables for a project, with the per-session conversion code setting ``table_metadata_key`` references to choose which columns pool where.


Migration: the current writer versus the target
------------------------------------------------

The metadata contract above is the **target**, shaped for the native NWBEP001 ``EventsTable``. The interim writer runs against ``ndx-events`` 0.2.x, which is far less expressive, so part of the contract is exercised today and part is forward-looking. Only the writer changes at migration; this metadata dict never does.

**What the current (ndx-events 0.2.x) writer does.** It writes **one container per column** into ``/acquisition``, not a shared table, and keeps only what 0.2.x can represent (timestamps and a label legend), ignoring the richer payload:

- A categorical column (``column_categories`` present) becomes a ``LabeledEvents``: the raw values are recoded to dense ints in ``LabeledEvents.data``, and ``labels`` become ``LabeledEvents.labels``.
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
   * - ``column_categories.labels``
     - ``LabeledEvents.labels`` (the string legend)
     - the categorical column's cell values
   * - ``column_categories.meanings``
     - **appended to the object** ``description`` as a stopgap (no table for them yet)
     - a real ``MeaningsTable`` linked to the column
   * - ``table_metadata_key``
     - **inert**: each column is its own container, so pooling several columns into one table is a no-op (the routing is recorded but not realized)
     - selects the shared ``EventsTable`` the column joins (real grouping/merge)

Forward-looking parts (in the contract, but not meaningful on 0.2.x):

- **Grouping / merge.** ``table_metadata_key`` pooling several columns into one table has no effect on 0.2.x (there is no shared table; columns stay separate containers). It is recorded for the future and becomes real at migration.
- ``meanings`` **as a MeaningsTable.** Today they only ride along in the object ``description`` text.
- **Durations.** ``LabeledEvents``/``Events`` have no duration slot, so durated events are written as onsets only; a ``DurationVectorData`` column appears at migration.
- **Continuous payloads.** There is no flat numeric-per-event column on 0.2.x, so a continuous column is deferred (the value is kept on the internal representation and recoverable at migration).

At the NWBEP001 migration the per-column containers collapse into the columns and rows of shared ``EventsTable`` s, ``meanings`` graduate to ``MeaningsTable`` s, durations and continuous values get real columns, and ``table_metadata_key`` grouping finally produces single pooled tables, all by swapping the writer, with the metadata dict unchanged.
