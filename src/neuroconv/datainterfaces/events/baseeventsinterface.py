from abc import abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field, replace

import numpy as np
from jsonschema import Draft7Validator
from pynwb.file import NWBFile

from ..._temporal_alignment import _TemporalAlignment
from ...basedatainterface import BaseDataInterface
from ...tools.events import _add_events_to_nwbfile
from ...tools.signal_processing import _ON_CHANGE_READINGS

_EVENT_EXTRACTION_CONFIGURATION_SCHEMA = {
    "type": ["object", "null"],
    "propertyNames": {"type": "string", "minLength": 1},
    "additionalProperties": {
        "type": "object",
        "properties": {
            "source": {"type": "string", "minLength": 1},
            "format_options": {"type": "object"},
            "signal_conditioning": {
                "type": "object",
                "required": ["binarize"],
                "properties": {"binarize": {"anyOf": [{"const": "midpoint"}, {"type": "number"}]}},
                "additionalProperties": False,
            },
            "detection": {
                "type": "object",
                "required": ["on_change"],
                "properties": {
                    "lines": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 0},
                        "minItems": 1,
                        "maxItems": 1,
                    },
                    "on_change": {
                        "type": "object",
                        "required": ["onset"],
                        "properties": {
                            "onset": {"enum": ["rising", "falling", "either"]},
                            "end": {"enum": ["rising", "falling"]},
                        },
                        "additionalProperties": False,
                    },
                    "timestamp_estimate": {
                        "enum": ["first_sample_after_change", "last_sample_before_change", "halfway_between_samples"]
                    },
                },
                "additionalProperties": False,
            },
            "separation": {
                "type": "object",
                "required": ["by_payload_fields"],
                "properties": {
                    "by_payload_fields": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "minItems": 1,
                        "maxItems": 2,
                        "uniqueItems": True,
                    },
                    "select": {"type": "array"},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    },
}


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
        self._alignment = _TemporalAlignment()
        for source_id in self.get_event_type_source_ids():
            self._alignment._add_time_bearing_object(
                key=source_id,
                get_native_times=lambda source_id=source_id: self._get_events_data_dict()[source_id].timestamps,
                get_number_of_samples=lambda source_id=source_id: len(
                    self._get_events_data_dict()[source_id].timestamps
                ),
                get_native_durations=lambda source_id=source_id: self._get_events_data_dict()[source_id].durations,
            )

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        if "event_extraction_configuration" in source_schema["properties"]:
            configuration_schema = source_schema["properties"]["event_extraction_configuration"]
            configuration_schema.setdefault("allOf", []).append(deepcopy(_EVENT_EXTRACTION_CONFIGURATION_SCHEMA))
        return source_schema

    @classmethod
    def get_available_event_sources(cls, **source_data) -> list[str]:
        """List the names of the event sources declared in the input data, in source order.

        Include sources with zero occurrences and return an empty list if none are declared.
        """
        raise NotImplementedError(f"{cls.__name__} does not provide event source discovery.")

    @classmethod
    def _resolve_event_sources(
        cls,
        event_extraction_configuration: dict | None,
        available_sources: dict[str, dict],
    ) -> dict | None:
        """Validate configured entries against the reader's inventory, or defer to its native default."""
        if not available_sources:
            raise ValueError("No event sources were found in the input data.")
        if event_extraction_configuration is None:
            return None

        validator = Draft7Validator(_EVENT_EXTRACTION_CONFIGURATION_SCHEMA)
        error = next(validator.iter_errors(event_extraction_configuration), None)
        if error is not None:
            location = "".join(f"[{key!r}]" for key in error.absolute_path)
            raise ValueError(f"Invalid event_extraction_configuration{location}: {error.message}")

        resolved_entries = {}
        for entry_name, entry in event_extraction_configuration.items():
            source_name = entry.get("source")
            if source_name is None:
                if len(available_sources) > 1:
                    raise ValueError(
                        f"Event extraction entry {entry_name!r} must specify 'source' because this recording has "
                        f"multiple event sources. Available sources: {list(available_sources)}."
                    )
                (source_name,) = available_sources
            if source_name not in available_sources:
                raise ValueError(
                    f"Event extraction entry {entry_name!r} requests missing source {source_name!r}. "
                    f"Available sources: {list(available_sources)}. "
                    f"Use {cls.__name__}.get_available_event_sources(...) to inspect the recording."
                )

            source = available_sources[source_name]
            if unsupported_reason := source.get("unsupported_reason"):
                raise ValueError(
                    f"Event extraction entry {entry_name!r} cannot read {source_name!r}: {unsupported_reason}"
                )
            supported_operations = source["supported_operations"]
            unsupported_operations = sorted(entry.keys() - {"source", *supported_operations})
            if unsupported_operations:
                raise ValueError(
                    f"Event extraction entry {entry_name!r} requests unsupported operations "
                    f"{unsupported_operations} for source {source_name!r}. "
                    f"Supported operations: {supported_operations}."
                )

            detection = entry.get("detection")
            if detection is not None:
                onset = detection["on_change"]["onset"]
                end = detection["on_change"].get("end")
                if (onset, end) not in _ON_CHANGE_READINGS:
                    raise ValueError(
                        f"Event extraction entry {entry_name!r} sets 'on_change' with onset {onset!r} and end "
                        f"{end!r}. An event that starts on a rising change ends on a falling one and the reverse, "
                        "and an 'either' onset takes no end."
                    )
            resolved_entries[entry_name] = {**entry, "source": source_name}
        return resolved_entries

    @property
    def temporal_alignment(self):
        return self._alignment

    def _get_event_durations(self, event_type_source_id: str) -> np.ndarray | None:
        """The durations of one event type on this interface's current clock, ``None`` for a type without any."""
        return self.temporal_alignment[event_type_source_id].get_durations()

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

        The handles :meth:`get_event_times` takes, and the keys of the metadata's ``event_types`` block,
        which :meth:`get_metadata` builds from this list. For a signal-encoded interface they are what
        ``detection_configuration`` resolves to, so a spec carrying an ``event_name`` is addressed by that
        name; for a pre-extracted one they are the source's own handles for its event types.

        Subclasses that can list their types from a header or a configuration override this so that
        listing them reads no events. This default reads the source.

        Returns
        -------
        list of str
            The event type identifiers.
        """
        return list(self._get_events_data_dict())

    def get_event_times(self, event_type_source_id: str) -> np.ndarray:
        """Return the onset times of one configured event type, writing nothing.

        The read that a line used as a clock calls for: a camera's frame-out pulse or an alignment pulse
        is configured like any other event type, and this hands back its times so another stream can be
        aligned against them. There is no second way to state a reading here, so the array is the one the
        writer writes, by construction rather than by agreement.

        A durative reading costs nothing for this purpose, since ``high_period`` pairs each rising edge
        with the next falling one and its onsets are those rising edges, so a line configured to be
        written with its pulse widths still answers with the edge times.

        The times are this interface's **current** times, including shifts.
        That is what makes them usable as the input to another stream's alignment:
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

        return self.temporal_alignment[event_type_source_id].get_times()

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

        events_data = {
            event_type_source_id: replace(
                event,
                timestamps=self.get_event_times(event_type_source_id),
                durations=self._get_event_durations(event_type_source_id),
            )
            for event_type_source_id, event in self._get_events_data_dict().items()
        }
        _add_events_to_nwbfile(nwbfile, events_data=events_data, metadata=metadata, metadata_key=self.metadata_key)
