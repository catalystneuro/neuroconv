import numpy as np


def get_rising_frames_from_ttl(trace: np.ndarray, threshold: float | None = None) -> np.ndarray:
    """
    Return the frame indices for rising events in a TTL pulse.

    Parameters
    ----------
    trace : numpy.ndarray
        A TTL signal.
    threshold : float, optional
        The threshold used to distinguish on/off states in the trace.
        The mean of the trace is used by default.

    Returns
    -------
    rising_frames : numpy.ndarray
        The frame indices of rising events.
    """
    flattened_trace = np.ravel(trace)  # Shapes like (1, x, 1, 1) might result from slicing patterns and are allowed
    if np.max(trace.shape) != flattened_trace.shape[0]:  # TODO: when 3.7 dropped, use math.prod to avoid overflow
        raise ValueError(f"This function expects a one-dimensional array! Received shape of {trace.shape}.")

    threshold = np.mean(trace) if threshold is None else threshold

    sign = np.sign(flattened_trace - threshold)
    diff = np.diff(sign)
    rising_frames = np.where(diff > 0)[0] + 1

    return rising_frames


def get_falling_frames_from_ttl(trace: np.ndarray, threshold: float | None = None) -> np.ndarray:
    """
    Return the frame indices for falling events in a TTL pulse.

    Parameters
    ----------
    trace : numpy.ndarray
        A TTL signal.
    threshold : float, optional
        The threshold used to distinguish on/off states in the trace.
        The mean of the trace is used by default.

    Returns
    -------
    falling_frames : numpy.ndarray
        The frame indices of falling events.
    """
    flattened_trace = np.ravel(trace)  # Shapes like (1, x, 1, 1) might result from slicing patterns and are allowed
    if np.max(trace.shape) != flattened_trace.shape[0]:  # TODO: when 3.7 dropped, use math.prod to avoid overflow
        raise ValueError(f"This function expects a one-dimensional array! Received shape of {trace.shape}.")

    threshold = np.mean(trace) if threshold is None else threshold

    sign = np.sign(flattened_trace - threshold)
    diff = np.diff(sign)
    falling_frames = np.where(diff < 0)[0] + 1

    return falling_frames


_DETECTION_READINGS = ("rising", "falling", "high_period", "low_period", "value_change")
_CUTS = ("bits", "binarize")
_BINARIZE_METHODS = ("midpoint",)


def _condition_signal(trace: np.ndarray, signal_conditioning: dict) -> np.ndarray:
    """Condition a sampled signal into a line of the same length, on the same timeline.

    The first of the two stages a signal-encoded events source runs (the second is
    :func:`_detect_events`). The boundary between them is where the data type changes: conditioning is
    signal-to-signal, detection is signal-to-events.

    **The postcondition is the contract:** whatever comes back is two-valued, the same length as the
    input, and indexed on the same timeline. Two-valued is what the edge readings need, and having every
    cut guarantee it is why detection needs no check of its own. Length preservation is what lets
    :func:`_detect_events` return frame indices that still address the caller's original timestamps, so a
    step that resampled or dropped samples would silently break the conversion and does not belong here.

    Parameters
    ----------
    trace : numpy.ndarray
        A one-dimensional sampled signal.
    signal_conditioning : dict
        How the signal becomes a line, holding exactly one cut. Which one is legal is decided by the
        signal rather than by the caller:

        - ``{"bits": [i]}`` selects a bit position out of a packed integer word, giving that wire's
          ``0``/``1`` line. Several positions are read together, least-significant first, as one coded
          value; the configuration grammar defers that reading pending its strobe guard.
        - ``{"binarize": c}`` cuts at the number you give, and ``{"binarize": "midpoint"}`` at
          ``(min + max) / 2``, derived from the data. Bands are half-open, so a sample sitting exactly on
          the cut belongs above it, which is ``np.digitize``'s convention.

        Required. A signal that is already a line takes ``{"binarize": "midpoint"}``, which cuts strictly
        between its two levels whatever they are, so the caller need not know them.

    Returns
    -------
    numpy.ndarray
        The conditioned line, same length as ``trace``, in the narrowest signed integer type that holds
        it (see :func:`_smallest_signed_dtype`).

    Raises
    ------
    ValueError
        If ``signal_conditioning`` is not exactly one known cut, or a cut's parameters are unusable.
    """
    if not isinstance(signal_conditioning, dict) or not signal_conditioning:
        raise ValueError(
            "signal_conditioning must be a dict holding exactly one cut, "
            f"{list(_CUTS)}, got {signal_conditioning!r}."
        )
    cuts = [cut for cut in _CUTS if cut in signal_conditioning]
    if len(cuts) != 1:
        raise ValueError(
            f"signal_conditioning {sorted(signal_conditioning)} must hold exactly one cut, {list(_CUTS)}. "
            "Named settings that are designed but unbuilt ('hysteresis', 'debounce') land here."
        )

    if "bits" in signal_conditioning:
        return _select_bits(trace=trace, bits=signal_conditioning["bits"])
    return _binarize(trace=trace, cut=signal_conditioning["binarize"])


