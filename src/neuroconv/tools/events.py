from dataclasses import replace

import numpy as np
from hdmf.common import MeaningsTable, VectorIndex
from pynwb.event import EventsTable
from pynwb.file import NWBFile

from .nwb_helpers._metadata_and_file_helpers import _validate_metadata_key, _validate_metadata_path
from ..utils import to_camel_case

# The two cuts: the routes a signal takes to become a line. Exactly one appears in every spec, and which
# one is legal is decided by the signal's kind rather than by the caller. 'bits' names a wire inside a
# packed word; 'binarize' cuts a magnitude, at a number you give or at "midpoint", derived from the data.
#
# These are also the *only* settings signal_conditioning recognizes: hysteresis and debounce are designed
# but unbuilt, so they hit the unrecognized-key error rather than validating and doing nothing, which is
# the silent-discard failure this validation exists to remove. They land with their implementation.
_CUTS = ("bits", "binarize")
_BINARIZE_METHODS = ("midpoint",)
_SPEC_KEYS = ("signal_conditioning", "detection", "event_time_convention", "event_name")

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
                # One method per entry. `on_change` watches one line. `on_code_change` and `on_strobe` read the
                # code that the state of several lines forms, so they name them.
                "oneOf": [{"required": ["on_change"]}, {"required": ["on_code_change"]}, {"required": ["on_strobe"]}],
                "if": {"required": ["on_change"]},
                "then": {"properties": {"lines": {"maxItems": 1}}},
                "dependencies": {"on_code_change": ["lines"], "on_strobe": ["lines"]},
                "properties": {
                    "lines": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 0},
                        "minItems": 1,
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
                    "on_code_change": {"type": "object", "properties": {}, "additionalProperties": False},
                    "on_strobe": {
                        "type": "object",
                        "required": ["line", "onset"],
                        "properties": {
                            "line": {"type": "integer", "minimum": 0},
                            "onset": {"enum": ["rising", "falling"]},
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


def _validate_detection_configuration(detection_configuration: dict, available_signals: dict) -> None:
    """Validate a ``detection_configuration``, raising ``ValueError`` on a bad entry.

    The one construction-time check. It answers both "is this well formed" (per-spec structure, checked
    against each signal's kind) and "do its identifiers resolve" (rules 4 and 5), so an interface calls
    this and nothing else. It is called on the interface's own default configuration too, not only on a
    caller-supplied one: a default is machine-built, but its inputs are not, so it can still resolve two
    event types to the same identifier.

    A shared helper for the signal-encoded events interfaces (each derives events from a sampled
    signal). ``detection_configuration`` maps each ``signal_source_id`` to a **list** of detection
    specs, one per event type derived from that signal. A spec is all-or-nothing and states both stages:
    pass ``None`` instead of a configuration to read every signal with the interface's default reading,
    or name signals and give each spec a ``signal_conditioning`` and a ``detection``. A half-filled spec
    is an error rather than a silent fallback, so what an event type is written from is always chosen.

    The ``detection`` *value* is deliberately not checked here:
    :func:`~neuroconv.tools.signal_processing._detect_events` is the single source of truth for the
    reading vocabulary and raises on an invalid one.

    Parameters
    ----------
    detection_configuration : dict
        The caller-supplied ``{signal_source_id: [spec, ...]}`` configuration to validate.
    available_signals : dict
        The signals discovered in the file, keyed by ``signal_source_id``. Each value is a descriptor
        whose ``kind`` is ``"line"`` (one digital line), ``"word"`` (a packed integer), ``"analog"`` (a
        continuous trace), or absent when the format records no kind. The kind decides which cut is
        legal. A word may additionally declare ``bits``, the line positions it carries, which is checked
        against the positions a spec asks for. Everything else in the descriptor is the interface's own
        addressing and stays opaque here.

    Raises
    ------
    ValueError
        If the configuration is empty, names a signal not in ``available_signals``, gives a signal
        something other than a non-empty list, or holds a malformed spec: an unrecognized key, no
        ``detection``, no ``signal_conditioning``, other than exactly one cut, a cut the signal's kind
        does not admit, or a bit position the word does not carry. Also if the identifiers do not
        resolve: two event types reaching the same identifier (rule 4) or a fan-out whose components do
        not stringify into a stable name (rule 5).
    """
    if not detection_configuration:
        raise ValueError(
            "detection_configuration is empty. Pass None (the default) to derive every signal, or name "
            "at least one signal."
        )
    for signal_source_id, specs in detection_configuration.items():
        if signal_source_id not in available_signals:
            raise ValueError(
                f"detection_configuration names '{signal_source_id}', which is not one of the file's "
                f"signals: {list(available_signals)}."
            )
        if not isinstance(specs, list):
            raise ValueError(
                f"detection_configuration entry for '{signal_source_id}' must be a list of detection "
                f"specs, got {type(specs).__name__}. A signal may yield several event types, so its "
                "value is always a list even when it holds one spec."
            )
        if not specs:
            raise ValueError(
                f"detection_configuration entry for '{signal_source_id}' is an empty list. Drop the "
                "signal to skip it, or give it at least one detection spec."
            )
        descriptor = available_signals[signal_source_id]
        # Read out the declared fields rather than handing the descriptor over, so what this function
        # sees of an interface's addressing stays exactly these two and the rest stays opaque.
        kind = descriptor.get("kind")
        available_bits = descriptor.get("bits")
        for spec in specs:
            _validate_spec(spec=spec, signal_source_id=signal_source_id, kind=kind, available_bits=available_bits)
    # Rules 4 and 5 are properties of the *derived* identifiers rather than of the configuration text, so
    # the only way to check them is to derive. Resolving is what raises them, and it is free inside the
    # loop that computes the identifiers, which is why they live there rather than being restated here.
    _resolve_event_types(detection_configuration)


def _validate_spec(
    spec: dict, signal_source_id: str, kind: str | None, available_bits: list[int] | None = None
) -> None:
    """Validate one detection spec, raising ``ValueError`` naming the stage that rejected it."""
    unknown_keys = set(spec) - set(_SPEC_KEYS)
    if unknown_keys:
        raise ValueError(
            f"detection_configuration spec for '{signal_source_id}' has unrecognized key(s) "
            f"{sorted(unknown_keys)}. A spec holds 'signal_conditioning' (how to reach a discrete-valued "
            "signal), 'detection' (which transitions become events), an optional 'event_time_convention' (which "
            "time each event gets), and an optional 'event_name'."
        )
    if "detection" not in spec:
        raise ValueError(
            f"detection_configuration spec for '{signal_source_id}' does not set 'detection'. Every "
            "spec must state how its signal's transitions become events; pass None instead of a "
            "detection_configuration to read every signal with the interface's default reading."
        )

    conditioning = spec.get("signal_conditioning")
    if conditioning is None:
        raise ValueError(
            f"detection_configuration spec for '{signal_source_id}' does not set 'signal_conditioning'. "
            f"Every spec states how its signal becomes a line: {list(_CUTS)}. A signal that is already "
            "one takes {'binarize': 'midpoint'}, which cuts between its two levels whatever they are."
        )

    if not isinstance(conditioning, dict):
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' must be a dict of conditioning settings, got "
            f"{type(conditioning).__name__}."
        )
    unknown_keys = set(conditioning) - set(_CUTS)
    if unknown_keys:
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' has unrecognized key(s) {sorted(unknown_keys)}. "
            f"Valid settings are {list(_CUTS)}."
        )
    cuts = [cut for cut in _CUTS if cut in conditioning]
    if len(cuts) != 1:
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' sets {len(cuts)} cuts ({cuts}), and a spec "
            f"holds exactly one. {list(_CUTS)} are alternative routes to a line, so one applies."
        )
    if "bits" in conditioning and kind not in ("word", None):
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' sets 'bits', but that signal is not a packed "
            "word. Bit selection applies only to a signal that packs several lines into one integer."
        )
    if "bits" in conditioning and len(list(conditioning["bits"])) != 1:
        # The coded-word reading (several bits read together as one value) is deferred, deliberately and
        # in full: reading a code needs a strobe or debounce guard to say when the word is settled, since
        # a real word's bits do not all change on the same sample and every transient combination it
        # passes through would otherwise be written as a real event. The guard and the reading land
        # together. Until then a spec names exactly one bit, which is a plain line and needs no guard.
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' sets 'bits' {list(conditioning['bits'])}, but "
            "reading several bits together as one coded value is not supported yet. It needs a strobe or "
            "debounce guard to know when the word is settled, and the two will land together. Name one "
            "bit per spec to read each line on its own."
        )
    if "bits" in conditioning and available_bits is not None:
        # Structural, from the format's own declaration, and it costs no data read. The failure it
        # prevents is silent: an unacquired bit is zero at every sample, so it reads as a line that
        # never toggled and writes a zero-row table. That is exactly what an acquired line that never
        # fired writes, and the design requires *that* to succeed, so the two cannot be told apart
        # afterwards. Only the header separates them, which is why this is checked here and never from
        # the samples. A word whose format declares no inventory omits 'bits' and gets no check, the
        # same way a signal whose kind is unknown is admitted.
        absent_bits = [bit for bit in conditioning["bits"] if bit not in available_bits]
        if absent_bits:
            raise ValueError(
                f"signal_conditioning for '{signal_source_id}' names bit position(s) {absent_bits}, "
                f"which this recording does not carry. Its bit positions are {sorted(available_bits)}. "
                "An unrecorded bit is zero at every sample, so it would write an empty table rather "
                "than fail."
            )
    if "binarize" in conditioning and not isinstance(conditioning["binarize"], (str, int, float)):
        raise ValueError(
            f"signal_conditioning 'binarize' for '{signal_source_id}' must be {list(_BINARIZE_METHODS)} "
            f"to derive the cut from the data, or a number to give it, got "
            f"{type(conditioning['binarize']).__name__}."
        )
    if kind == "word" and cuts != ["bits"]:
        # A word is several signals until the caller says which bits form one value, so cutting its
        # integer at a magnitude reads a bit pattern as a number. Values 0, 1, 2, 3 on a two-line word
        # are four combinations of two independent lines, not four levels of one signal, and a cut at
        # 1.5 asks which of them are "large". The derived cut is the same mistake with the number
        # computed rather than given, so both spellings of 'binarize' are refused here.
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' cuts a packed word with '{cuts[0]}', which "
            "reads its bit pattern as a magnitude. A word is several signals until you say which bits "
            "form one value, so name the line you want with 'bits'."
        )


