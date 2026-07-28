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


_DETECTION_READINGS = ("rising", "falling", "high_period", "low_period")
_BINARIZE_METHODS = ("midpoint", "mean")


def _condition_signal(trace: np.ndarray, signal_conditioning: dict | None = None) -> np.ndarray:
    """Condition a sampled signal into a discrete-valued one of the same length, on the same timeline.

    The first of the two stages a signal-encoded events source runs (the second is
    :func:`_detect_events`). The boundary between them is where the data type changes: conditioning is
    signal-to-signal, detection is signal-to-events.

    **The postcondition is the contract:** whatever comes back is discrete-valued, the same length as
    the input, and indexed on the same timeline. Length preservation is what lets :func:`_detect_events`
    return frame indices that still address the caller's original timestamps, so a step that resampled
    or dropped samples would silently break the conversion downstream and does not belong here.

    Parameters
    ----------
    trace : numpy.ndarray
        A one-dimensional sampled signal.
    signal_conditioning : dict, optional
        How to reach a discrete-valued signal. ``{"binarize": "midpoint"}`` (or ``"mean"``) cuts a
        two-level but numerically noisy trace at a value computed from the data itself.

        If None (default), the trace is returned unchanged, which asserts it is already discrete-valued.
        That is the ordinary case for a recorded digital line.

    Returns
    -------
    numpy.ndarray
        The conditioned signal, same length as ``trace``.

    Raises
    ------
    ValueError
        If the conditioning names no cut, or a cut's parameters are unusable.
    """
    if not signal_conditioning:
        # Omission asserts the signal is already discrete-valued. Whether that assertion holds is
        # checked by the backstop in _detect_events at read time.
        return np.asarray(trace)

    if "binarize" not in signal_conditioning:
        # Reachable only by calling this directly, since an interface's validator rejects an unrecognized
        # conditioning key first. Routes that are designed but unbuilt ('bits' for a packed word,
        # 'thresholds' for an analog trace, 'hysteresis', 'debounce') land here, so the message says the
        # key is not implemented rather than letting a bare KeyError out.
        raise ValueError(
            f"signal_conditioning {sorted(signal_conditioning)} sets no cut. 'binarize' is required; "
            "pass None to leave a signal that is already discrete-valued unconditioned. Any other "
            "setting is not implemented."
        )

    return _binarize(trace=np.asarray(trace), method=signal_conditioning["binarize"])


def _binarize(trace: np.ndarray, method: str) -> np.ndarray:
    """Cut a two-level but numerically noisy trace at a value derived from the data itself."""
    if method not in _BINARIZE_METHODS:
        raise ValueError(f"Invalid binarize method '{method}'. Valid methods are {list(_BINARIZE_METHODS)}.")
    trace = np.asarray(trace, dtype="float64")
    # "midpoint" is the default elsewhere because it is invariant under windowing: it is unchanged by any
    # sample lying between the two levels, so a stub_test slice containing both levels derives the same
    # cut as the full recording. The mean moves with both duty cycle and window, which would make a stub
    # and a full conversion emit different events; it stays available for a trace with an extreme outlier.
    cut = (trace.min() + trace.max()) / 2 if method == "midpoint" else trace.mean()
    return (trace > cut).astype("int64")


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
    detection : {"rising", "falling", "high_period", "low_period"}
        Which transitions become events. ``"rising"`` and ``"falling"`` give a point event at each edge.
        ``"high_period"`` pairs each rising edge with the next falling one, and ``"low_period"`` the
        reverse, giving a durative event.

    Returns
    -------
    onset_frames : numpy.ndarray
        Frame indices of the event onsets.
    offset_frames : numpy.ndarray or None
        ``None`` for a point reading. For a durative reading, the closing frame of each event, as
        ``float64`` so an event with no closing edge in the trace can carry ``NaN`` (a truncated
        interval).

    Raises
    ------
    ValueError
        If ``detection`` is not a known reading, or an edge reading meets a signal with more than two
        distinct values, which means it was never conditioned into a line.
    """
    if detection not in _DETECTION_READINGS:
        raise ValueError(f"Invalid detection '{detection}'. Valid readings are {list(_DETECTION_READINGS)}.")

    discrete_trace = np.asarray(discrete_trace)
    difference = np.diff(discrete_trace)

    # The read-time backstop. Every reading here is only meaningful on a two-valued signal: with
    # three or more levels there is no fact about which of them count as high. "At most two", not
    # exactly two, because a line that never toggles has one value and must still convert (to a
    # zero-row table) rather than fail.
    distinct_values = np.unique(discrete_trace)
    if distinct_values.size > 2:
        raise ValueError(
            f"detection '{detection}' needs a two-valued signal, but this one has {distinct_values.size} "
            "distinct values. Condition it into a line first, with 'binarize' for a numerically noisy "
            "one."
        )

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