def _smallest_signed_dtype(maximum: int) -> np.dtype:
    """The narrowest signed integer type holding ``0 .. maximum``, for a conditioned signal's values.

    Conditioning's output is bounded and tiny (a line is 0/1, a band index by its cut count, a coded word
    by its bit count), while the arrays are whole recordings, so the width is worth choosing rather than
    defaulting to ``int64``. **Signed** so :func:`_detect_events` has nothing to promote before
    differencing, and an integer rather than a boolean, since ``np.diff`` on a boolean array computes
    ``!=`` rather than a difference and would report every transition as a rising edge.
    """
    for candidate in ("int8", "int16", "int32", "int64"):
        if maximum <= np.iinfo(candidate).max:
            return np.dtype(candidate)
    raise ValueError(f"No signed integer type holds {maximum}.")  # unreachable: int64 covers any real case


def _select_bits(trace: np.ndarray, bits) -> np.ndarray:
    """Pull bit positions out of a packed integer word, several read together as one coded value.

    The result is the narrowest **signed** integer type that holds it, which is one byte for the ordinary
    single-bit line. Width follows ``len(bits)`` rather than being fixed, because a coded read builds its
    value with ``<< position`` and ``1 << 7`` already overflows a signed byte. Signed rather than
    unsigned so :func:`_detect_events` has nothing to promote, and never boolean, since ``np.diff`` on a
    boolean array computes ``!=`` rather than a difference and would report every transition as rising.
    """
    bits = list(bits)
    if not bits:
        raise ValueError("signal_conditioning 'bits' is empty; name at least one bit position.")
    dtype = _smallest_signed_dtype(maximum=2 ** len(bits) - 1)
    word = np.asarray(trace)
    # Least-significant first, so bits [0, 1] reads bit 0 as the low bit of the resulting code. A single
    # position therefore gives a plain 0/1 line, which is the common case.
    value = np.zeros(word.shape, dtype=dtype)
    for position, bit in enumerate(bits):
        value |= ((word >> int(bit)) & 1).astype(dtype) << position
    return value


def _binarize(trace: np.ndarray, cut) -> np.ndarray:
    """Cut a magnitude into a line, at a number the caller gives or at one derived from the data."""
    trace = np.asarray(trace)
    if isinstance(cut, str):
        if cut not in _BINARIZE_METHODS:
            raise ValueError(f"Invalid binarize method '{cut}'. Valid methods are {list(_BINARIZE_METHODS)}.")
        if np.issubdtype(trace.dtype, np.floating) and np.isnan(trace).any():
            # A derived cut is NaN if any sample is, and `trace >= nan` is False everywhere, so the
            # signal goes constant and the conversion writes a zero-row table for a channel that fired.
            # Refuse instead: a NaN is a defect in the file (a blank cell in a Doric CSV column reads as
            # one), not something the caller chose, and it is the one input a derived cut cannot read.
            raise ValueError(
                "signal_conditioning 'binarize' cannot derive a cut from a signal containing NaN, since "
                "the cut would be NaN and every sample would fall below it, silently writing a zero-row "
                "table. Clean the signal, or give the cut as a number instead of deriving it."
            )
        # "midpoint" is invariant under windowing: unchanged by any sample lying between the two levels,
        # so a stub_test slice containing both levels derives the same cut as the full recording. It also
        # cannot miss on a line, since (min + max) / 2 falls strictly between two distinct values whatever
        # they are, which is why it is the spelling for a signal that is already one.
        #
        # Both statistics come back as Python scalars rather than through a float64 copy of the trace.
        # `.item()` is what makes that safe: an integer dtype yields a Python int, which cannot overflow,
        # where `min + max` in the native dtype would wrap (a uint8 line at 128 and 224 would cut at 48,
        # putting every sample high and finding nothing).
        cut = (trace.min().item() + trace.max().item()) / 2
    # At or above, not above, which is np.digitize's convention for a bin edge.
    #
    # int8 rather than the bare boolean: np.diff on a boolean array computes `!=`, so every transition
    # would read as rising and none as falling, silently.
    return (trace >= cut).astype("int8")


