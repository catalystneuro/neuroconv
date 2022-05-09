from nwb_conversion_tools.utils import check_regular_series


def test_check_regular_series():
    assert check_regular_series(series=[1, 2, 3])
    assert not check_regular_series(series=[1, 2, 4])
