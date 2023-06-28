from typing import Optional, Real, Sequence

import numpy as np


def is_series_regular(series: Sequence[float]) -> bool:
    """
    Determine if a series has a regular sampling rate.

    A series is considered to have a regular sampling rate if the difference
    between the first two elements (the first difference) is the same as the
    difference between the first element and the last one, as estimated using
    the number of samples and the first difference. That is, if the difference
    in values is constant and you can multiply the first difference
    by the number of samples to get the last value.

    Parameters
    ----------
    series : Sequence[float]
        An ordered iterable (e.g., list, tuple, Pandas Series, or NumPy array)
        of numerical values representing the series to check for regularity.
        The series is assumed to be sorted in increasing order.

    Returns
    -------
    bool
        True if the series is regularly sampled, False otherwise.

    Examples
    --------
    >>> is_series_regular([0, 2, 4, 6, 8])
    True
    >>> is_series_regular([0, 2, 4, 7, 8])
    False
    """
    fist_difference = series[1] - series[0]
    num_samples = len(series)
    last_value = series[-1]

    estimated_last_value = series[0] + (num_samples - 1) * fist_difference
    is_regular = last_value == estimated_last_value
    return is_regular


def calculate_regular_series_rate(series: np.ndarray, tolerance_decimals: int = 6) -> Optional[Real]:
    """Calculates the rate of a series as the difference between all consecutive points.
    If the difference between all time points are all the same value, then the value of
    rate is a scalar otherwise it is None."""

    diff_ts = np.diff(series)
    rounded_diff_ts = diff_ts.round(decimals=tolerance_decimals)
    uniq_diff_ts = np.unique(rounded_diff_ts)
    rate = 1.0 / diff_ts[0] if len(uniq_diff_ts) == 1 else None
    return rate
