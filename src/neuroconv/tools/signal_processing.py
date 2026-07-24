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


def discretize_trace(
    trace: np.ndarray,
    detect: str,
    threshold: float | None = None,
) -> tuple[np.ndarray, np.ndarray | None]:
    """
    Discretize a trace into event onset frames and, for a durative reading, per-event durations.

    This is the format-agnostic edge-detection step shared by signal-encoded events sources (e.g.
    digital TTL (transistor-transistor logic) lines from Intan, SpikeGLX NIDQ, an analog photodiode):
    the trace is thresholded into a binary line, and the same rising/falling structure can then be read
    as point events or as durative high/low periods, and only the caller knows which the experiment
    intends.

    Parameters
    ----------
    trace : numpy.ndarray
        A one-dimensional signal. A strictly 0/1 digital line, or any trace thresholded into one.
    detect : {"rising", "falling", "high_period", "low_period"}
        What to detect. ``"rising"``/``"falling"`` return the up/down transition frames as point
        events. ``"high_period"`` pairs each rising edge with the next falling edge (onset + high span);
        ``"low_period"`` pairs each falling edge with the next rising edge (onset + low span).
    threshold : float, optional
        The on/off threshold passed through to :func:`get_rising_frames_from_ttl` /
        :func:`get_falling_frames_from_ttl`. The mean of the trace is used by default; pass ``0.5`` for
        a strictly 0/1 digital line.

    Returns
    -------
    onset_frames : numpy.ndarray
        The frame indices of the event onsets.
    durations : numpy.ndarray or None
        ``None`` for a point reading (``"rising"``/``"falling"``). For a durative reading, per-event
        durations **in frames** (the caller converts to seconds with the sampling period). An onset with
        no closing edge in the trace gets a ``NaN`` duration (a truncated interval).
    """
    valid = ("rising", "falling", "high_period", "low_period")
    if detect not in valid:
        raise ValueError(f"Invalid detect '{detect}'. Valid values are {list(valid)}.")

    rising = get_rising_frames_from_ttl(trace, threshold=threshold)
    falling = get_falling_frames_from_ttl(trace, threshold=threshold)
    if detect == "rising":
        return rising, None
    if detect == "falling":
        return falling, None

    onsets, closes = (rising, falling) if detect == "high_period" else (falling, rising)
    # For each onset, the first close strictly after it; onsets and closes strictly alternate on a
    # binary line, so this pairs each onset to its own closing edge.
    close_index = np.searchsorted(closes, onsets, side="right")
    durations = np.full(onsets.shape, np.nan, dtype="float64")
    matched = close_index < len(closes)
    durations[matched] = closes[close_index[matched]] - onsets[matched]  # in frames
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