def _resolve_event_types(detection_configuration: dict) -> list[tuple[str, str, dict]]:
    """The derivation itself: ``(event_type_source_id, signal_source_id, spec)``, in configuration order.

    Private, and the single place an identifier is computed or the cross-signal uniqueness check is run.
    The two public views are independent thin wrappers over this, so each depends only on the
    ``detection_configuration`` and never on the other.

    The rules, in order:

    1. One spec for a signal: the identifier is the ``signal_source_id`` unchanged, which keeps a
       zero-configuration conversion's identifiers equal to the strings the acquisition software shows.
    2. Several specs: the identifier is the signal handle plus every distinguishing component present,
       in conditioning-then-detection order, giving ``XD0_bit0_rising`` or ``DIN-01_rising`` /
       ``DIN-01_falling``. Every component is included rather than only the differing ones, so adding a
       spec later does not rename its siblings. ``event_time_convention`` is not a component: it moves an
       event's time without selecting which transitions are events, so two specs that differ only in it
       collide under rule 4.
    3. A spec's ``event_name`` replaces the derived identifier entirely. Set it when you want an
       identifier pinned against later edits, since a signal going from one spec to several moves it
       from rule 1 to rule 2 and the derived form changes.
    4. Identifiers must be unique across the whole configuration.
    5. ``event_name`` is required when a fan-out spec gives ``binarize`` a **number**, since a cut point
       does not stringify into a stable valid name. Stated as an exclusion so absence is fine: a spec
       carving a single bit, or one cutting at ``"midpoint"``, derives perfectly well, because neither
       carries a free value and the specs are then told apart by their reading.

    Returns a list rather than a generator so rule 4 is always checked in full, even by a caller that
    would otherwise stop early.
    """
    event_types: list[tuple[str, str, dict]] = []
    seen: set[str] = set()
    for signal_source_id, specs in detection_configuration.items():
        yields_one_event_type = len(specs) == 1
        for spec in specs:
            event_name = spec.get("event_name")
            if event_name is not None:
                event_type_source_id = event_name
            elif yields_one_event_type:
                event_type_source_id = signal_source_id
            else:
                event_type_source_id = _derive_event_type_source_id(signal_source_id=signal_source_id, spec=spec)
            if event_type_source_id in seen:
                raise ValueError(
                    f"detection_configuration resolves two event types to the same identifier "
                    f"'{event_type_source_id}'. Set 'event_name' on one of them to tell them apart."
                )
            seen.add(event_type_source_id)
            event_types.append((event_type_source_id, signal_source_id, spec))
    return event_types


