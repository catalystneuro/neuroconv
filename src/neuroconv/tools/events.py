"""Tools for the discrete-events data interfaces."""

# The alternative cuts: three routes to a discrete-valued signal, exactly one of which may appear in a
# spec's signal_conditioning. Which one is legal is decided by the signal's kind, not by the caller.
_CUTS = ("bits", "thresholds", "binarize")
# hysteresis is a parameter of the cut rather than an operation of its own, and debounce is the only
# genuine second operation, always running after the cut. Hence a dict rather than an ordered list:
# there is no free sequence to express, so no arrangement can be typed that would then be rejected.
_CONDITIONING_KEYS = _CUTS + ("hysteresis", "debounce")
_SPEC_KEYS = ("signal_conditioning", "detection", "event_name")


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
        The signals discovered in the file, keyed by ``signal_source_id``. Each value is a descriptor
        whose ``kind`` is ``"line"`` (one digital line), ``"word"`` (a packed integer), ``"analog"`` (a
        continuous trace), or ``None`` when the format records no kind. The kind decides which cut is
        legal and whether ``signal_conditioning`` may be omitted.

    Raises
    ------
    ValueError
        If the configuration is empty, names a signal not in ``available_signals``, gives a signal an
        empty list, or holds a malformed spec: an unrecognized key, no ``detection``, more than one cut,
        a ``hysteresis`` with no cut, or a cut the signal's kind does not admit.
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
        kind = available_signals[signal_source_id].get("kind")
        for spec in specs:
            _validate_spec(spec=spec, signal_source_id=signal_source_id, kind=kind)


def _validate_spec(spec: dict, signal_source_id: str, kind: str | None) -> None:
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
        # Omitting conditioning asserts the signal is already discrete-valued. That assertion is checked
        # structurally: a line qualifies, a packed word does not (it is several signals until the caller
        # says which bits form one value), and an analog trace does not (nothing decides which values
        # count as high). A signal whose kind the format does not record is admitted here and caught by
        # the read-time backstop instead.
        if kind == "word":
            raise ValueError(
                f"'{signal_source_id}' is a packed word, so its spec needs signal_conditioning with "
                "'bits' saying which bit positions to read. A word is several signals until you say "
                "which bits form one value."
            )
        if kind == "analog":
            raise ValueError(
                f"'{signal_source_id}' is an analog signal, so its spec needs signal_conditioning with "
                "'thresholds' saying where to cut it. There is no defensible default cut."
            )
        return

    if not isinstance(conditioning, dict):
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' must be a dict of conditioning settings, got "
            f"{type(conditioning).__name__}."
        )
    unknown_keys = set(conditioning) - set(_CONDITIONING_KEYS)
    if unknown_keys:
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' has unrecognized key(s) {sorted(unknown_keys)}. "
            f"Valid settings are {list(_CONDITIONING_KEYS)}."
        )
    cuts = [cut for cut in _CUTS if cut in conditioning]
    if len(cuts) > 1:
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' sets more than one cut ({cuts}). 'bits', "
            "'thresholds' and 'binarize' are alternative routes to a discrete-valued signal, so exactly "
            "one of them applies."
        )
    if "hysteresis" in conditioning and not cuts:
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' sets 'hysteresis' with no cut. Hysteresis is "
            "a dead band around a cut, so it needs a 'thresholds' or 'binarize' to band."
        )
    if "bits" in conditioning and kind not in ("word", None):
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' sets 'bits', but that signal is not a packed "
            "word. Bit selection applies only to a signal that packs several lines into one integer."
        )
    if "thresholds" in conditioning and kind == "line":
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' sets 'thresholds', but that signal is already "
            "a single digital line. Omit signal_conditioning to read its own values."
        )


def resolve_detection_plan(detection_configuration: dict) -> dict[str, tuple[str, dict]]:
    """Resolve a configuration into ``{event_type_source_id: (signal_source_id, spec)}``.

    An event type is (what you read) times (how you read it), so a signal yielding one event type keeps
    its own handle as the identifier and a signal yielding several fans out. Derivation is content-based
    rather than positional: an identifier depends on its own spec's distinguishing components and never
    on the spec's position in the list, so reordering a list renames nothing.

    The rules, in order:

    1. One spec for a signal: the identifier is the ``signal_source_id`` unchanged, which keeps a
       zero-configuration conversion's identifiers equal to the strings the acquisition software shows.
    2. Several specs: the identifier is the signal handle plus every distinguishing component present,
       in pipeline order, giving ``XD0_bit0_rising`` or ``DIN-01_rising`` / ``DIN-01_falling``. Every
       component is included rather than only the differing ones, so adding a spec later does not
       rename its siblings.
    3. A spec's ``event_name`` replaces the derived identifier entirely. Set it when you want an
       identifier pinned against later edits, since a signal going from one spec to several moves it
       from rule 1 to rule 2 and the derived form changes.
    4. Identifiers must be unique across the whole configuration.
    5. ``event_name`` is required when the identifier is not safely derivable, meaning any fan-out whose
       distinguishing components go beyond the detection value and a single-bit ``bits``: a multi-bit
       field or a ``thresholds`` fan-out, neither of which stringifies into a stable valid name.

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
        If a fan-out spec needs an ``event_name`` and has none, or if two event types resolve to the
        same identifier.
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
                event_type_source_id = _derive_event_type_source_id(signal_source_id=signal_source_id, spec=spec)
            if event_type_source_id in detection_plan:
                raise ValueError(
                    f"detection_configuration resolves two event types to the same identifier "
                    f"'{event_type_source_id}'. Set 'event_name' on one of them to tell them apart."
                )
            detection_plan[event_type_source_id] = (signal_source_id, spec)
    return detection_plan


def _derive_event_type_source_id(signal_source_id: str, spec: dict) -> str:
    """Build a fan-out spec's identifier from its signal handle plus its distinguishing components."""
    conditioning = spec.get("signal_conditioning") or {}
    if "thresholds" in conditioning:
        raise ValueError(
            f"'{signal_source_id}' fans out on 'thresholds', whose cut points do not stringify into a "
            "stable identifier. Give each of its specs an 'event_name'."
        )
    components = []
    if "bits" in conditioning:
        bits = conditioning["bits"]
        if len(bits) != 1:
            raise ValueError(
                f"'{signal_source_id}' fans out on the multi-bit field {list(bits)}, whose derived "
                "identifier would be unwieldy. Give each of its specs an 'event_name'."
            )
        components.append(f"bit{bits[0]}")
    components.append(spec["detection"])
    return "_".join([signal_source_id, *components])
