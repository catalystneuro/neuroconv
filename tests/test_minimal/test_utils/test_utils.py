import numpy as np
import pytest

from neuroconv.utils import calculate_regular_series_rate


def test_check_regular_series():
    assert calculate_regular_series_rate(series=[1, 2, 3])
    assert not calculate_regular_series_rate(series=[1, 2, 4])


def test_calculate_regular_series_rate_zero_diff_returns_none():
    """Regression test: UserWarning emitted and None returned when all timestamps are identical."""
    with pytest.warns(UserWarning, match="All timestamps in the series are identical"):
        result = calculate_regular_series_rate(series=[1, 1, 1, 1])
    assert result is None


def test_calculate_regular_series_rate_rejects_accumulated_drift():
    """A series whose consecutive differences are all within one microsecond still drifts from a straight line."""
    number_of_samples = 300_000
    start_sampling_rate = 30_675.0
    end_sampling_rate = 29_940.0
    start_sampling_period = 1 / start_sampling_rate
    end_sampling_period = 1 / end_sampling_rate
    differences = np.linspace(start_sampling_period, end_sampling_period, number_of_samples - 1)
    series = np.concatenate([[0.0], np.cumsum(differences)])
    assert np.unique(np.diff(series).round(decimals=6)).size == 1  # indistinguishable to a per-difference test

    assert calculate_regular_series_rate(series=series) is None


def test_calculate_regular_series_rate_uses_all_samples():
    """The rate comes from the endpoints rather than from the first difference alone."""
    number_of_samples = 100_000
    sampling_rate = 30_000.0
    start_time = 1.7e9
    series = (
        start_time + np.arange(number_of_samples) / sampling_rate
    )  # float64 on an epoch clock perturbs the first difference
    assert calculate_regular_series_rate(series=series) == pytest.approx(sampling_rate, rel=1e-7)


def test_calculate_regular_series_rate_tolerates_a_microsecond():
    """The tolerance is one microsecond of displacement, bracketed from both sides.

    A single sample in the middle of the series is displaced, so it barely tilts the line fitted through
    the endpoints and the deviation is the displacement itself.
    """
    number_of_samples = 1_000
    sampling_rate = 30_000.0
    series = np.arange(number_of_samples) / sampling_rate
    displaced_sample_index = number_of_samples // 2

    displacement_under_microsecond = 0.9e-6
    series_under_tolerance = series.copy()
    series_under_tolerance[displaced_sample_index] += displacement_under_microsecond
    assert calculate_regular_series_rate(series=series_under_tolerance) == pytest.approx(sampling_rate)

    displacement_over_microsecond = 1.1e-6
    series_over_tolerance = series.copy()
    series_over_tolerance[displaced_sample_index] += displacement_over_microsecond
    assert calculate_regular_series_rate(series=series_over_tolerance) is None
