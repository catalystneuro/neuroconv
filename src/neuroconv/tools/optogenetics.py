import numpy as np


def create_optogenetic_stimulation_timeseries(
    *,
    stimulation_onset_times: np.ndarray,
    duration: float,
    frequency: float,
    pulse_width: float,
    power: float,
) -> tuple[np.ndarray, np.ndarray]:
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