def _resolve_detection_plan(detection_configuration: dict) -> dict[str, list[tuple[str, dict]]]:
    """Resolve a ``detection_configuration`` into ``{signal_source_id: [(event_type_source_id, spec), ...]}``.

    The structure the read walks, built from the ``detection_configuration`` alone. It is **grouped by
    signal** because reading is per signal while deriving is per event type: a
    sixteen-bit word fanned into sixteen event types is one read and sixteen derivations, not sixteen
    reads, which is the difference that matters once a signal is hours of 30 kHz samples.

    The grouping mirrors the ``detection_configuration``'s own, so the plan is that configuration with
    each spec annotated by the identifier it resolves to. Entries come back in configuration order
    (signals in their configured order, each signal's specs in list order), which is the order the
    metadata and the writer present event types in.

    An event type is (what you read) times (how you read it), so a signal yielding one event type keeps
    its own handle as the identifier and a signal yielding several fans out. The derivation rules are in
    :func:`_resolve_event_types`.

    Build it where it is read rather than holding it on the interface: it is pure and cheap, so rebuilding
    costs nothing, and an interface that never reads never needs one.

    Parameters
    ----------
    detection_configuration : dict
        A validated ``{signal_source_id: [spec, ...]}`` configuration.

    Returns
    -------
    dict
        ``signal_source_id -> [(event_type_source_id, spec), ...]``, one entry per signal to read and one
        pair per event type to derive from it.

    Raises
    ------
    ValueError
        If a fan-out spec needs an ``event_name`` and has none, or if two event types resolve to the
        same identifier.
    """
    detection_plan: dict[str, list[tuple[str, dict]]] = {}
    for event_type_source_id, signal_source_id, spec in _resolve_event_types(detection_configuration):
        detection_plan.setdefault(signal_source_id, []).append((event_type_source_id, spec))
    return detection_plan


