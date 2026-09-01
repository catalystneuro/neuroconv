from abc import abstractmethod
from dataclasses import dataclass, field

import numpy as np
from hdmf.common import MeaningsTable, VectorIndex
from pynwb.event import EventsTable
from pynwb.file import NWBFile

from ..._temporal_alignment import _TemporalAlignment
from ...basedatainterface import BaseDataInterface
from ...utils import to_camel_case


@dataclass
class _EventsData:
    """One event type's occurrences: the IO-independent internal representation (events taxonomy, Layer 3).

    Format-agnostic; every event source maps into this, independent of both the source format and NWB.
    Self-contained: it carries its own ``event_type_source_id`` (the type's identity) alongside the
    Extent (``timestamps`` and, for an interval type, ``durations``) and the Payload (``payload``, a
    typed field-map). :meth:`BaseEventsInterface._get_events_data_dict` returns these in a dict keyed by
    ``event_type_source_id`` for convenient grouping; that key mirrors the object's own field.

    Attributes
    ----------
    event_type_source_id : str
        The source's own handle for this event type (e.g. a TDT epoc name), meaning-free. It is the join
        key to the metadata ``event_types`` entry, whose ``event_name``/``event_description`` supply the
        human-facing name and meaning.
    timestamps : numpy.ndarray
        The event onset times, in seconds. May be empty: an event type that was recorded but had no
        occurrences (for example an enabled digital line that never toggled) is written as a zero-row
        table, which is faithful to the source (the type existed, nothing fired). Turning that normal
        experimental condition into a conversion-time error or warning is not this layer's job; whether
        an empty table is acceptable for archival is a best-practice question the NWB Inspector owns.
    durations : numpy.ndarray or None
        The per-event durations, in seconds, for an interval (durative) event type; ``None`` for a
        point event type. Within an interval type, ``NaN`` marks an event whose offset is missing.
    payload : dict[str, numpy.ndarray]
        A typed field-map of per-event values, keyed by ``field_source_id`` (the source's name for
        the field), kept in native dtype. Empty for a timestamp-only event type; one entry for a
        single value; several for a struct (multi-value) payload. Field names are scoped to their
        event type, so two streams may reuse the same field name.
    """

    event_type_source_id: str
    timestamps: np.ndarray
    durations: np.ndarray | None = None
    payload: dict[str, np.ndarray] = field(default_factory=dict)


def _holds_several_values(value) -> bool:
    """Whether one event's value for a payload field is several values rather than one.

    A string is a scalar even though it is iterable, and a numpy string scalar likewise, so the test is
    for the container types a payload actually uses to mean "more than one".
    """
    return isinstance(value, (list, tuple, set)) or (isinstance(value, np.ndarray) and value.ndim > 0)


