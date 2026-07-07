from abc import abstractmethod
from dataclasses import dataclass, field

import numpy as np
from hdmf.common import MeaningsTable
from pynwb.event import EventsTable
from pynwb.file import NWBFile

from ...basedatainterface import BaseDataInterface
from ...utils import to_camel_case


@dataclass
class _EventsData:
    """One event type's occurrences: the IO-independent internal representation (events taxonomy, Layer 3).

    Format-agnostic; every event source maps into this, independent of both the source format and
    NWB. It holds the Extent (``timestamps`` and, for an interval type, ``durations``) and the
    Payload (``payload``, a typed field-map). Interfaces return these keyed by ``event_type_source_id``
    (see :meth:`BaseEventsInterface._get_events_data_dict`), so the stream id is the dict key, not a
    field here.

    Attributes
    ----------
    timestamps : numpy.ndarray
        The event onset times, in seconds.
    durations : numpy.ndarray or None
        The per-event durations, in seconds, for an interval (durative) event type; ``None`` for a
        point event type. Within an interval type, ``NaN`` marks an event whose offset is missing.
    payload : dict[str, numpy.ndarray]
        A typed field-map of per-event values, keyed by ``field_source_id`` (the source's name for
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
    and expose the events through :meth:`_get_events_data_dict` as :class:`_EventsData`
    records. This base owns the two pieces that do not depend on the source format: the shared
    ``Events`` metadata schema (:meth:`get_metadata_schema`) and the writer (:meth:`add_to_nwbfile`)
    that maps that internal representation, together with the metadata, into ``pynwb.event.EventsTable``
    objects inside ``nwbfile.events``.

    The metadata lives under a per-interface ``metadata_key`` as an ``event_types`` block, one entry
    per event type keyed by its ``event_type_source_id``. Each entry carries a required
    ``event_name``/``event_description`` (the type's name and description, both defaulting to the source
    id), an optional ``table_metadata_key`` (which table it routes into, defaulting to the source id so
    each type gets its own table), and a ``columns`` map keyed by ``field_source_id`` (a payload field),
    where each column carries its output ``column_name`` and optional ``column_categories`` (relabelling
    + meanings). A single value gives one column, a struct payload several (sharing the event's rows), a
    timestamp-only type an empty ``columns``.

    ``event_name``/``event_description`` play a dual role by layout. When a type has its own table
    (**solo**, the default), they become the table's object name (CamelCased) and description. When
    several types share a ``table_metadata_key`` (**merge**), the table gets an ``event_type``
    discriminator column holding each row's ``event_name``, plus a ``MeaningsTable`` mapping those to
    ``event_description``. A merged table's own name/description are derived, or taken from an optional
    global ``EventTables`` entry (``table_name`` + ``description``) which always has the last word;
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
                            "required": ["event_name", "event_description"],
                            "properties": {
                                # The type's name and description. Dual role: name/describe the auto-created
                                # table when the type is solo; label/mean the type in the ``event_type``
                                # discriminator when merged. Both default to the event_type_source_id.
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
        each row's ``event_name``, plus a ``MeaningsTable`` mapping those to ``event_description``; the
        merged table's own name/description come from the ``EventTables`` entry when given, else are
        derived. Value columns are joined per type (a categorical one writes display labels plus a
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

        event_data = self._get_events_data_dict()
        events_metadata = metadata["Events"]
        event_tables_metadata = events_metadata.get("EventTables", {})
        event_types = events_metadata[self.metadata_key]["event_types"]

        # Group event types by the table they route to; table_metadata_key defaults to the source id.
        event_type_source_ids_by_table = {}
        for event_type_source_id, entry in event_types.items():
            table_metadata_key = entry.get("table_metadata_key", event_type_source_id)
            event_type_source_ids_by_table.setdefault(table_metadata_key, []).append(event_type_source_id)

        for table_metadata_key, event_type_source_ids in event_type_source_ids_by_table.items():
            self._add_or_extend_events_table(
                nwbfile=nwbfile,
                table_metadata_key=table_metadata_key,
                event_type_source_ids=event_type_source_ids,
                event_types=event_types,
                event_tables_metadata=event_tables_metadata,
                event_data=event_data,
            )

    def _add_or_extend_events_table(
        self,
        *,
        nwbfile: NWBFile,
        table_metadata_key: str,
        event_type_source_ids: list,
        event_types: dict,
        event_tables_metadata: dict,
        event_data: dict,
    ) -> None:
        """Create the ``EventsTable`` for one ``table_metadata_key``, or append to it if it already exists.

        Solo (one type, no EventTables entry): the object name is the type's ``event_name`` CamelCased and
        the description is its ``event_description``. Merge (several types here, a declared EventTables
        entry, or a table another interface already wrote): the ``event_type`` discriminator holds each
        row's ``event_name`` and a MeaningsTable maps those to ``event_description``; the table's own
        name/description come from the EventTables entry when given, else are derived. Appending backfills
        this interface's new columns on the existing rows and fills the existing columns on the new rows,
        then the table is re-sorted by timestamp.
        """
        # Resolve the table name/description: a declared EventTables entry wins, else derive from the
        # single solo type, else from the pooled types.
        declared_entry = event_tables_metadata.get(table_metadata_key)
        if declared_entry is not None:  # an EventTables entry always has the last word
            table_name, description = declared_entry["table_name"], declared_entry["description"]
        elif len(event_type_source_ids) == 1:
            only = event_types[event_type_source_ids[0]]
            table_name, description = to_camel_case(only["event_name"]), only["event_description"]
        else:
            names = ", ".join(event_types[source_id]["event_name"] for source_id in event_type_source_ids)
            table_name, description = to_camel_case(table_metadata_key), f"Events pooled from types: {names}."

        existing_table = nwbfile.events.get(table_name) if nwbfile.events is not None else None
        # A declared shared table, more than one type here, or a table another interface already wrote all
        # mean this is a merge, which needs the event_type discriminator.
        is_merge = declared_entry is not None or len(event_type_source_ids) > 1 or existing_table is not None
        if existing_table is not None and "event_type" not in existing_table.colnames:
            raise ValueError(
                f"An events table named '{table_name}' already exists but is a single-type table (it has "
                "no 'event_type' discriminator), so events cannot be merged into it. Give this interface's "
                "table a distinct name, or declare a shared EventTables entry with this table_name so every "
                "contributing interface writes it as a merged table."
            )

        # Flatten this interface's types into rows (timestamp, event_name, duration, cells) and collect the
        # value-column specs keyed by column_name.
        rows = []
        column_specs = {}
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
                assert column_name not in column_specs, (
                    f"Two event columns write the same column_name '{column_name}'. "
                    "Give each event column a unique column_name."
                )
                column_specs[column_name] = column_spec
                resolved_columns.append((field_source_id, column_name, self._labels_map(column_spec)))
            for index, timestamp in enumerate(event.timestamps):
                cells = {}
                for field_source_id, column_name, labels_map in resolved_columns:
                    value = event.payload[field_source_id][index]
                    cells[column_name] = labels_map[str(value)] if labels_map is not None else value
                duration = float(event.durations[index]) if event.durations is not None else np.nan
                rows.append((float(timestamp), event_name, duration, cells))

        has_duration = any(event_data[source_id].durations is not None for source_id in event_type_source_ids)
        if existing_table is None:
            table = EventsTable(name=table_name, description=description)
            table_has_duration = has_duration
            if is_merge:
                table.add_column(name="event_type", description="The event type of each event.", data=[])
        else:
            table = existing_table
            table_has_duration = "duration" in table.colnames
            if has_duration and not table_has_duration:
                raise ValueError(
                    f"Cannot merge events with durations into the existing table '{table_name}', which has "
                    "no duration column. Duration presence must be consistent across the types sharing a table."
                )

        n_existing = len(table.id)
        # Ensure each value column this interface writes exists, backfilling already-present rows, and
        # attach a MeaningsTable for a categorical column that supplies meanings.
        for column_name, column_spec in column_specs.items():
            if column_name in table.colnames:
                continue
            categories = column_spec.get("column_categories")
            fill = "" if categories is not None else np.nan
            table.add_column(
                name=column_name,
                description=column_spec.get("description", f"Value of the '{column_name}' column for each event."),
                data=[fill] * n_existing,
            )
            meanings = categories.get("meanings") if categories else None
            if meanings:
                # labels and meanings are both keyed by the raw value; the MeaningsTable value is the
                # display label, matching the column's cells.
                labels = categories["labels"]
                meanings_table = MeaningsTable(target=table[column_name], description="Meaning of each label.")
                for raw_value, meaning in meanings.items():
                    meanings_table.add_row(value=labels[raw_value], meaning=meaning)
                table.add_meanings_table(meanings_table)

        # The discriminator carries each type's event_name; create or extend its MeaningsTable (extending
        # lets a second interface add its own types on append) mapping event_name -> event_description.
        if is_merge:
            column = table["event_type"]
            meanings_table = next(
                (other for other in (table.meanings_tables or {}).values() if other.target is column), None
            )
            creating_meanings = meanings_table is None
            if creating_meanings:
                meanings_table = MeaningsTable(target=column, description="Meaning of each event type.")
            existing_values = set(meanings_table["value"].data)
            for event_type_source_id in event_type_source_ids:
                entry = event_types[event_type_source_id]
                if entry["event_name"] in existing_values:
                    continue
                meanings_table.add_row(value=entry["event_name"], meaning=entry["event_description"])
                existing_values.add(entry["event_name"])
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
                elif column_name in column_specs:
                    row_kwargs[column_name] = "" if column_specs[column_name].get("column_categories") else np.nan
                else:  # a column from a prior interface: infer the fill from its existing dtype
                    existing = table[column_name].data
                    row_kwargs[column_name] = "" if len(existing) and isinstance(existing[0], str) else np.nan
            table.add_row(**row_kwargs)

        if existing_table is None:
            nwbfile.add_events_table(table)

        # Re-sort chronologically by permuting every full-length column in place (stable, so equal
        # timestamps keep insertion order). Works while the columns are in-memory lists.
        n = len(table.id)
        order = list(np.argsort(np.asarray(table["timestamp"].data), kind="stable"))
        if order != list(range(n)):
            for column in table.columns:
                if len(column.data) == n:
                    column.data[:] = [column.data[index] for index in order]

    @staticmethod
    def _labels_map(column_spec: dict) -> dict | None:
        """Return a stringified raw-value -> display-label map for a categorical column, else None.

        Keys are stringified so a value that survives a JSON round trip (metadata keys become strings)
        still matches.
        """
        categories = column_spec.get("column_categories")
        return {str(key): label for key, label in categories["labels"].items()} if categories else None
