"""Author: Cody Baker."""
from typing import Tuple

import numpy as np

from ..utils import ArrayType


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


def synchronize_timestamps_between_systems(
    unsynchronized_timestamps: ArrayType,
    primary_reference_timestamps: ArrayType,
    secondary_reference_timestamps: ArrayType,
) -> np.ndarray:
    """
    One method of synchronization used to align timing information across sytems.

    Involves taking timestamps recorded in a secondary system and inferring their corresponding times in a primary
    system given a pair of reference timestamps between the two systems.

    Parameters
    ----------
    unsynchronized_timestamps : ArrayType
        The timestamps that need to be synchronized into the primary time basis.
    primary_reference_timestamps : ArrayType
        A known set of timestamps in the primary system to be used as reference.
    secondary_reference_timestamps : ArrayType
        A known set of timestamps in the secondary system to be used as reference.

    Returns
    -------
    synchronized_timestamps: numpy.ndarray
        The interpolation of the unsynchronized_timestamps into the primary reference times.
    """
    return np.interp(x=unsynchronized_timestamps, xp=secondary_reference_timestamps, fp=primary_reference_timestamps)
