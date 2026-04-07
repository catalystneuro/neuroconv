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
