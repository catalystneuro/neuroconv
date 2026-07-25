"""Tools for the discrete-events data interfaces."""


def validate_event_specs(event_specs: dict, available_lines: dict) -> None:
    """Validate a signal-encoded ``event_specs`` dict's line selection, raising ``ValueError`` on a bad entry.

    A shared helper for the signal-encoded events interfaces (each edge-detects a sampled line): a
    per-interface ``_resolve_event_specs`` calls this before parsing a user-supplied dict. ``event_specs``
    maps each ``event_type_source_id`` to its per-line spec; this checks the dict is non-empty and that
    every entry names a line present in ``available_lines`` (the discovered lines keyed by source id). The
    per-line ``detect`` reading is deliberately not checked here: the edge detector
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
        If ``event_specs`` is empty or names a line not in ``available_lines``.
    """
    if not event_specs:
        raise ValueError(
            "event_specs is empty. Pass None (the default) to derive every line, or name at least one line."
        )
    for source_id in event_specs:
        if source_id not in available_lines:
            raise ValueError(
                f"event_specs names '{source_id}', which is not one of the file's lines: {list(available_lines)}."
            )
