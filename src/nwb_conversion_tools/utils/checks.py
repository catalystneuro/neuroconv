import numpy as np


def check_regular_series(series: np.ndarray, tolerance_decimals: int = 9):
    """General purpose function for checking if the difference between all consecutive points in a series are equal."""
    uniq_diff_ts = np.unique(np.diff(series).round(decimals=tolerance_decimals))
    return len(uniq_diff_ts) == 1


def check_actual_rate_for_regular_series(series: np.ndarray, rate: float):
    """Checks if there is a mismatch between the internally recorded rate
    and the actual difference in a series assumed that the series is regular."""
    actual_rate = series[1] - series[0]
    return actual_rate == rate
