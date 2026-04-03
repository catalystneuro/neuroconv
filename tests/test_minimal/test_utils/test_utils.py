import warnings

from neuroconv.utils import calculate_regular_series_rate


def test_check_regular_series():
    assert calculate_regular_series_rate(series=[1, 2, 3])
    assert not calculate_regular_series_rate(series=[1, 2, 4])


def test_calculate_regular_series_rate_zero_diff_returns_none():
    """Regression test: no RuntimeWarning when first two timestamps are identical (diff is zero)."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = calculate_regular_series_rate(series=[1, 1, 1, 1])
    assert result is None
