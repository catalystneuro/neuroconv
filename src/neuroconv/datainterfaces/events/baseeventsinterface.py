from dataclasses import dataclass, field

import numpy as np
from hdmf.common import MeaningsTable
from pynwb.event import EventsTable
from pynwb.file import NWBFile

from ...basedatainterface import BaseDataInterface


@dataclass
class _EventInternalClass:
    """One event type's occurrences: the IO-independent internal representation (events taxonomy, Layer 3).

    Format-agnostic; every event source maps into this, independent of both the source format and
    NWB. It holds the Extent (``timestamps`` and, for an interval type, ``durations``) and the
    Payload (``payload``, a typed field-map). Interfaces return these keyed by ``event_type_id``
    (see :meth:`BaseEventsInterface._load_event_data_dict`), so the stream id is the dict key, not a
    field here.

    Attributes
    ----------
    timestamps : numpy.ndarray
        The event onset times, in seconds.
    durations : numpy.ndarray or None
        The per-event durations, in seconds, for an interval (durative) event type; ``None`` for a
        point event type. Within an interval type, ``NaN`` marks an event whose offset is missing.
    payload : dict[str, numpy.ndarray]
        A typed field-map of per-event values, keyed by ``field_id`` (the source's name for
        the field), kept in native dtype. Empty for a timestamp-only event type; one entry for a
        single value; several for a struct (multi-value) payload. Field names are scoped to their
        event type, so two streams may reuse the same field name.
    """

    timestamps: np.ndarray
    durations: np.ndarray | None = None
    payload: dict[str, np.ndarray] = field(default_factory=dict)

    def __post_init__(self):
        # An event type with no occurrences is meaningless; keep the empty state unrepresentable so
        # the writer never has to guard against it (producers skip such types instead).
        assert len(self.timestamps) > 0, "An event type must have at least one event; empty timestamps are not allowed."