def _get_event_type_source_ids(detection_configuration: dict) -> list[str]:
    """The identifiers a ``detection_configuration`` resolves to, in configuration order.

    Everything ``get_metadata`` sees of the configuration, deliberately. Metadata names event types; it
    has no business with how they are read, so it gets identifiers and not specs. Keeping the seam here
    is what stops a metadata question (does this event type carry a payload?) from pulling the detection
    vocabulary into the metadata layer.
    """
    return [event_type_source_id for event_type_source_id, _, _ in _resolve_event_types(detection_configuration)]


def _derive_event_type_source_id(signal_source_id: str, spec: dict) -> str:
    """Build a fan-out spec's identifier from its signal handle plus its distinguishing components."""
    conditioning = spec.get("signal_conditioning") or {}
    if not isinstance(conditioning.get("binarize", "midpoint"), str):
        # A given cut is a number, and numbers do not stringify into a stable valid name. Derived cuts
        # do: "midpoint" carries no free value, so two specs sharing it are told apart by their reading.
        raise ValueError(
            f"'{signal_source_id}' fans out on a 'binarize' cut point, which does not stringify into a "
            "stable identifier. Give each of its specs an 'event_name'."
        )
    components = []
    if "bits" in conditioning:
        # Always exactly one bit: the validator rejects a multi-bit spec, since the coded-word reading
        # is deferred until its strobe/debounce guard exists.
        components.append(f"bit{list(conditioning['bits'])[0]}")
    components.append(spec["detection"])
    return "_".join([signal_source_id, *components])


