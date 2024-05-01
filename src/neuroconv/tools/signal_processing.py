from typing import Optional, Tuple

import numpy as np


def get_rising_frames_from_ttl(trace: np.ndarray, threshold: Optional[float] = None) -> np.ndarray:
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


def get_falling_frames_from_ttl(trace: np.ndarray, threshold: Optional[float] = None) -> np.ndarray:
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


def create_ogen_stimulation_timeseries(
    *,
    stimulation_onset_times: np.ndarray,
    duration: float,
    frequency: float,
    pulse_width: float,
    power: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Create a continuous stimulation time series from stimulation onset times and parameters.

    In the resulting data array, the offset time of each pulse is represented by a 0 power value.

    Parameters
    ----------
    stimulation_onset_times : np.ndarray
        Array of stimulation onset times.
    duration : float
        Duration of stimulation in seconds.
    frequency : float
        Frequency of stimulation in Hz.
    pulse_width : float
        Pulse width of stimulation in seconds.
    power : float
        Power of stimulation in W.

    Returns
    -------
    np.ndarray
        Stimulation timestamps.
    np.ndarray
        Instantaneous stimulation power.

    Notes
    -----
    For continuous (non-pulsed) stimulation of a desired duration, simply set
    ```
    pulse_width = duration
    frequency = 1 / duration
    ```
    """
    num_pulses = int(duration * frequency)
    inter_pulse_interval = 1 / frequency
    timestamps, data = [0], [0]
    for onset_time in stimulation_onset_times:
        for i in range(num_pulses):
            pulse_onset_time = onset_time + i * inter_pulse_interval
            timestamps.append(pulse_onset_time)
            data.append(power)
            pulse_offset_time = pulse_onset_time + pulse_width
            timestamps.append(pulse_offset_time)
            data.append(0)
    return np.array(timestamps, dtype=np.float64), np.array(data, dtype=np.float64)