def _detect_events(
    discrete_trace: np.ndarray,
    detection: str,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Read a discrete-valued signal's transitions as events, in frame indices.

    The second of the two stages (the first is :func:`_condition_signal`). It takes **no threshold**:
    conditioning has already happened, so a rising edge is simply a transition from the lower value to
    the higher one and no cut is needed or wanted here.

    Frames rather than seconds, and offsets rather than durations, are deliberate. The caller holds the
    timestamps, so it can index them at both ends of an event and get the exact elapsed time. Returning
    a frame count instead would force the caller to multiply by an assumed sampling period, which is
    wrong for any source whose clock is not regular.

    .. warning::

        This reads a **whole signal** and does not compose over chunks. It is pure, and so are its two
        siblings, which makes them look chunk-safe; they are not. Every transition is found from
        ``np.diff``, so a chunk boundary hides the edge that spans it: the durative readings pair each
        onset with the next opposite edge, so an event still open at the end of a chunk gets a ``NaN``
        duration and its real closing edge is then read as belonging to no event in the next chunk. The
        result is a spurious truncated interval at every boundary rather than an error. Condition and
        detect over the full trace; chunk the write, not the detection.

    Parameters
    ----------
    discrete_trace : numpy.ndarray
        A discrete-valued signal, as returned by :func:`_condition_signal`.
    detection : {"rising", "falling", "high_period", "low_period", "value_change"}
        Which transitions become events. ``"rising"`` and ``"falling"`` give a point event at each edge.
        ``"high_period"`` pairs each rising edge with the next falling one, and ``"low_period"`` the
        reverse, giving a durative event. ``"value_change"`` means "a transition of this signal is an
        event of this type", pooling both directions into one event type and carrying no payload, so on
        the line conditioning always hands over it is exactly ``"rising"`` together with ``"falling"``,
        in one table rather than two. It used to be the reading a *multi-valued* signal admitted, which
        stopped being a distinct job when every cut started guaranteeing a line. To tell transitions
        apart, cut one line per distinction and give each its own spec.

    Returns
    -------
    onset_frames : numpy.ndarray
        Frame indices of the event onsets.
    offset_frames : numpy.ndarray or None
        ``None`` for a point reading. For a durative reading, the closing frame of each event, as
        ``float64`` so an event with no closing edge in the trace can carry ``NaN`` (a truncated
        interval). ``None`` for ``"rising"``, ``"falling"`` and ``"value_change"``, which are point
        readings.

    Raises
    ------
    ValueError
        If ``detection`` is not a known reading, or an edge reading meets a signal with more than two
        distinct values, which means it was never conditioned into a line.
    """
    if detection not in _DETECTION_READINGS:
        raise ValueError(f"Invalid detection '{detection}'. Valid readings are {list(_DETECTION_READINGS)}.")

    discrete_trace = np.asarray(discrete_trace)
    if np.issubdtype(discrete_trace.dtype, np.unsignedinteger):
        # Differencing an unsigned dtype wraps, so a 1 -> 0 fall comes back as 65535 rather than -1 and
        # every falling edge reads as a rising one. Silent and total: a line would report twice its real
        # events, all of them "rising", and a durative reading would give every event a NaN duration
        # because no closing edge is ever found. Promote to a signed type wide enough to hold the
        # difference before taking it. Intan hands over its digital lines as uint16.
        discrete_trace = discrete_trace.astype(np.promote_types(discrete_trace.dtype, np.int8))
    difference = np.diff(discrete_trace)

    if detection == "value_change":
        # Every transition is an event of the one type, with nothing to tell them apart. On a line that
        # is rising and falling pooled, so this is a packaging choice rather than a distinct reading.
        # Distinguishing the values is a conditioning job (cut a line per distinction), not a payload.
        return np.flatnonzero(difference) + 1, None

    rising_frames = np.flatnonzero(difference > 0) + 1
    falling_frames = np.flatnonzero(difference < 0) + 1
    if detection == "rising":
        return rising_frames, None
    if detection == "falling":
        return falling_frames, None

    onset_frames, closing_frames = (
        (rising_frames, falling_frames) if detection == "high_period" else (falling_frames, rising_frames)
    )
    # For each onset, the first close strictly after it; onsets and closes strictly alternate on a
    # two-valued signal, so this pairs each onset with its own closing edge.
    close_index = np.searchsorted(closing_frames, onset_frames, side="right")
    offset_frames = np.full(onset_frames.shape, np.nan, dtype="float64")
    matched = close_index < len(closing_frames)
    offset_frames[matched] = closing_frames[close_index[matched]]
    return onset_frames, offset_frames


def _frames_to_seconds(
    onset_frames: np.ndarray,
    offset_frames: np.ndarray | None,
    timestamps: np.ndarray,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Convert event frames to onset times and durations in seconds, by indexing the timestamps.

    The third and last shared step, and the one the interfaces used to each do slightly differently.
    Durations come from reading the clock at both ends of an event and subtracting, which is exact
    whether the sampling is regular or not. Estimating a sampling period and multiplying by a frame
    count is only correct for a regular clock and silently wrong for a source that records a timestamp
    per change, such as Inscopix.

    Parameters
    ----------
    onset_frames : numpy.ndarray
        Frame indices of the event onsets, from :func:`_detect_events`.
    offset_frames : numpy.ndarray or None
        Closing frames, or None for a point reading. ``NaN`` marks an event with no closing edge.
    timestamps : numpy.ndarray
        The signal's own clock, one entry per frame.

    Returns
    -------
    onsets : numpy.ndarray
        Onset times in seconds.
    durations : numpy.ndarray or None
        ``None`` for a point reading. Otherwise per-event durations in seconds, with ``NaN`` for an
        event whose offset is missing (a truncated interval), which is what NWB's ``DurationVectorData``
        expects.
    """
    timestamps = np.asarray(timestamps, dtype="float64")
    onsets = timestamps[onset_frames]
    if offset_frames is None:
        return onsets, None

    durations = np.full(onsets.shape, np.nan, dtype="float64")
    closed = ~np.isnan(offset_frames)
    durations[closed] = timestamps[offset_frames[closed].astype("int64")] - onsets[closed]
    return onsets, durations


def _run_length_encode_labels(
    labels: np.ndarray,
    timestamps: np.ndarray,
    frame_period: float | None = None,
) -> list[tuple[float, float, int]]:
    """
    Run-length-encode a per-frame integer label array into labeled time intervals.

    A label at frame ``k`` occupies ``[timestamps[k], timestamps[k] + frame_period)``, so a maximal
    run of identical labels over frames ``[i, j]`` becomes one interval
    ``[timestamps[i], timestamps[j] + frame_period]``. For a regular series the stop time of one
    interval equals the start time of the next, giving a gapless single-label partition.

    Parameters
    ----------
    labels : numpy.ndarray
        1D array of per-frame integer labels (e.g. behavioral motif/syllable ids, threshold states).
    timestamps : numpy.ndarray
        1D array of frame times in seconds, the same length as ``labels``.
    frame_period : float, optional
        Duration of a single frame in seconds. Defaults to the median inter-frame interval of
        ``timestamps``.

    Returns
    -------
    list of tuple of (float, float, int)
        One ``(start_time, stop_time, label)`` tuple per run, in time order.
    """
    labels = np.asarray(labels)
    timestamps = np.asarray(timestamps)
    if frame_period is None:
        frame_period = float(np.median(np.diff(timestamps)))

    boundaries = np.flatnonzero(np.diff(labels)) + 1
    run_starts = np.concatenate(([0], boundaries))
    run_ends = np.concatenate((boundaries, [labels.size]))  # exclusive frame index
    return [
        (
            float(timestamps[start_index]),
            float(timestamps[end_index - 1] + frame_period),
            int(labels[start_index]),
        )
        for start_index, end_index in zip(run_starts, run_ends)
    ]
