import warnings

import numpy as np
from numpy.typing import ArrayLike, NDArray


def calculate_regular_series_rate(series: ArrayLike | NDArray, tolerance_in_seconds: float = 1e-6) -> float | None:
    """Calculate the rate of a series if a rate can stand in for it.

    The series is regular if replacing it with ``series[0] + index / rate`` displaces no sample by more than the
    tolerance, which is the stricter of ``tolerance_in_seconds`` and a tenth of the sampling period. The second
    term only binds above 100 kHz, where a microsecond exceeds half a sampling period and a dropped sample would
    otherwise go undetected.

    Returns the rate, or ``None`` if the series is not regular.
    """
    series = np.asarray(series, dtype="float64")

    number_of_samples = series.size
    if number_of_samples < 2:
        return None

    first = series[0]
    last = series[-1]
    duration = last - first

    if duration == 0 and series.min() == first and series.max() == first:
        warnings.warn(
            "All timestamps in the series are identical. This likely indicates a problem with the data source.",
            UserWarning,
            stacklevel=2,
        )
        return None
    if not duration > 0:  # zero duration, decreasing series, or a non-finite endpoint
        return None

    sampling_period = duration / (number_of_samples - 1)
    tolerance_in_samples = 0.1
    tolerance = min(tolerance_in_samples * sampling_period, tolerance_in_seconds)

    ideal_series = first + np.arange(number_of_samples) * sampling_period
    max_deviation = np.abs(ideal_series - series).max()
    if not max_deviation <= tolerance:  # negated so a NaN anywhere in the series rejects
        return None

    return 1.0 / sampling_period
