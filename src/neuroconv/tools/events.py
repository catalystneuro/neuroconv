"""Tools for the discrete-events data interfaces."""


def validate_event_specs(event_specs: dict, available_lines: dict) -> None:
    """Validate a signal-encoded ``event_specs`` dict, raising ``ValueError`` on a bad entry.

    A shared helper for the signal-encoded events interfaces (each edge-detects a sampled line), called
    on a user-supplied dict before it is used. ``event_specs`` maps each ``event_type_source_id`` to its
    per-line spec; this checks the dict is non-empty, that every entry names a line present in
    ``available_lines`` (the discovered lines keyed by source id), and that every entry sets its
    ``detect``. A spec is all-or-nothing: pass ``None`` to read every line with the interface's default
    reading, or name lines and state each one's reading in full. A half-filled entry is an error rather
    than a silent fallback, so the reading a line is written with is always one the caller chose. The
    ``detect`` *value* is deliberately not checked here: the edge detector
    (:func:`~neuroconv.tools.signal_processing.discretize_trace`) is the single source of truth for its
    valid values and raises on an invalid one.

    Parameters
    ----------
    event_specs : dict
        The user-supplied ``{event_type_source_id: {...}}`` config to validate.
    available_lines : dict
        The lines discovered in the file, keyed by ``event_type_source_id``; every ``event_specs`` key
        must be one of these.

    Raises
    ------
    ValueError
        If ``event_specs`` is empty, names a line not in ``available_lines``, or has an entry with no
        ``detect``.
    """
    if not event_specs:
        raise ValueError(
            "event_specs is empty. Pass None (the default) to derive every line, or name at least one line."
        )
    for source_id, entry in event_specs.items():
        if source_id not in available_lines:
            raise ValueError(
                f"event_specs names '{source_id}', which is not one of the file's lines: {list(available_lines)}."
            )
        if "detect" not in entry:
            raise ValueError(
                f"event_specs entry for '{source_id}' does not set 'detect'. Every named line must state "
                "how its transitions become events; pass None instead of event_specs to read every line "
                "with the default reading."
            )
