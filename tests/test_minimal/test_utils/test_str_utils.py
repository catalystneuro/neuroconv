import pytest

from neuroconv.utils.str_utils import human_readable_size

def test_small_bytes():
    """Test sizes smaller than 1 KB"""
    assert human_readable_size(0) == '0.00 B'
    assert human_readable_size(1) == '1.00 B'
    assert human_readable_size(512) == '512.00 B'
    assert human_readable_size(1023) == '1023.00 B'

def test_kilobytes():
    """Test sizes from 1 KB to less than 1 MB"""
    assert human_readable_size(1024) == '1.00 KB'
    assert human_readable_size(1025) == '1.00 KB'
    assert human_readable_size(10 * 1024) == '10.00 KB'
    assert human_readable_size(1024 * 1024 - 1) == '1024.00 KB'

def test_megabytes():
    """Test sizes from 1 MB to less than 1 GB"""
    assert human_readable_size(1024 * 1024) == '1.00 MB'
    assert human_readable_size(5 * 1024 * 1024) == '5.00 MB'
    assert human_readable_size(1024 * 1024 * 1024 - 1) == '1024.00 MB'

def test_gigabytes():
    """Test sizes from 1 GB to less than 1 TB"""
    assert human_readable_size(1024 ** 3) == '1.00 GB'
    assert human_readable_size(10 * 1024 ** 3) == '10.00 GB'
    assert human_readable_size(1024 ** 4 - 1) == '1024.00 GB'

def test_negative_size():
    """Test that negative sizes raise ValueError"""
    with pytest.raises(ValueError):
        human_readable_size(-1)

def test_very_large_numbers():
    """Test sizes in the terabyte range and beyond"""
    assert human_readable_size(1024 ** 4) == '1.00 TB'
    assert human_readable_size(1024 ** 5) == '1.00 PB'
    assert human_readable_size(1024 ** 6 * 3) == '3.00 EB'