def _separate_events(resolved_configuration: dict, events_by_entry: dict) -> dict:
    """Apply each entry's ``separation`` to the occurrences read for it, keyed by the resulting identifiers.

    An entry without ``separation`` is one event type identified by the entry name. An entry with it
    becomes one event type per distinct value, or pair of values, of ``by_payload_fields``, in order of
    first occurrence, or one per item of ``select`` in the order listed. The identifier is the entry
    name followed by the values in the order of ``by_payload_fields``, joined with underscores.
    Timestamps, durations and every payload field, including the separation fields, are selected with
    the same rows, so a requested value with no occurrences gives a type with typed empty arrays.

    Parameters
    ----------
    resolved_configuration : dict
        The configuration returned by ``BaseEventsInterface._resolve_event_sources``.
    events_by_entry : dict[str, _EventsData]
        The occurrences the reader read for each entry, keyed by entry name.

    Returns
    -------
    dict[str, _EventsData]
        The event types of the interface, keyed by ``event_type_source_id``.

    Raises
    ------
    ValueError
        If two event types get the same identifier.
    """
    events_by_identifier = {}
    origins = {}  # identifier -> where the event type came from, to explain a collision
    for entry_name, events in events_by_entry.items():
        separation = resolved_configuration[entry_name].get("separation")
        if separation is None:
            groups = [(entry_name, f"entry {entry_name!r}", slice(None))]
        else:
            fields = separation["by_payload_fields"]
            indices_by_values = {}
            for index in range(len(events.timestamps)):
                values = []
                for field in fields:
                    value = events.payload[field][index]
                    values.append(value.item() if isinstance(value, np.generic) else value)
                indices_by_values.setdefault(tuple(values), []).append(index)

            selection = separation.get("select")
            if selection is None:
                requested = list(indices_by_values)
            elif len(fields) == 1:
                requested = list(dict.fromkeys((value,) for value in selection))
            else:
                requested = list(dict.fromkeys(tuple(item[field] for field in fields) for item in selection))

            groups = [
                (
                    "_".join([entry_name, *(str(value) for value in values)]),
                    f"entry {entry_name!r} with {dict(zip(fields, values))}",
                    np.asarray(indices_by_values.get(values, []), dtype=int),
                )
                for values in requested
            ]

        for identifier, origin, indices in groups:
            if identifier in origins:
                raise ValueError(
                    f"Two event types get the identifier {identifier!r}: {origins[identifier]} and {origin}."
                )
            origins[identifier] = origin
            events_by_identifier[identifier] = replace(
                events,
                event_type_source_id=identifier,
                timestamps=events.timestamps[indices],
                durations=None if events.durations is None else events.durations[indices],
                payload={field: field_values[indices] for field, field_values in events.payload.items()},
            )
    return events_by_identifier


def _detect_on_line_changes(entry: dict, edges) -> tuple[np.ndarray, np.ndarray | None]:
    """Read an ``on_change`` entry on a source whose hardware captured each change of a line, such as Open Ephys
    hardware events.

    Each change is an edge the hardware already timestamped, so nothing is detected in samples: the entry picks the edges of the
    line in ``detection.lines``, which is line 0 when the entry names none. With only an ``onset`` the
    occurrences are that line's edges of that direction, or all of them for ``"either"``. With an ``end``
    each onset edge is paired with the next end edge on the same line into one occurrence. An onset
    followed by another onset, or by nothing, stays open. An end edge with no open onset closes a period
    whose onset was not recorded, and is dropped.

    Parameters
    ----------
    entry : dict
        The entry as ``BaseEventsInterface._resolve_event_sources`` returns it.
    edges : _EventsData
        The line changes in time order, whose payload holds the ``line`` of each edge, counted from 0, and
        its ``onset``, ``"rising"`` or ``"falling"``.

    Returns
    -------
    onset_indices : numpy.ndarray
        The index of the edge that starts each occurrence.
    end_indices : numpy.ndarray or None
        ``None`` without an ``end``. Otherwise the index of the edge that closes each occurrence, or ``-1``
        for an occurrence that stays open.
    """
    lines = edges.payload["line"]
    onsets = edges.payload["onset"]
    detection = entry["detection"]
    line = detection.get("lines", [0])[0]
    onset = detection["on_change"]["onset"]
    end = detection["on_change"].get("end")
    line_indices = np.flatnonzero(lines == line)

    if end is None:
        if onset == "either":
            return line_indices, None
        return line_indices[onsets[line_indices] == onset], None

    onset_indices, end_indices = [], []
    open_index = None
    for index in line_indices:
        if onsets[index] == onset:
            if open_index is not None:
                onset_indices.append(open_index)
                end_indices.append(-1)
            open_index = index
        elif open_index is not None:
            onset_indices.append(open_index)
            end_indices.append(index)
            open_index = None
    if open_index is not None:
        onset_indices.append(open_index)
        end_indices.append(-1)
    return np.array(onset_indices, dtype="int64"), np.array(end_indices, dtype="int64")


