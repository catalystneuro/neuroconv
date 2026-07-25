"""Tools for the discrete-events data interfaces."""

# A detection spec holds the reading and, optionally, a name for the event type it produces. The
# signal-conditioning vocabulary (bits, thresholds, binarize, and the deferred hysteresis and debounce)
# is not here yet: a Doric digital line is already a 0/1 signal, so no conditioning arises for it. Those
# keys land with the first interface that needs them, alongside the shared mock.
_SPEC_KEYS = ("detection", "event_name")


def validate_detection_configuration(detection_configuration: dict, available_signals: dict) -> None:
    """Validate a caller-supplied ``detection_configuration``, raising ``ValueError`` on a bad entry.

    A shared helper for the signal-encoded events interfaces (each derives events from a sampled
    signal). ``detection_configuration`` maps each ``signal_source_id`` to a **list** of detection
    specs, one per event type derived from that signal. A spec is all-or-nothing: pass ``None`` instead
    of a configuration to read every signal with the interface's default reading, or name signals and
    state each spec in full. A half-filled spec is an error rather than a silent fallback, so the
    reading an event type is written with is always one the caller chose.

    The ``detection`` *value* is deliberately not checked here: the edge detector
    (:func:`~neuroconv.tools.signal_processing.discretize_trace`) is the single source of truth for its
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
        ``detection``.
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
            unknown_keys = set(spec) - set(_SPEC_KEYS)
            if unknown_keys:
                raise ValueError(
                    f"detection_configuration spec for '{signal_source_id}' has unrecognized key(s) "
                    f"{sorted(unknown_keys)}. A spec holds 'detection' (which transitions become events) "
                    "and an optional 'event_name'."
                )
            if "detection" not in spec:
                raise ValueError(
                    f"detection_configuration spec for '{signal_source_id}' does not set 'detection'. "
                    "Every spec must state how its signal's transitions become events; pass None instead "
                    "of a detection_configuration to read every signal with the default reading."
                )


def resolve_detection_plan(detection_configuration: dict) -> dict[str, tuple[str, dict]]:
    """Resolve a configuration into ``{event_type_source_id: (signal_source_id, spec)}``.

    An event type is (what you read) times (how you read it), so a signal yielding one event type keeps
    its own handle as the identifier and a signal yielding several fans out. Derivation is content-based
    rather than positional: an identifier depends on its own spec's reading and never on the spec's
    position in the list, so reordering a list renames nothing.

    The rules:

    1. One spec for a signal: the identifier is the ``signal_source_id`` unchanged, which keeps a
       zero-configuration conversion's identifiers equal to the strings the acquisition software shows.
    2. Several specs: the identifier is the signal handle plus the spec's reading, giving
       ``DIN-01_rising`` and ``DIN-01_falling``.
    3. A spec's ``event_name`` replaces the derived identifier entirely. Set it when you want an
       identifier pinned against later edits, since a signal going from one spec to several moves it
       from rule 1 to rule 2 and the derived form changes.
    4. Identifiers must be unique across the whole configuration.

    Parameters
    ----------
    detection_configuration : dict
        A validated ``{signal_source_id: [spec, ...]}`` configuration.

    Returns
    -------
    dict
        ``event_type_source_id -> (signal_source_id, spec)``, one entry per event type to derive.

    Raises
    ------
    ValueError
        If two event types resolve to the same identifier.
    """
    detection_plan: dict[str, tuple[str, dict]] = {}
    for signal_source_id, specs in detection_configuration.items():
        yields_one_event_type = len(specs) == 1
        for spec in specs:
            event_name = spec.get("event_name")
            if event_name is not None:
                event_type_source_id = event_name
            elif yields_one_event_type:
                event_type_source_id = signal_source_id
            else:
                event_type_source_id = f"{signal_source_id}_{spec['detection']}"
            if event_type_source_id in detection_plan:
                raise ValueError(
                    f"detection_configuration resolves two event types to the same identifier "
                    f"'{event_type_source_id}'. Set 'event_name' on one of them to tell them apart."
                )
            detection_plan[event_type_source_id] = (signal_source_id, spec)
    return detection_plan
