from numbers import Real
from typing import Optional

import numpy as np


def calculate_regular_series_rate(series: np.ndarray, tolerance_decimals: int = 6) -> Optional[Real]:
    """Calculates the rate of a series as the difference between all consecutive points.
    If the difference between all time points are all the same value, then the value of
    rate is a scalar otherwise it is None."""
    diff_ts = np.diff(series)
    rounded_diff_ts = diff_ts.round(decimals=tolerance_decimals)
    uniq_diff_ts = np.unique(rounded_diff_ts)
    rate = 1.0 / diff_ts[0] if len(uniq_diff_ts) == 1 else None
    return rate
