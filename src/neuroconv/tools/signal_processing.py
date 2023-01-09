"""Author: Cody Baker."""
from typing import Optional

import numpy as np


def get_rising_frames_from_ttl(trace: np.ndarray, threshold: Optional[float] = None) -> np.ndarray:
    """
    Return the frame indices for rising events in a TTL pulse.

    Parameters
    ----------
    trace: numpy.ndarray
        A TTL pulse.
    threshold: float, optional
        The threshold used to distinguish on/off states in the trace.
        The mean of the trace is used by default.

    Returns
    -------
    rising_frames: numpy.ndarray
        The frame indices of rising events.
    """
    threshold = threshold or np.mean(trace)

    sign = np.sign(trace - threshold)
    diff = np.diff(sign)
    rising_frames = np.where(diff > 0)[0] + 1

    return rising_frames


def get_falling_frames_from_ttl(trace: np.ndarray, threshold: Optional[float] = None) -> np.ndarray:
    """
    Return the frame indices for falling events in a TTL pulse.

    Parameters
    ----------
    trace: numpy.ndarray
        A TTL pulse.
    threshold: float, optional
        The threshold used to distinguish on/off states in the trace.
        The mean of the trace is used by default.

    Returns
    -------
    falling_frames: numpy.ndarray
        The frame indices of falling events.
    """
    threshold = threshold or np.mean(trace)

    sign = np.sign(trace - threshold)
    diff = np.diff(sign)
    falling_frames = np.where(diff < 0)[0] + 1

    return falling_frames
