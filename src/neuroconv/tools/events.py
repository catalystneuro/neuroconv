"""Tools for the discrete-events data interfaces.

Everything here is private. It is the shared implementation the signal-encoded events interfaces call,
not a surface anyone should import: a caller writes a ``detection_configuration`` and hands it to an
interface, which is where the documented contract lives.
"""

# The alternative cuts: three routes to a discrete-valued signal, exactly one of which may appear in a
# spec's signal_conditioning. Which one is legal is decided by the signal's kind, not by the caller.
# These are also the *only* settings signal_conditioning recognizes: hysteresis and debounce are designed
# but unbuilt, so they hit the unrecognized-key error rather than validating and doing nothing, which is
# the silent-discard failure this validation exists to remove. They land with their implementation.
_CUTS = ("bits", "thresholds", "binarize")
_SPEC_KEYS = ("signal_conditioning", "detection", "event_name")


def _validate_detection_configuration(detection_configuration: dict, available_signals: dict) -> None:
    """Validate a ``detection_configuration``, raising ``ValueError`` on a bad entry.

    The one construction-time check. It answers both "is this well formed" (per-spec structure, checked
    against each signal's kind) and "do its identifiers resolve" (rules 4 and 5), so an interface calls
    this and nothing else. It is called on the interface's own default configuration too, not only on a
    caller-supplied one: a default is machine-built, but its inputs are not, so it can still resolve two
    event types to the same identifier.

    A shared helper for the signal-encoded events interfaces (each derives events from a sampled
    signal). ``detection_configuration`` maps each ``signal_source_id`` to a **list** of detection
    specs, one per event type derived from that signal. A spec is all-or-nothing: pass ``None`` instead
    of a configuration to read every signal with the interface's default reading, or name signals and
    state each spec in full. A half-filled spec is an error rather than a silent fallback, so the
    reading an event type is written with is always one the caller chose.

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
        legal and whether ``signal_conditioning`` may be omitted. A word may additionally declare
        ``bits``, the line positions it carries, which is checked against the positions a spec asks
        for. Everything else in the descriptor is the interface's own addressing and stays opaque here.

    Raises
    ------
    ValueError
        If the configuration is empty, names a signal not in ``available_signals``, gives a signal
        something other than a non-empty list, or holds a malformed spec: an unrecognized key, no
        ``detection``, more than one cut, a cut the signal's kind does not admit, or a bit position the
        word does not carry. Also if the configuration's identifiers do not resolve: two event types
        reaching the same identifier (rule 4) or a fan-out whose components do not stringify into a
        stable name (rule 5).
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
        _validate_omission(signal_source_id=signal_source_id, kind=kind)
        return

    if not isinstance(conditioning, dict):
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' must be a dict of conditioning settings, got "
            f"{type(conditioning).__name__}."
        )
    if not conditioning:
        # An empty dict is not a quiet spelling of omission, and treating it as one would make it a way
        # around the check omission gets: a word would pass here and then be read whole as if it were a
        # line. Empty containers raise everywhere else in this grammar (the configuration itself, a
        # signal's spec list, 'bits', 'thresholds'), so this is that rule rather than a new one.
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' is an empty dict, which states nothing. Drop "
            f"the key to read the signal's own values, which is an assertion checked against its kind, "
            f"or set one of {list(_CUTS)}."
        )
    unknown_keys = set(conditioning) - set(_CUTS)
    if unknown_keys:
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' has unrecognized key(s) {sorted(unknown_keys)}. "
            f"Valid settings are {list(_CUTS)}."
        )
    cuts = [cut for cut in _CUTS if cut in conditioning]
    if len(cuts) > 1:
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' sets more than one cut ({cuts}). 'bits', "
            "'thresholds' and 'binarize' are alternative routes to a discrete-valued signal, so exactly "
            "one of them applies."
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
    if "thresholds" in conditioning and kind == "line":
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' sets 'thresholds', but that signal is already "
            "a single digital line. Omit signal_conditioning to read its own values."
        )
    if kind == "word" and cuts != ["bits"]:
        # The other half of the word's own rule, and the same argument that rejects omission on one: a
        # word is several signals until the caller says which bits form one value, so cutting its integer
        # at a magnitude reads a bit pattern as a number. Values 0, 1, 2, 3 on a two-line word are four
        # combinations of two independent lines, not four levels of one signal, and a threshold at 1.5
        # asks which of them are "large". 'binarize' is the same mistake with the cut derived instead of
        # given. Without this a word reached its cuts through a route omission was closed off from.
        raise ValueError(
            f"signal_conditioning for '{signal_source_id}' cuts a packed word with '{cuts[0]}', which "
            "reads its bit pattern as a magnitude. A word is several signals until you say which bits "
            "form one value, so name the line you want with 'bits'."
        )


def _validate_omission(signal_source_id: str, kind: str | None) -> None:
    """Check the assertion that omitting ``signal_conditioning`` makes, structurally and with no data read.

    Omission says the signal is already discrete-valued. A line qualifies. A packed word does not, since
    it is several signals until the caller says which bits form one value. An analog trace does not,
    since nothing decides which of its values count as high. A signal whose kind the format does not
    record is admitted here and left to the read-time backstop in
    :func:`~neuroconv.tools.signal_processing._detect_events`.
    """
    if kind == "word":
        raise ValueError(
            f"'{signal_source_id}' is a packed word, so its spec needs signal_conditioning with 'bits' "
            "saying which bit positions to read. A word is several signals until you say which bits "
            "form one value."
        )
    if kind == "analog":
        raise ValueError(
            f"'{signal_source_id}' is an analog signal, so its spec needs signal_conditioning with "
            "'thresholds' saying where to cut it. There is no defensible default cut."
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
       spec later does not rename its siblings.
    3. A spec's ``event_name`` replaces the derived identifier entirely. Set it when you want an
       identifier pinned against later edits, since a signal going from one spec to several moves it
       from rule 1 to rule 2 and the derived form changes.
    4. Identifiers must be unique across the whole configuration.
    5. ``event_name`` is required when a fan-out spec cuts with ``thresholds``, whose cut points do not
       stringify into a stable valid name. Stated as an exclusion so absence is fine: a signal with no
       conditioning, or one carving a single bit, derives perfectly well.

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
    if "thresholds" in conditioning:
        raise ValueError(
            f"'{signal_source_id}' fans out on 'thresholds', whose cut points do not stringify into a "
            "stable identifier. Give each of its specs an 'event_name'."
        )
    components = []
    if "bits" in conditioning:
        # Always exactly one bit: the validator rejects a multi-bit spec, since the coded-word reading
        # is deferred until its strobe/debounce guard exists.
        components.append(f"bit{list(conditioning['bits'])[0]}")
    components.append(spec["detection"])
    return "_".join([signal_source_id, *components])