class BaseEventsInterface(BaseDataInterface):
    """Base interface for discrete-event data written as NWB ``EventsTable`` objects.

    Concrete event interfaces (e.g. :class:`.TDTEventsInterface`) read their format-specific source
    and expose the events through :meth:`_get_events_data_dict` as :class:`_EventsData`
    records. This base owns the two pieces that do not depend on the source format: the shared
    ``Events`` metadata schema (:meth:`get_metadata_schema`) and the writer (:meth:`add_to_nwbfile`)
    that maps that internal representation, together with the metadata, into ``pynwb.event.EventsTable``
    objects inside ``nwbfile.events``.

    The metadata lives under a per-interface ``metadata_key`` as an ``event_types`` block, one entry
    per event type keyed by its ``event_type_source_id``. Each entry carries a required ``event_name``
    (seeded from the source id) and an optional ``event_description``: a source carries handles, not
    prose, so an interface that reads no description omits the key rather than inventing one, and the
    writer treats an absent description as empty. It also carries
    an optional ``table_metadata_key`` (which table it routes into, defaulting to the source id so
    each type gets its own table), and a ``columns`` map keyed by ``field_source_id`` (a payload field),
    where each column carries its output ``column_name`` and optional ``column_categories`` (relabelling
    + meanings). A single value gives one column, a struct payload several (sharing the event's rows), a
    timestamp-only type an empty ``columns``.

    ``event_name``/``event_description`` play a dual role by layout. When a type has its own table
    (**solo**, the default), they become the table's object name (CamelCased) and description. When
    several types share a ``table_metadata_key`` (**merge**), the table gets an ``event_type``
    discriminator column holding each row's ``event_name``, plus a ``MeaningsTable`` mapping those to
    ``event_description`` for the types that carry one; a merge nobody described gets no such table,
    since it would explain nothing. A merged table's own name is derived from the ``table_metadata_key``
    and its description left empty, unless an optional
    global ``EventTables`` entry (``table_name`` + ``description``) supplies them, which always has the last word;
    ``EventTables`` is only needed to name a merge (including one shared across interfaces). The writer
    is append-capable, so a second interface routing into an existing table merges into it. This
    structure is documented in the events taxonomy and PR #1774
    (https://github.com/catalystneuro/neuroconv/pull/1774).

    Subclasses must set ``self.metadata_key`` and implement :meth:`_get_events_data_dict`.
    """

    keywords = ("events",)

    def __init__(self, **source_data):
        super().__init__(**source_data)
        # Filled on the first _get_events_data_dict() call and reused thereafter, so the backend is
        # coerced once even though get_metadata, add_to_nwbfile, and alignment all read it.
        self._events_data_dict = None
        # Alignment by composition: the interface holds the offset applied to its event times at write and
        # exposes it as ``interface.alignment`` (so ``alignment.shift_times``), rather than inheriting the
        # array-shaped BaseTemporalAlignmentInterface contract, which does not fit events. Minimal (offset +
        # shift_times) for now; see neuroconv/_temporal_alignment.py.
        self.alignment = _TemporalAlignment()

    @abstractmethod
    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Return the internal event representation, keyed by ``event_type_source_id``.

        Coerces the backend (a source file or an intermediate reader, e.g. the ``tdt`` reader) into
        the standard representation on the first call, and returns the cached
        ``self._events_data_dict`` on every call after. Subclasses own both the coercion and the
        caching guard (see :class:`~neuroconv.tools.testing.mock_interfaces.MockEventsInterface` for
        the reference implementation): return ``self._events_data_dict`` early when it is not
        ``None``, otherwise build it, store it on ``self._events_data_dict``, and return it.

        Returns
        -------
        dict[str, _EventsData]
            Maps each ``event_type_source_id`` (the source's own handle for an event type, e.g. a TDT
            epoc name) to its :class:`_EventsData` (timestamps, optional durations, typed
            payload field-map). The writer joins this to the metadata by key: the ``event_types``
            entry keyed by the same ``event_type_source_id``, and each of its ``columns`` keyed by a
            ``field_source_id`` in this record's ``payload``.
        """
        raise NotImplementedError("Event interfaces must implement `_get_events_data_dict`.")

    def get_event_type_source_ids(self) -> list[str]:
        """Return the identifiers of the event types this interface reads, in the order it reports them.

        The handles :meth:`get_event_times` takes, and the keys of the metadata's ``event_types`` block.
        For a signal-encoded interface they are what ``detection_configuration`` resolves to, so a spec
        carrying an ``event_name`` is addressed by that name; for a pre-extracted one they are the
        source's own handles for its event types.

        Returns
        -------
        list of str
            The event type identifiers.
        """
        return list(self.get_metadata()["Events"][self.metadata_key]["event_types"])

    def get_event_times(self, event_type_source_id: str) -> np.ndarray:
        """Return the onset times of one configured event type, writing nothing.

        The read that a line used as a clock calls for: a camera's frame-out pulse or an alignment pulse
        is configured like any other event type, and this hands back its times so another stream can be
        aligned against them. There is no second way to state a reading here, so the array is the one the
        writer writes, by construction rather than by agreement.

        A durative reading costs nothing for this purpose, since ``high_period`` pairs each rising edge
        with the next falling one and its onsets are those rising edges, so a line configured to be
        written with its pulse widths still answers with the edge times.

        The times are this interface's **current** times, which is ``self.alignment.offset`` added to the
        source's own clock. That is what makes them usable as the input to another stream's alignment:
        pulses recorded by a device that has itself been shifted onto a session clock come back already
        on that clock, and reading them before the shift would leave them wrong by the drift with nothing
        to catch it.

        Parameters
        ----------
        event_type_source_id : str
            The identifier of the event type, as :meth:`get_event_type_source_ids` reports it. Not the
            metadata ``event_name``, which is the editable display name and which the interface never
            sees, since it hands out metadata and keeps none. Setting ``event_name`` on a spec in
            ``detection_configuration`` is what makes the identifier readable, since a named spec is
            addressed by that name.

        Returns
        -------
        numpy.ndarray
            The event onset times, in seconds, on this interface's current clock.

        Raises
        ------
        KeyError
            If no event type resolves to that identifier, naming the ones that do.
        """
        events_data_dict = self._get_events_data_dict()

        if event_type_source_id not in events_data_dict:
            raise KeyError(
                f"No event type '{event_type_source_id}' in {type(self).__name__}. This interface reads "
                f"{sorted(events_data_dict)}, which get_event_type_source_ids lists."
            )

        return events_data_dict[event_type_source_id].timestamps + self.alignment.offset

    def get_metadata_schema(self) -> dict:
        """
        Get the metadata schema for an events interface.

        Returns
        -------
        dict
            The metadata schema for this interface.
        """
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Events"] = {
            "type": "object",
            "properties": {
                # GLOBAL: the output table objects, shared across interfaces. Keyed by table_metadata_key.
                "EventTables": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "required": ["table_name", "description"],
                        "properties": {
                            "table_name": {"type": "string"},  # the table's NWB object name
                            "description": {"type": "string"},
                        },
                    },
                },
            },
            # PER-INTERFACE: one block per metadata_key (any key other than the reserved "EventTables").
            "additionalProperties": {
                "type": "object",
                "properties": {
                    # One entry per event type, keyed by event_type_source_id.
                    "event_types": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "required": ["event_name"],
                            "properties": {
                                # The type's name and description. Dual role: name/describe the auto-created
                                # table when the type is solo; label/mean the type in the ``event_type``
                                # discriminator when merged. event_name is seeded from the
                                # event_type_source_id; event_description is optional, since a source that
                                # carries no description has none to report (absent is treated as empty).
                                "event_name": {"type": "string"},
                                "event_description": {"type": "string"},
                                # Which table this type routes into (grouping). Optional; defaults to the
                                # event_type_source_id, i.e. the type gets its own table.
                                "table_metadata_key": {"type": "string"},
                                # value columns, keyed by field_source_id (a payload field); {} = timestamp-only
                                "columns": {
                                    "type": "object",
                                    "additionalProperties": {
                                        "type": "object",
                                        "required": ["column_name"],
                                        "properties": {
                                            "column_name": {"type": "string"},  # the value column's name
                                            "description": {"type": "string"},
                                            # A categorical column: raw value -> display label (+ optional
                                            # meanings). Omit for a numeric/free-text column.
                                            "column_categories": {
                                                "type": "object",
                                                "properties": {
                                                    # maps each raw value to a display label in the cells
                                                    "labels": {
                                                        "type": "object",
                                                        "additionalProperties": {"type": "string"},
                                                    },
                                                    # maps each raw value to its meaning, joined with
                                                    # ``labels`` by the raw value (a MeaningsTable)
                                                    "meanings": {
                                                        "type": "object",
                                                        "additionalProperties": {"type": "string"},
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }
        return metadata_schema

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None) -> None:
        """Write the events as ``pynwb.event.EventsTable`` objects inside ``nwbfile.events``.

        Event types are grouped by ``table_metadata_key`` (which defaults to the ``event_type_source_id``,
        so by default each type gets its own table). A **solo** type (one type, no ``EventTables`` entry)
        becomes a table whose object name is the type's ``event_name`` CamelCased and whose description is
        its ``event_description``. A **merge** (several types on one key, a declared ``EventTables`` entry,
        or a table another interface already wrote) gets an ``event_type`` discriminator column holding
        each row's ``event_name``, plus a ``MeaningsTable`` mapping those to ``event_description`` for the
        types that carry one; the merged table's own name/description come from the ``EventTables`` entry
        when given, else the name is derived from the ``table_metadata_key`` and the description is left
        empty. Value columns are joined per type (a categorical one writes display labels plus a
        ``MeaningsTable``), rows a type does not fill get the column's fill value.

        The writer is append-capable: if the target table already exists in ``nwbfile.events`` (e.g. a
        prior interface routed a merge into it), this interface's events are appended, its new columns
        backfilled on the existing rows and the existing columns filled on the new rows. Each touched
        table is re-sorted by timestamp at the end, so a merge (within or across interfaces) stays
        chronological. This in-memory re-sort applies only to tables built in the current run; events
        appended to a table already written to disk keep per-interface-block order.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the events to.
        metadata : dict, optional
            Metadata dictionary; see :meth:`get_metadata_schema`. If None, ``get_metadata()`` is used.
        """
        if metadata is None:
            metadata = self.get_metadata()

        events_metadata = metadata["Events"]
        self._validate_shared_columns(events_metadata)
        event_tables_metadata = events_metadata.get("EventTables", {})
        event_types = events_metadata[self.metadata_key]["event_types"]

        # Group event types by the table they route to; table_metadata_key defaults to the source id.
        event_type_source_ids_by_table = {}
        for event_type_source_id, entry in event_types.items():
            table_metadata_key = entry.get("table_metadata_key", event_type_source_id)
            event_type_source_ids_by_table.setdefault(table_metadata_key, []).append(event_type_source_id)

        table_owners = {}  # table object name -> event_type_source_ids this call wrote into it (to name collisions)
        for (
            table_metadata_key,
            event_type_source_ids,
        ) in event_type_source_ids_by_table.items():
            # Resolve the table name/description: a declared EventTables entry wins, else a solo type
            # supplies both, else the name comes from the routing key and the description stays empty.
            declared_entry = event_tables_metadata.get(table_metadata_key)
            if declared_entry is not None:  # an EventTables entry always has the last word
                table_name, description = (
                    declared_entry["table_name"],
                    declared_entry["description"],
                )
            elif len(event_type_source_ids) == 1:
                only = event_types[event_type_source_ids[0]]
                table_name = _to_table_object_name(only["event_name"])
                description = only.get("event_description", "")
            else:
                # An undeclared merge names itself from the routing key. Its description is left empty
                # for the same reason a solo table's is: only the user can describe the table, and here
                # there is not even a single type's description to fall back on. Declare an EventTables
                # entry to name and describe a pooled table.
                table_name, description = _to_table_object_name(table_metadata_key), ""

            existing_table = nwbfile.events.get(table_name) if nwbfile.events is not None else None
            # The user asks to combine several event types into one table by declaring an EventTables entry
            # or by routing more than one type to the same table_metadata_key; either needs an event_type
            # column. A table another interface already wrote continues such a combine.
            wants_merge = declared_entry is not None or len(event_type_source_ids) > 1
            is_merge = wants_merge or existing_table is not None
            if existing_table is not None and "event_type" not in existing_table.colnames:
                if wants_merge:
                    # Combining was intended, but the existing table was written holding a single event type,
                    # so it has no event_type column and its rows' identity was never recorded (and cannot be
                    # recovered to backfill). This only arises when the first writer lacked the full metadata
                    # (independent add_to_nwbfile calls, or on-disk append); a converter, which passes every
                    # interface the merged metadata, builds the shared table correctly from the first write.
                    # Rather than error we could always write an 'event_type' column (taxes every single-type
                    # table with a constant column, and silently swallows accidental name collisions) or
                    # backfill the existing rows' 'event_type' with "" (mislabels real events); both rejected.
                    raise ValueError(
                        f"An events table named '{table_name}' already exists but holds a single event type "
                        "(it has no 'event_type' column), so more event types cannot be combined into it. "
                        "Declare a shared EventTables entry with this table_name so every contributing "
                        "interface writes it as a shared table from the start."
                    )
                # No combine was intended: this event type's table name is already taken by another type.
                offender = event_type_source_ids[0]
                offender_name = event_types[offender]["event_name"]
                prior = table_owners.get(table_name, [])
                if prior:
                    colliding = ", ".join(f"'{source_id}'" for source_id in [*prior, offender])
                    raise ValueError(
                        f"Event types {colliding} resolve to the same events table name '{table_name}' (their "
                        "event_names produce the same table name). Give them different event_names, or route "
                        "them to one shared table with the same table_metadata_key if you meant to combine them."
                    )
                raise ValueError(
                    f"Event type '{offender}' (event_name '{offender_name}') resolves to the events table name "
                    f"'{table_name}', which already exists. Give it a different event_name, or route it to a "
                    "shared table with the same table_metadata_key if you meant to combine them."
                )

            table_owners.setdefault(table_name, []).extend(event_type_source_ids)
            table = (
                existing_table if existing_table is not None else EventsTable(name=table_name, description=description)
            )
            self._append_events_to_table(
                table=table,
                metadata=metadata,
                event_type_source_ids=event_type_source_ids,
                is_merge=is_merge,
            )
            if existing_table is None:
                nwbfile.add_events_table(table)

            # Finalize: re-sort the table chronologically (stable, so equal timestamps keep insertion
            # order). Works while the columns are in-memory lists.
            n = len(table.id)
            order = list(np.argsort(np.asarray(table["timestamp"].data), kind="stable"))
            if order != list(range(n)):
                # A ragged column is two datasets, cumulative offsets and the values they slice, and a
                # row is a span of the second rather than an element of it. Permuting the offsets would
                # be meaningless and would leave them describing values that had not moved, so its rows
                # are read out, reordered, and the pair rebuilt from them.
                ragged_columns = [column for column in table.columns if isinstance(column, VectorIndex)]
                sliced_by_index = {id(column.target) for column in ragged_columns}
                for column in ragged_columns:
                    rows = [list(column[row_index]) for row_index in range(n)]
                    reordered = [rows[index] for index in order]
                    column.target.data[:] = [value for row in reordered for value in row]
                    offsets, running_total = [], 0
                    for row in reordered:
                        running_total += len(row)
                        offsets.append(running_total)
                    column.data[:] = offsets
                for column in table.columns:
                    # A ragged column's values are not one per row, and are rebuilt above; its offsets
                    # happen to be one per row and must not be permuted as if they were values.
                    if isinstance(column, VectorIndex) or id(column) in sliced_by_index:
                        continue
                    if len(column.data) == n:
                        column.data[:] = [column.data[index] for index in order]

    def _append_events_to_table(
        self,
        *,
        table: EventsTable,
        metadata: dict,
        event_type_source_ids: list,
        is_merge: bool,
    ) -> None:
        """Append this interface's events to ``table``, creating whatever columns that data needs.

        Builds this interface's rows, ensures its value columns exist (backfilling rows already on the
        table) with a ``MeaningsTable`` for any categorical column, sets up or extends the ``event_type``
        discriminator and its ``MeaningsTable`` when merging, then adds the rows. The caller owns the
        table's identity, registration, and final re-sort; this method only fills the table it is handed.
        """
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        event_data = self._get_events_data_dict()

        # Apply the alignment offset here (lazily, at write): every written timestamp is native + offset, so
        # the cached internal representation stays in the source clock. A shift is rigid, so durations are
        # left unchanged.
        time_offset = self.alignment.offset

        # Flatten this interface's types into rows (timestamp, event_name, duration, cells) and collect the
        # value-column specs keyed by column_name.
        rows = []
        column_specs = {}
        # A payload field may hold several values per event rather than one, a behavior scored with two
        # qualifiers at once or a trial tagged with three conditions. Those become a ragged column, and
        # which columns those are is read off the data rather than declared: a metadata flag would be a
        # second place for the same fact to live and to disagree.
        ragged_column_names = set()
        for event_type_source_id in event_type_source_ids:
            event = event_data[event_type_source_id]
            entry = event_types[event_type_source_id]
            event_name = entry["event_name"]
            resolved_columns = []
            for field_source_id, column_spec in entry.get("columns", {}).items():
                assert field_source_id in event.payload, (
                    f"Event type '{event_type_source_id}' declares a column for payload field "
                    f"'{field_source_id}', but its payload has no such field (has {sorted(event.payload)})."
                )
                column_name = column_spec["column_name"]
                # Several types writing the same column_name is one shared column (its declarations are
                # checked for consistency up front by _validate_shared_columns); record it once, then let
                # each type fill its own rows below.
                column_specs.setdefault(column_name, column_spec)
                if any(_holds_several_values(value) for value in event.payload[field_source_id]):
                    ragged_column_names.add(column_name)
                resolved_columns.append((field_source_id, column_name, self._labels_map(column_spec)))
            for index, timestamp in enumerate(event.timestamps):
                cells = {}
                for field_source_id, column_name, labels_map in resolved_columns:
                    value = event.payload[field_source_id][index]
                    if labels_map is None:
                        cells[column_name] = value
                    elif _holds_several_values(value):
                        cells[column_name] = [labels_map[str(item)] for item in value]
                    else:
                        cells[column_name] = labels_map[str(value)]
                duration = float(event.durations[index]) if event.durations is not None else np.nan
                rows.append((float(timestamp) + time_offset, event_name, duration, cells))

        n_existing = len(table.id)
        has_duration = any(event_data[source_id].durations is not None for source_id in event_type_source_ids)
        if n_existing == 0:  # a fresh table: this interface decides whether it carries durations
            table_has_duration = has_duration
        else:
            table_has_duration = "duration" in table.colnames
            if has_duration and not table_has_duration:
                raise ValueError(
                    f"Cannot merge events with durations into the existing table '{table.name}', which has "
                    "no duration column. Duration presence must be consistent across the types sharing a table."
                )

        # A table that gets no rows at all is a real result, a line that was recorded and never fired, and
        # it is written rather than dropped. hdmf infers a column added at runtime from its data, though,
        # and an empty Python list carries no dtype, so those columns get a typed empty instead. (The
        # predefined timestamp and duration columns declare theirs in the schema, which is why a table
        # holding a single event type has always written empty without this.)
        stays_empty = n_existing == 0 and not rows

        # A fresh merged table needs the discriminator column before its MeaningsTable and rows.
        if is_merge and "event_type" not in table.colnames:
            table.add_column(
                name="event_type",
                description="The event type of each event.",
                data=np.array([], dtype=str) if stays_empty else [""] * n_existing,
            )

        # Ensure each value column this interface writes exists (backfilling already-present rows), and
        # create or extend its MeaningsTable. A shared column is the union of its contributors' declarations
        # (validated for consistency up front), so a later interface extends the column's MeaningsTable with
        # its own labels rather than dropping them.
        for column_name, column_spec in column_specs.items():
            categories = column_spec.get("column_categories")
            is_ragged = column_name in ragged_column_names
            if column_name not in table.colnames:
                if is_ragged:
                    # A row that has nothing for a ragged column holds an empty list, which is the only
                    # fill that means the same thing as the scalar fills below.
                    table.add_column(
                        name=column_name,
                        description=column_spec.get("description", ""),
                        data=[[] for _ in range(n_existing)],
                        index=True,
                    )
                else:
                    fill = "" if categories is not None else np.nan
                    empty = np.array([], dtype=str if categories is not None else float)
                    table.add_column(
                        name=column_name,
                        description=column_spec.get("description", ""),
                        data=empty if stays_empty else [fill] * n_existing,
                    )
            elif is_ragged and not isinstance(table[column_name], VectorIndex):
                raise ValueError(
                    f"Column '{column_name}' on table '{table.name}' holds one value per event, and this "
                    "interface writes several. A column is one shape or the other for every contributor."
                )
            # Only a meaning the user actually wrote earns a row: a column whose meanings are all empty
            # gets no MeaningsTable rather than a table of empty strings, and a partly annotated column
            # keeps just the entries that were filled in.
            meanings = {
                raw_value: meaning
                for raw_value, meaning in ((categories or {}).get("meanings") or {}).items()
                if meaning
            }
            if meanings:
                # labels and meanings are both keyed by the raw value; the MeaningsTable value is the display
                # label, matching the column's cells. Create the table the first time the column is seen, else
                # extend it (dedup by label) so a shared column keeps every contributor's meanings.
                labels = categories["labels"]
                # A ragged column is a VectorIndex over the data, and the meanings describe the values,
                # so the table targets what is underneath rather than the index.
                column = table[column_name]
                if isinstance(column, VectorIndex):
                    column = column.target
                meanings_table = next(
                    (other for other in (table.meanings_tables or {}).values() if other.target is column),
                    None,
                )
                creating = meanings_table is None
                if creating:
                    meanings_table = MeaningsTable(target=column, description="Meaning of each label.")
                existing_labels = set(meanings_table["value"].data)
                for raw_value, meaning in meanings.items():
                    label = labels[raw_value]
                    if label in existing_labels:
                        continue
                    meanings_table.add_row(value=label, meaning=meaning)
                    existing_labels.add(label)
                if creating:
                    table.add_meanings_table(meanings_table)

        # The discriminator carries each type's event_name; create or extend its MeaningsTable (extending
        # lets a second interface add its own types on append) mapping event_name -> event_description.
        # Only a type the user described earns a row, so a merge nobody annotated gets no MeaningsTable
        # at all rather than one restating each event_name back at the reader.
        if is_merge:
            column = table["event_type"]
            meanings_table = next(
                (other for other in (table.meanings_tables or {}).values() if other.target is column),
                None,
            )
            existing_values = set(meanings_table["value"].data) if meanings_table is not None else set()
            described_types = []
            for event_type_source_id in event_type_source_ids:
                entry = event_types[event_type_source_id]
                event_name = entry["event_name"]
                event_description = entry.get("event_description", "")
                if event_name in existing_values or not event_description:
                    continue
                described_types.append((event_name, event_description))
                existing_values.add(event_name)
            if described_types:
                creating_meanings = meanings_table is None
                if creating_meanings:
                    meanings_table = MeaningsTable(target=column, description="Meaning of each event type.")
                for event_name, event_description in described_types:
                    meanings_table.add_row(value=event_name, meaning=event_description)
                if creating_meanings:
                    table.add_meanings_table(meanings_table)

        # Add this interface's rows. A row fills its own columns; every other column on the table (from
        # this or a prior interface) gets that column's fill value ("" for a string column, else NaN).
        value_column_names = [name for name in table.colnames if name not in ("timestamp", "duration", "event_type")]
        for timestamp, event_name, duration, cells in rows:
            row_kwargs = {"timestamp": timestamp}
            if table_has_duration:
                row_kwargs["duration"] = duration
            if is_merge:
                row_kwargs["event_type"] = event_name
            for column_name in value_column_names:
                if column_name in cells:
                    row_kwargs[column_name] = cells[column_name]
                elif isinstance(table[column_name], VectorIndex):
                    row_kwargs[column_name] = []
                elif column_name in column_specs:
                    row_kwargs[column_name] = "" if column_specs[column_name].get("column_categories") else np.nan
                else:  # a column from a prior interface: infer the fill from its existing dtype
                    existing = table[column_name].data
                    row_kwargs[column_name] = "" if len(existing) and isinstance(existing[0], str) else np.nan
            # check_ragged=False: the check only warns that a column of scalars was handed a value of
            # a different length, and it cannot fire here, since every column's shape is settled before
            # the first row and a ragged one is a VectorIndex that add_row fills through `add_vector`
            # whatever the flag says. It is still worth passing rather than left at its default, because
            # hdmf made it amortized O(1) only in 6.2.0 and the floor is 6.1.0, where it rescans the
            # whole column on every row and makes filling a table quadratic in its rows.
            table.add_row(check_ragged=False, **row_kwargs)

    @staticmethod
    def _validate_shared_columns(events_metadata: dict) -> None:
        """Validate that event types writing one shared column declare it consistently.

        Several event types may write the same ``column_name`` into one merged table (they share a
        ``table_metadata_key``); the output column is then the union of their declarations. That union is
        well defined only where the declarations agree: a label both types explain must get the same meaning,
        and a description both types set must match. Raw codes are *not* compared across contributors, because
        each source's codes are private (two sources may reuse the same integer for different labels, which is
        a legitimate heterogeneous merge, not a conflict). Where declarations do not overlap it is a
        contribution, not a conflict (each may add its own values). The
        whole ``Events`` metadata is checked at once, so an inconsistency is caught before anything is
        written, whether the contributors live in one interface or several (a converter passes every
        interface's block in the one dict). Only genuine merges are checked: a table with a declared
        ``EventTables`` entry, or one that more than one type in a single interface routes to. Two interfaces
        that merely leave ``table_metadata_key`` unset (so it defaults to each type's own
        ``event_type_source_id``) are not a shared table even if those defaults coincide.
        """
        event_tables = events_metadata.get("EventTables", {})

        # Count, per interface block, how many types route to each table key (tells a real within-interface
        # merge from a default key that two interfaces coincidentally share), and collect every column
        # declaration keyed by the table and column it targets.
        block_table_counts = {}
        declarations = {}  # (table_key, column_name) -> list of (event_name, interface_key, column_spec)
        for interface_key, block in events_metadata.items():
            if interface_key == "EventTables":
                continue
            for source_id, entry in block.get("event_types", {}).items():
                table_key = entry.get("table_metadata_key", source_id)
                block_table_counts[(interface_key, table_key)] = (
                    block_table_counts.get((interface_key, table_key), 0) + 1
                )
                for spec in entry.get("columns", {}).values():
                    declarations.setdefault((table_key, spec["column_name"]), []).append(
                        (entry["event_name"], interface_key, spec)
                    )

        def is_merge_table(table_key: str) -> bool:
            return table_key in event_tables or any(
                count >= 2 for (_interface, key), count in block_table_counts.items() if key == table_key
            )

        for (table_key, column_name), decls in declarations.items():
            if len(decls) < 2 or not is_merge_table(table_key):
                continue
            table_display = event_tables.get(table_key, {}).get("table_name", table_key)
            label_to_meaning = {}  # display label -> (meaning, event_name, interface_key)
            described_by = None  # (description, event_name, interface_key) for the first non-empty description
            for event_name, interface_key, spec in decls:
                who = (event_name, interface_key)
                categories = spec.get("column_categories") or {}
                labels = {str(code): label for code, label in categories.get("labels", {}).items()}
                meanings = {str(code): meaning for code, meaning in categories.get("meanings", {}).items()}
                for code, meaning in meanings.items():
                    label = labels.get(code, code)
                    prior = label_to_meaning.get(label)
                    if prior is not None and prior[0] != meaning:
                        raise _shared_column_conflict(
                            column_name,
                            table_display,
                            f"label '{label}' means '{prior[0]}' vs '{meaning}'",
                            prior[1:],
                            who,
                        )
                    label_to_meaning.setdefault(label, (meaning, *who))
                description = spec.get("description", "")
                if description:
                    if described_by is not None and described_by[0] != description:
                        raise _shared_column_conflict(
                            column_name,
                            table_display,
                            f"description '{described_by[0]}' vs '{description}'",
                            described_by[1:],
                            who,
                        )
                    described_by = described_by or (description, *who)

    @staticmethod
    def _labels_map(column_spec: dict) -> dict | None:
        """Return a stringified raw-value -> display-label map for a categorical column, else None.

        Keys are stringified so a value that survives a JSON round trip (metadata keys become strings)
        still matches.
        """
        categories = column_spec.get("column_categories")
        return {str(key): label for key, label in categories["labels"].items()} if categories else None


def _shared_column_conflict(
    column_name: str, table_display: str, detail: str, first: tuple, second: tuple
) -> ValueError:
    """Build the error for two event types declaring one shared column inconsistently.

    ``first``/``second`` are ``(event_name, interface_key)`` pairs naming the two types that disagree, and
    ``detail`` says exactly how (a label, a meaning, or the description). Returned (not raised) so the caller
    raises at the offending site.
    """
    (first_name, first_interface), (second_name, second_interface) = first, second
    return ValueError(
        f"Event types '{first_name}' (interface '{first_interface}') and '{second_name}' "
        f"(interface '{second_interface}') disagree on column '{column_name}' in the shared events table "
        f"'{table_display}': {detail}. A column shared across event types must be declared consistently "
        f"(matching labels, meanings, and description where they overlap); reconcile the declarations or use "
        f"distinct column_names."
    )


def _to_table_object_name(name: str) -> str:
    """CamelCase a derived table name for use as an NWB object name, but keep an already-cased
    identifier verbatim so a raw source id is not mangled.

    A snake_case or all-lowercase ``name`` is CamelCased (``port_entries`` -> ``PortEntries``); a name
    that already carries mixed/upper casing and no underscore (a raw ``event_type_source_id`` like
    ``PtAB`` or ``XD0``) is returned unchanged, because ``to_camel_case("PtAB")`` would lowercase the
    rest and give ``"Ptab"``.
    """
    return to_camel_case(name) if ("_" in name or name.islower()) else name
