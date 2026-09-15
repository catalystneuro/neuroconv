import pytest

from neuroconv.utils.str_utils import human_readable_size, to_snake_case


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Miniscope", "miniscope"),  # already one word
        ("HPC_miniscope1", "hpc_miniscope1"),  # an acronym the device name carries
        ("Miniscope_V4_BNO", "miniscope_v4_bno"),  # a hardware design name
        ("MyDeviceName", "my_device_name"),  # written without separators
        ("my-device name", "my_device_name"),  # hyphen and space are separators
    ],
)
def test_to_snake_case(name, expected):
    assert to_snake_case(name) == expected


def test_small_bytes():
    """Test sizes smaller than 1 KB"""
    assert human_readable_size(0) == "0 B"
    assert human_readable_size(1) == "1 B"
    assert human_readable_size(512) == "512 B"
    assert human_readable_size(1023) == "1.02 KB"


def test_kilobytes():
    """Test sizes from 1 KB to less than 1 MB"""
    assert human_readable_size(1024, binary=True) == "1.00 KiB"
    assert human_readable_size(1025, binary=True) == "1.00 KiB"
    assert human_readable_size(10 * 1024, binary=True) == "10.00 KiB"
    assert human_readable_size(1024 * 1024 - 1, binary=True) == "1024.00 KiB"


def test_megabytes():
    """Test sizes from 1 MB to less than 1 GB"""
    assert human_readable_size(1024 * 1024, binary=True) == "1.00 MiB"
    assert human_readable_size(5 * 1024 * 1024, binary=True) == "5.00 MiB"
    assert human_readable_size(1024 * 1024 * 1024 - 1, binary=True) == "1024.00 MiB"


def test_gigabytes():
    """Test sizes from 1 GB to less than 1 TB"""
    assert human_readable_size(1024**3, binary=True) == "1.00 GiB"
    assert human_readable_size(10 * 1024**3, binary=True) == "10.00 GiB"
    assert human_readable_size(1024**4 - 1, binary=True) == "1024.00 GiB"


def test_negative_size():
    """Test that negative sizes raise ValueError"""
    with pytest.raises(ValueError):
        human_readable_size(-1)


def test_very_large_numbers():
    """Test sizes in the terabyte range and beyond"""
    assert human_readable_size(1024**4, binary=True) == "1.00 TiB"
    assert human_readable_size(1024**5, binary=True) == "1.00 PiB"
    assert human_readable_size(1024**6 * 3, binary=True) == "3.00 EiB"