class BaseEventsInterface(BaseDataInterface):
    """Base interface for discrete-event data written as NWB ``EventsTable`` objects.

    Concrete event interfaces (e.g. :class:`.TDTEventsInterface`) read their format-specific source
    and expose the events through :meth:`_load_event_data_dict` as :class:`_EventInternalClass`
    records. This base owns the two pieces that do not depend on the source format: the shared
    ``Events`` metadata schema (:meth:`get_metadata_schema`) and the writer (:meth:`add_to_nwbfile`)
    that maps that internal representation, together with the metadata, into ``pynwb.event.EventsTable``
    objects inside ``nwbfile.events``.

    The metadata has two levels. A global ``EventTables`` block declares each output table object
    (``table_name`` + ``description``, shared across interfaces). A per-interface ``event_types``
    block (under each ``metadata_key``) holds one entry per event type, keyed by its
    ``event_type_id``: the entry names the table it enters (``table_metadata_key``) and holds a
    ``columns`` map, keyed by ``field_id`` (a payload field), where each column carries its
    output ``column_name`` and optional ``column_categories`` (relabelling + meanings). A single value
    gives one column, a struct payload several (they share the event's rows), a timestamp-only type
    an empty ``columns``. ``table_metadata_key`` is the grouping knob: it defaults to one table per
    event type; pointing several event types at one table pools their events, and the writer then adds
    an ``event_type`` discriminator column naming each row's ``event_type_id``. This structure
    is documented in the events taxonomy and PR #1759
    (https://github.com/catalystneuro/neuroconv/pull/1759).

    Subclasses must set ``self.metadata_key`` and implement :meth:`_load_event_data_dict`.
    """

    keywords = ("events",)

    def _load_event_data_dict(self) -> dict[str, _EventInternalClass]:
        """Return the internal event representation, keyed by ``event_type_id``.

        Returns
        -------
        dict[str, _EventInternalClass]
            Maps each ``event_type_id`` (the source's own handle for an event type, e.g. a TDT
            epoc name) to its :class:`_EventInternalClass` (timestamps, optional durations, typed
            payload field-map). The writer joins this to the metadata by key: the ``event_types``
            entry keyed by the same ``event_type_id``, and each of its ``columns`` keyed by a
            ``field_id`` in this record's ``payload``.
        """
        raise NotImplementedError("Event interfaces must implement `_load_event_data_dict`.")

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
                    # One entry per event type, keyed by event_type_id.
                    "event_types": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "required": ["table_metadata_key"],
                            "properties": {
                                # which (global) EventTables entry this type's rows fill -> grouping
                                "table_metadata_key": {"type": "string"},
                                # value columns, keyed by field_id (a payload field); {} = timestamp-only
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

        Each ``event_types`` entry is one event type; the writer joins it to the loaded data by key
        (``event_type_id``), and each of its ``columns`` to a payload field (``field_id``).
        Event types are grouped by ``table_metadata_key``. Within a table, the columns of one event
        type share the same rows (a struct payload fans into several columns); several event types
        pooled into one table are written long and time-sorted, with an ``event_type`` discriminator
        naming each row's ``event_type_id`` and each type's columns filled only on its own rows.
        A categorical column writes display labels plus a ``MeaningsTable`` when meanings are supplied;
        any other column writes raw values. Two columns writing the same ``column_name`` into one table
        raise, as does a declared column whose ``field_id`` is absent from the payload.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the events to.
        metadata : dict, optional
            Metadata dictionary; see :meth:`get_metadata_schema`. If None, ``get_metadata()`` is used.
        """
        if metadata is None:
            metadata = self.get_metadata()

        event_data = self._load_event_data_dict()

        events_metadata = metadata["Events"]
        event_tables_metadata = events_metadata["EventTables"]
        event_types = events_metadata[self.metadata_key]["event_types"]

        # Group the event types by the table they route to.
        event_type_ids_by_table = {}
        for event_type_id, entry in event_types.items():
            event_type_ids_by_table.setdefault(entry["table_metadata_key"], []).append(event_type_id)

        # Each table_metadata_key becomes one EventsTable object, so their table_names must be unique.
        table_metadata_keys_by_name = {}
        for table_metadata_key in event_type_ids_by_table:
            table_name = event_tables_metadata[table_metadata_key]["table_name"]
            table_metadata_keys_by_name.setdefault(table_name, []).append(table_metadata_key)
        collisions = {name: keys for name, keys in table_metadata_keys_by_name.items() if len(keys) > 1}
        assert not collisions, (
            f"Duplicate EventTables 'table_name' values found in metadata: {collisions}. "
            "Each EventsTable must have a unique name; give these table_metadata_key entries distinct table_name values."
        )

        for table_metadata_key, event_type_ids in event_type_ids_by_table.items():
            # More than one event type pooled into one table is a merge, told apart by an event_type
            # column. A single event type (however many columns it fans into) needs no discriminator.
            is_merge = len(event_type_ids) > 1
            has_duration = any(event_data[event_type_id].durations is not None for event_type_id in event_type_ids)

            rows = []  # (timestamp, event_type_id, duration_or_nan, {column_name: cell})
            column_specs = {}  # column_name -> column_spec (the value columns to attach)
            for event_type_id in event_type_ids:
                event = event_data[event_type_id]
                columns = event_types[event_type_id].get("columns", {})

                # Resolve this event type's columns once: (field_id, column_name, labels_map).
                resolved_columns = []
                for field_id, column_spec in columns.items():
                    assert field_id in event.payload, (
                        f"Event type '{event_type_id}' declares a column for payload field "
                        f"'{field_id}', but its payload has no such field (has {sorted(event.payload)})."
                    )
                    column_name = column_spec["column_name"]
                    assert column_name not in column_specs, (
                        f"Two event columns write the same column_name '{column_name}' into table "
                        f"'{table_metadata_key}'. Give each event column a unique column_name."
                    )
                    column_specs[column_name] = column_spec
                    resolved_columns.append((field_id, column_name, self._labels_map(column_spec)))

                for index, timestamp in enumerate(event.timestamps):
                    cells = {}
                    for field_id, column_name, labels_map in resolved_columns:
                        value = event.payload[field_id][index]
                        cells[column_name] = labels_map[str(value)] if labels_map is not None else value
                    duration = float(event.durations[index]) if event.durations is not None else np.nan
                    rows.append((float(timestamp), event_type_id, duration, cells))

            # Pooled types concatenate in blocks; sort by timestamp for a true chronological timeline
            # (a no-op for a single type, whose onsets are already ordered).
            rows.sort(key=lambda row: row[0])

            table_metadata = event_tables_metadata[table_metadata_key]
            table = EventsTable(name=table_metadata["table_name"], description=table_metadata["description"])
            # Only the native EventsTable columns go through add_event: timestamp, plus duration when any
            # pooled type has one. Every derived column (the event_type discriminator and the value
            # columns) is attached full-length afterwards.
            for timestamp, _event_type_id, duration, _cells in rows:
                event_kwargs = {"timestamp": timestamp}
                if has_duration:
                    event_kwargs["duration"] = duration
                table.add_event(**event_kwargs)

            # A merge tells its pooled types apart with an event_type discriminator: one value per row,
            # filled on every row, so it is just another full-length column like the value columns below.
            if is_merge:
                table.add_column(
                    name="event_type",
                    description="The event type of each event.",
                    data=[event_type_id for _, event_type_id, _, _ in rows],
                )

            # Attach each value column full-length, filling rows from other types, plus a MeaningsTable
            # for a categorical column that supplies meanings.
            for column_name, column_spec in column_specs.items():
                categories = column_spec.get("column_categories")
                fill = "" if categories is not None else np.nan
                column_data = [cells.get(column_name, fill) for _, _, _, cells in rows]
                description = column_spec.get("description", f"Value of the '{column_name}' column for each event.")
                table.add_column(name=column_name, description=description, data=column_data)
                meanings = categories.get("meanings") if categories else None
                if meanings:
                    # labels and meanings are both keyed by the raw value; the MeaningsTable value is
                    # the display label, matching the column's cells.
                    labels = categories["labels"]
                    meanings_table = MeaningsTable(target=table[column_name], description="Meaning of each label.")
                    for raw_value, meaning in meanings.items():
                        meanings_table.add_row(value=labels[raw_value], meaning=meaning)
                    table.add_meanings_table(meanings_table)

            nwbfile.add_events_table(table)

    @staticmethod
    def _labels_map(column_spec: dict) -> dict | None:
        """Return a stringified raw-value -> display-label map for a categorical column, else None.

        Keys are stringified so a value that survives a JSON round trip (metadata keys become strings)
        still matches.
        """
        categories = column_spec.get("column_categories")
        return {str(key): label for key, label in categories["labels"].items()} if categories else None
