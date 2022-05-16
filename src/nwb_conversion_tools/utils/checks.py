import numpy as np


def check_regular_series(series: np.ndarray, tolerance_decimals: int = 9):
    """General purpose function for checking if the difference between all consecutive points in a series are equal.
    If it is, returns the assessed sampling rate."""
    diff_ts = np.diff(series).round(decimals=tolerance_decimals)
    uniq_diff_ts = np.unique(diff_ts)
    rate = diff_ts[0] if len(uniq_diff_ts) == 1 else None
    return len(uniq_diff_ts) == 1, rate
