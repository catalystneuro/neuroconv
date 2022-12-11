"""Author: Cody Baker and Ben Dichter."""
from typing import Tuple

import numpy as np


def parse_rising_and_falling_frames_from_ttl(trace: np.ndarray, num_bins: int = 2) -> Tuple[np.ndarray, np.ndarray]:
    """
    Parse the frame indices for rising and falling events in a TTL pulse.

    Parameters
    ----------
    trace: numpy.ndarray
        A TTL pulse.
    num_bins: int
        When digitizing the signal to clean up signal noise, specify the level of refinement in terms of the number
        of bins incurred from a linear interval partition from the minimum to the maximum trace values.
        The default is 2, signifying a clear on/off signal from a baseline value to a target value.

    Returns
    -------
    rising_frames: numpy.ndarray
        The frame indices of rising events.
    falling_frames: numpy.ndarray
        The frame indices of falling events.
    """
    eps = 1 if np.issubdtype(trace.dtype, np.integer) else np.finfo(float).eps
    binned_states = np.digitize(
        x=trace,
        bins=np.linspace(
            start=np.min(trace) - eps,  # Must go slightly beyond min/max to prevent binning occurences at the boundary
            stop=np.max(trace) + eps,
            num=num_bins + 1,  # 'num' in np.linspace is actually the number of partitions; +1 to translate to # bins
        ),
    ).astype("int8")

    diff_binned_states = np.diff(binned_states, axis=0)

    rising_frames = np.where(diff_binned_states > 0)[0]
    falling_frames = np.where(diff_binned_states < 0)[0]

    return rising_frames, falling_frames


def syncrhonize_timestamps_from_pulses(pulse_sent_times, pulse_received_times, unsynched_timestamps):
    """

    Parameters
    ----------
    pulse_sent_times: array-like
        Times that pulses were sent from secondary acquisition system
    pulse_received_times: array-like
        Times that pulses were received by primary acquisition system
    unsynched_timestamps: array-like
        Timestamps from the secondary acquisition system that need to be synchronized with the primary system

    Returns
    -------
    array-like

    """
    assert len(pulse_sent_times) == len(pulse_received_times), "child and parent have different number of pulses."

    child_idxs = np.searchsorted(unsynched_timestamps, pulse_sent_times)
    interval_ratios = np.diff(pulse_received_times) / np.diff(pulse_sent_times)

    synched_timestamps = np.array([])
    for i in np.arange(len(pulse_sent_times)-1):
        interval_timestamps = (unsynched_timestamps[child_idxs[i]:child_idxs[i+1]] - pulse_sent_times[i]) * \
                              interval_ratios[i] + pulse_received_times[i]
        synched_timestamps = np.hstack((synched_timestamps, interval_timestamps))

    return synched_timestamps

