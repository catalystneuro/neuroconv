"""Author: Cody Baker."""
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
