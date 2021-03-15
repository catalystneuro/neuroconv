from nwb_conversion_tools.conversion_tools import check_regular_timestamps


def test_check_regular_timestamps():
    assert check_regular_timestamps([1,2,3])
    assert not check_regular_timestamps([1,2,4])