def _add_events_to_nwbfile(nwbfile: NWBFile, *, events_data: dict, metadata: dict, metadata_key: str) -> None:
    """Write one interface's events as ``pynwb.event.EventsTable`` objects inside ``nwbfile.events``.

    The writer behind ``BaseEventsInterface.add_to_nwbfile``, whose docstring describes the tables it builds.

    An ``EventTables`` entry whose ``type`` is ``"EthogramEvents"`` builds an ``ndx-ethogram`` ``EthogramEvents``
    instead of a plain ``EventsTable``, as the ``type`` of a ``Devices`` entry picks a device subclass. Its rows name
    their behavior in ``label`` instead of ``event_type``, and it links the catalogue its ``ethogram_metadata_key``
    names, which must already be in the file.

    Parameters
    ----------
    nwbfile : NWBFile
        The NWB file to add the events to.
    events_data : dict
        The ``_EventsData`` of each event type, keyed by ``event_type_source_id``, with its timestamps and
        durations on the interface's current clock.
    metadata : dict
        Metadata dictionary with the ``Events`` field.
    metadata_key : str
        The key of the interface's block in ``metadata["Events"]``.
    """
    _validate_metadata_key(metadata, metadata_path=("Events",), metadata_key=metadata_key)
    _validate_metadata_path(metadata, ("Events", metadata_key, "event_types"))
    events_metadata = metadata["Events"]
    event_tables_metadata = events_metadata.get("EventTables", {})

    # Event types writing one shared column must declare it consistently. Several event types may write the
    # same `column_name` into one merged table (they share a `table_metadata_key`); the output column is then
    # the union of their declarations. That union is well defined only where the declarations agree: a label
    # both types explain must get the same meaning, and a description both types set must match. Raw codes
    # are not compared across contributors, because each source's codes are private (two sources may reuse
    # the same integer for different labels, which is a legitimate heterogeneous merge, not a conflict).
    # Where declarations do not overlap it is a contribution, not a conflict. The whole `Events` metadata is
    # checked at once, so an inconsistency is caught before anything is written, whether the contributors
    # live in one interface or several (a converter passes every interface's block in the one dict). Only
    # genuine merges are checked: a table with a declared `EventTables` entry, or one that more than one type
    # in a single interface routes to. Two interfaces that merely leave `table_metadata_key` unset (so it
    # defaults to each type's own `event_type_source_id`) are not a shared table even if those defaults
    # coincide.
    #
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
            block_table_counts[(interface_key, table_key)] = block_table_counts.get((interface_key, table_key), 0) + 1
            for spec in entry.get("columns", {}).values():
                declarations.setdefault((table_key, spec["column_name"]), []).append(
                    (entry["event_name"], interface_key, spec)
                )

    for (table_key, column_name), decls in declarations.items():
        is_merge_table = table_key in event_tables_metadata or any(
            count >= 2 for (_interface, key), count in block_table_counts.items() if key == table_key
        )
        if len(decls) < 2 or not is_merge_table:
            continue
        table_display = event_tables_metadata.get(table_key, {}).get("table_name", table_key)
        label_to_meaning = {}  # display label -> (meaning, event_name, interface_key)
        described_by = None  # (description, event_name, interface_key) for the first non-empty description
        for event_name, interface_key, spec in decls:
            # A conflict is the detail of the disagreement and the (value, event_name, interface_key) of the
            # type this one disagrees with.
            conflict = None
            categories = spec.get("column_categories") or {}
            labels = {str(code): label for code, label in categories.get("labels", {}).items()}
            meanings = {str(code): meaning for code, meaning in categories.get("meanings", {}).items()}
            for code, meaning in meanings.items():
                label = labels.get(code, code)
                prior = label_to_meaning.setdefault(label, (meaning, event_name, interface_key))
                if prior[0] != meaning:
                    conflict = (f"label '{label}' means '{prior[0]}' vs '{meaning}'", prior)
                    break
            description = spec.get("description", "")
            if conflict is None and description:
                described_by = described_by or (description, event_name, interface_key)
                if described_by[0] != description:
                    conflict = (f"description '{described_by[0]}' vs '{description}'", described_by)
            if conflict is not None:
                detail, (_, first_name, first_interface) = conflict
                raise ValueError(
                    f"Event types '{first_name}' (interface '{first_interface}') and '{event_name}' "
                    f"(interface '{interface_key}') disagree on column '{column_name}' in the shared events "
                    f"table '{table_display}': {detail}. A column shared across event types must be declared "
                    f"consistently (matching labels, meanings, and description where they overlap); reconcile "
                    f"the declarations or use distinct column_names."
                )

    event_types = events_metadata[metadata_key]["event_types"]

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

        is_ethogram_events = declared_entry is not None and declared_entry.get("type") == "EthogramEvents"
        # An ethogram record names each row's behavior in its required `label` column, the catalogue's term.
        type_column_name = "label" if is_ethogram_events else "event_type"
        existing_table = nwbfile.events.get(table_name) if nwbfile.events is not None else None
        # The user asks to combine several event types into one table by declaring an EventTables entry
        # or by routing more than one type to the same table_metadata_key; either needs an event_type
        # column. A table another interface already wrote continues such a combine.
        wants_merge = declared_entry is not None or len(event_type_source_ids) > 1
        is_merge = wants_merge or existing_table is not None
        if existing_table is not None and type_column_name not in existing_table.colnames:
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
        if existing_table is not None:
            table = existing_table
        elif is_ethogram_events:
            from ndx_ethogram import EthogramEvents

            # The record links its catalogue as a device links its model: by key, to an object already in
            # the file. ndx-ethogram requires the link, so the catalogue is written before the events.
            ethogram_metadata_key = declared_entry["ethogram_metadata_key"]
            _validate_metadata_key(
                metadata, metadata_path=("Behavior", "Ethograms"), metadata_key=ethogram_metadata_key
            )
            catalogue_name = metadata["Behavior"]["Ethograms"][ethogram_metadata_key]["name"]
            behavior_module = nwbfile.processing.get("behavior")
            catalogue = behavior_module.data_interfaces.get(catalogue_name) if behavior_module is not None else None
            if catalogue is None:
                raise ValueError(
                    f"The events table '{table_name}' links the catalogue '{catalogue_name}', which is not in the "
                    "file's behavior module. Write the catalogue before the events that link it."
                )
            table = EthogramEvents(
                name=table_name,
                description=description,
                labeling_method=declared_entry["labeling_method"],
                ethogram=catalogue,
                source_software=declared_entry.get("source_software"),
                annotator=declared_entry.get("annotator"),
            )
        else:
            table = EventsTable(name=table_name, description=description)
        if is_ethogram_events:
            catalogued_behaviors = set(table.ethogram["behavior"].data)
            for event_type_source_id in event_type_source_ids:
                event_name = event_types[event_type_source_id]["event_name"]
                if event_name not in catalogued_behaviors:
                    raise ValueError(
                        f"Event type '{event_type_source_id}' writes the label '{event_name}' into "
                        f"'{table_name}', but its catalogue '{table.ethogram.name}' has no behavior of that "
                        "name. An event_name renamed in metadata must be renamed in the catalogue too."
                    )
        _append_events_to_table(
            table=table,
            events_data=events_data,
            event_types=event_types,
            event_type_source_ids=event_type_source_ids,
            is_merge=is_merge,
            type_column_name=type_column_name,
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
    *,
    table: EventsTable,
    events_data: dict,
    event_types: dict,
    event_type_source_ids: list,
    is_merge: bool,
    type_column_name: str,
) -> None:
    """Append this interface's events to ``table``, creating whatever columns that data needs.

    Builds this interface's rows, ensures its value columns exist (backfilling rows already on the
    table) with a ``MeaningsTable`` for any categorical column, sets up or extends the ``event_type``
    discriminator and its ``MeaningsTable`` when merging, then adds the rows. The caller owns the
    table's identity, registration, and final re-sort; this method only fills the table it is handed.
    ``type_column_name`` is the column holding each row's ``event_name``: ``event_type``, or ``label`` in an
    ``EthogramEvents``.
    """
    event_data = events_data

    # Flatten this interface's types into rows (timestamp, event_name, duration, cells) and collect the
    # value-column specs keyed by column_name.
    rows = []
    column_specs = {}
    column_dtypes = {}
    # A payload field may hold several values per event rather than one, a behavior scored with two
    # qualifiers at once or a trial tagged with three conditions. Those become a ragged column, and
    # which columns those are is read off the data rather than declared: a metadata flag would be a
    # second place for the same fact to live and to disagree.
    ragged_column_names = set()
    for event_type_source_id in event_type_source_ids:
        event = event_data[event_type_source_id]
        timestamps = event.timestamps
        durations = event.durations
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
            # checked for consistency up front by _add_events_to_nwbfile); record it once, then let
            # each type fill its own rows below.
            column_specs.setdefault(column_name, column_spec)
            values = event.payload[field_source_id]
            if isinstance(values, np.ndarray) and values.dtype.kind in "biufSU":
                column_dtypes.setdefault(column_name, []).append(values.dtype)
            # A string is a scalar even though it is iterable, and a numpy string scalar likewise, so the test
            # is for the container types a payload actually uses to mean "more than one".
            if any(
                isinstance(value, (list, tuple, set)) or (isinstance(value, np.ndarray) and value.ndim > 0)
                for value in values
            ):
                ragged_column_names.add(column_name)
            # The raw-value to display-label map of a categorical column, else None. Keys are stringified so a
            # value that survives a JSON round trip (metadata keys become strings) still matches.
            categories = column_spec.get("column_categories")
            labels_map = {str(key): label for key, label in categories["labels"].items()} if categories else None
            resolved_columns.append((field_source_id, column_name, labels_map))
        for index, timestamp in enumerate(timestamps):
            cells = {}
            for field_source_id, column_name, labels_map in resolved_columns:
                value = event.payload[field_source_id][index]
                if labels_map is None:
                    cells[column_name] = value
                elif isinstance(value, (list, tuple, set)) or (isinstance(value, np.ndarray) and value.ndim > 0):
                    cells[column_name] = [labels_map[str(item)] for item in value]
                else:
                    cells[column_name] = labels_map[str(value)]
            duration = float(durations[index]) if durations is not None else np.nan
            rows.append((float(timestamp), event_name, duration, cells))

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
    if is_merge and type_column_name not in table.colnames:
        table.add_column(
            name=type_column_name,
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
                dtypes = column_dtypes.get(column_name, [])
                if categories is not None:
                    empty_dtype = str
                elif dtypes and all(dtype.kind == dtypes[0].kind for dtype in dtypes):
                    empty_dtype = np.result_type(*dtypes)
                else:
                    empty_dtype = float
                table.add_column(
                    name=column_name,
                    description=column_spec.get("description", ""),
                    data=np.array([], dtype=empty_dtype) if stays_empty else [fill] * n_existing,
                )
        elif is_ragged and not isinstance(table[column_name], VectorIndex):
            raise ValueError(
                f"Column '{column_name}' on table '{table.name}' holds one value per event, and this "
                "interface writes several. A column is one shape or the other for every contributor."
            )
        elif not is_ragged and isinstance(table[column_name], VectorIndex):
            # The mirror of the case above, and the one that fails silently without this: a scalar
            # handed to a ragged column reaches `VectorIndex.add_vector`, which extends the values
            # with it, so a string is appended one character at a time.
            raise ValueError(
                f"Column '{column_name}' on table '{table.name}' holds several values per event, and "
                "this interface writes one. A column is one shape or the other for every contributor."
            )
        # Only a meaning the user actually wrote earns a row: a column whose meanings are all empty
        # gets no MeaningsTable rather than a table of empty strings, and a partly annotated column
        # keeps just the entries that were filled in.
        meanings = {
            raw_value: meaning for raw_value, meaning in ((categories or {}).get("meanings") or {}).items() if meaning
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
    # at all rather than one restating each event_name back at the reader. An ethogram record's labels
    # are defined by its catalogue, so its label column gets none.
    if is_merge and type_column_name == "event_type":
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
    value_column_names = [name for name in table.colnames if name not in ("timestamp", "duration", type_column_name)]
    for timestamp, event_name, duration, cells in rows:
        row_kwargs = {"timestamp": timestamp}
        if table_has_duration:
            row_kwargs["duration"] = duration
        if is_merge:
            row_kwargs[type_column_name] = event_name
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
        table.add_row(**row_kwargs)


def _to_table_object_name(name: str) -> str:
    """CamelCase a derived table name for use as an NWB object name, but keep an already-cased
    identifier verbatim so a raw source id is not mangled.

    A snake_case or all-lowercase ``name`` is CamelCased (``port_entries`` -> ``PortEntries``); a name
    that already carries mixed/upper casing and no underscore (a raw ``event_type_source_id`` like
    ``PtAB`` or ``XD0``) is returned unchanged, because ``to_camel_case("PtAB")`` would lowercase the
    rest and give ``"Ptab"``.

    The two characters NWB rejects in an object name are replaced here rather than by the interface that
    supplies the name, since this is the only place the name has to satisfy that constraint. Everywhere
    else an ``event_name`` goes, the ``event_type`` column and its ``MeaningsTable``, any string is legal,
    and a source identifier is worth more there intact: ``Grooming/Eating`` is an ordinary way to name one
    behavior covering two things, and only the object name derived from it needs repairing.
    ``to_camel_case`` does not remove them, so ``"Foraging/Caching"`` would otherwise reach a name as
    ``"Foraging/caching"``.
    """
    name = name.replace("/", "_").replace(":", "_")
    return to_camel_case(name) if ("_" in name or name.islower()) else name
