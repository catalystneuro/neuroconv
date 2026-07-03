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
