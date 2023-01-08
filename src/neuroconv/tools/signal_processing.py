"""Author: Cody Baker."""
from typing import Tuple, Optional

import numpy as np


def _get_default_bins(trace: np.ndarray) -> np.ndarray:
    trace_max = float(np.max(trace))  # cast to Python floats during calculation to avoid overflows
    trace_min = float(np.min(trace))
    midpoint = (trace_max - trace_min) / 2

    eps = 1 if np.issubdtype(trace.dtype, np.integer) else np.finfo(float).eps * 10
    bins = np.array([trace_min - eps, midpoint, trace_max + eps])  # +/- buffer on the boundaries to remove edge effects
    return bins


def get_rising_frames_from_ttl(trace: np.ndarray, bins: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return the frame indices for rising events in a TTL pulse.

    Parameters
    ----------
    trace: numpy.ndarray
        A TTL pulse.
    bins: numpy.ndarray, optional
        The edges of bins to use for digitization.
        The default is two bins set to [min(trace), midpoint(trace), max(trace)].

    Returns
    -------
    rising_frames: numpy.ndarray
        The frame indices of rising events.
    """
    bins = bins or _get_default_bins(trace=trace)

    binned_states = np.digitize(x=trace, bins=bins).astype("int8")
    diff_binned_states = np.diff(binned_states, axis=0)

    rising_frames = np.where(diff_binned_states > 0)[0]

    return rising_frames


def get_falling_frames_from_ttl(trace: np.ndarray, bins: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return the frame indices for falling events in a TTL pulse.

    Parameters
    ----------
    trace: numpy.ndarray
        A TTL pulse.
    bins: numpy.ndarray, optional
        The edges of bins to use for digitization.
        The default is two bins set to [min(trace), midpoint(trace), max(trace)].

    Returns
    -------
    falling_frames: numpy.ndarray
        The frame indices of falling events.
    """
    bins = bins or _get_default_bins(trace=trace)

    binned_states = np.digitize(x=trace, bins=bins).astype("int8")
    diff_binned_states = np.diff(binned_states, axis=0)

    falling_frames = np.where(diff_binned_states < 0)[0]

    return falling_frames
