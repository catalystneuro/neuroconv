from nwb_conversion_tools.utils import calculate_regular_series_rate


def test_check_regular_series():
    assert calculate_regular_series_rate(series=[1, 2, 3])
    assert not calculate_regular_series_rate(series=[1, 2, 4])
