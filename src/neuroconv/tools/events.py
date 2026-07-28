"""Tools for the discrete-events data interfaces."""

# A detection spec holds the reading, optionally a name for the event type it produces, and optionally
# the conditioning that reaches a discrete-valued signal. Of the conditioning vocabulary only binarize
# is here: bits, thresholds, and the deferred hysteresis and debounce land with the first interface that
# needs them, alongside the shared mock. Until then they hit the unrecognized-key error rather than
# validating and doing nothing.
_CUTS = ("binarize",)
_SPEC_KEYS = ("signal_conditioning", "detection", "event_name")


def _validate_detection_configuration(detection_configuration: dict, available_signals: dict) -> None:
    """Validate a ``detection_configuration``, raising ``ValueError`` on a bad entry.

    The one construction-time check. It answers both "is this well formed" (per-spec structure) and "do
    its identifiers resolve" (rule 4), so an interface calls this and nothing else. It is called
    on the interface's own default configuration too, not only on a caller-supplied one: a default is
    machine-built, but its inputs are not, so it can still resolve two event types to the same
    identifier.

    A shared helper for the signal-encoded events interfaces (each derives events from a sampled
    signal). ``detection_configuration`` maps each ``signal_source_id`` to a **list** of detection
    specs, one per event type derived from that signal. A spec is all-or-nothing: pass ``None`` instead
    of a configuration to read every signal with the interface's default reading, or name signals and
    state each spec in full. A half-filled spec is an error rather than a silent fallback, so the
    reading an event type is written with is always one the caller chose.

    The ``detection`` *value* is deliberately not checked here: the edge detector
    (:func:`~neuroconv.tools.signal_processing._detect_events`) is the single source of truth for its
    valid values and raises on an invalid one.

    Parameters
    ----------
    detection_configuration : dict
        The caller-supplied ``{signal_source_id: [spec, ...]}`` configuration to validate.
    available_signals : dict
        The signals discovered in the file, keyed by ``signal_source_id``. Only the keys are read here;
        the values are the interface's own addressing and stay opaque to this function.

    Raises
    ------
    ValueError
        If the configuration is empty, names a signal not in ``available_signals``, gives a signal
        something other than a non-empty list, or holds a spec with an unrecognized key or no
        ``detection``. Also if two event types resolve to the same identifier.
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
        for spec in specs:
            _validate_spec(spec=spec, signal_source_id=signal_source_id)
    _resolve_event_types(detection_configuration)  # raises if two event types resolve to one identifier


def _validate_spec(spec: dict, signal_source_id: str) -> None:
    """Validate one detection spec, raising ``ValueError`` naming the stage that rejected it."""
    unknown_keys = set(spec) - set(_SPEC_KEYS)
    if unknown_keys:
        raise ValueError(
            f"detection_configuration spec for '{signal_source_id}' has unrecognized key(s) "
            f"{sorted(unknown_keys)}. A spec holds 'signal_conditioning' (how to reach a discrete-valued "
            "signal), 'detection' (which transitions become events), and an optional 'event_name'."
        )
    if "detection" not in spec:
        raise ValueError(
            f"detection_configuration spec for '{signal_source_id}' does not set 'detection'. Every "
            "spec must state how its signal's transitions become events; pass None instead of a "
            "detection_configuration to read every signal with the default reading."
        )

    conditioning = spec.get("signal_conditioning")
    if conditioning is None:
        # Omission asserts the signal is already discrete-valued, which is the ordinary case for a
        # recorded digital line. Whether the assertion holds is checked at read time by the backstop in
        # :func:`~neuroconv.tools.signal_processing._detect_events`.
        return

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


def _resolve_event_types(detection_configuration: dict) -> list[tuple[str, str, dict]]:
    """The derivation itself: ``(event_type_source_id, signal_source_id, spec)``, in configuration order.

    The single place an identifier is computed or the cross-signal uniqueness check is run. The two
    views over it are independent thin wrappers, so each depends only on the ``detection_configuration``
    and never on the other.

    The rules, in order:

    1. One spec for a signal: the identifier is the ``signal_source_id`` unchanged, which keeps a
       zero-configuration conversion's identifiers equal to the strings the acquisition software shows.
    2. Several specs: the identifier is the signal handle plus the spec's reading, giving
       ``DIN-01_rising`` and ``DIN-01_falling``.
    3. A spec's ``event_name`` replaces the derived identifier entirely. Set it when you want an
       identifier pinned against later edits, since a signal going from one spec to several moves it
       from rule 1 to rule 2 and the derived form changes.
    4. Identifiers must be unique across the whole configuration.

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
    signal** because reading is per signal while deriving is per event type: a line read as both a
    rising and a falling event type is one read and two derivations, not two reads, which is the
    difference that matters once a signal is hours of 30 kHz samples.

    The grouping mirrors the ``detection_configuration``'s own, so the plan is that configuration with
    each spec annotated by the identifier it resolves to. Entries come back in configuration order
    (signals in their configured order, each signal's specs in list order), which is the order the
    metadata and the writer present event types in.

    An event type is (what you read) times (how you read it), so a signal yielding one event type keeps
    its own handle as the identifier and a signal yielding several fans out. Derivation is content-based
    rather than positional: an identifier depends on its own spec's reading and never on the spec's
    position in the list, so reordering a list renames nothing. The rules are in
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
        ``signal_source_id -> [(event_type_source_id, spec), ...]``, one entry per signal to read and,
        inside it, one spec per event type to derive from that signal, each paired with the identifier it
        resolves to.

    Raises
    ------
    ValueError
        If two event types resolve to the same identifier.
    """
    detection_plan: dict[str, list[tuple[str, dict]]] = {}
    for event_type_source_id, signal_source_id, spec in _resolve_event_types(detection_configuration):
        detection_plan.setdefault(signal_source_id, []).append((event_type_source_id, spec))
    return detection_plan


def _get_event_type_source_ids(detection_configuration: dict) -> list[str]:
    """The identifiers a ``detection_configuration`` resolves to, in configuration order.

    Everything ``get_metadata`` sees of the configuration, deliberately. Metadata names event types; it
    has no business with how they are read, so it gets identifiers and not specs.
    """
    return [event_type_source_id for event_type_source_id, _, _ in _resolve_event_types(detection_configuration)]


def _derive_event_type_source_id(signal_source_id: str, spec: dict) -> str:
    """Build a fan-out spec's identifier from its signal handle plus the reading that distinguishes it."""
    return f"{signal_source_id}_{spec['detection']}"
