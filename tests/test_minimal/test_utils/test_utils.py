from neuroconv.utils import calculate_regular_series_rate, is_series_regular


def test_check_regular_series():
    assert calculate_regular_series_rate(series=[1, 2, 3])
    assert not calculate_regular_series_rate(series=[1, 2, 4])


def is_series_regular():
    assert is_series_regular(series=[1, 2, 3])
    assert not is_series_regular(series=[1, 2, 4])
