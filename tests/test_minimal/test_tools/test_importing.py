"""Tests for neuroconv.tools.importing module."""

import pytest

from neuroconv import get_format_summaries
from neuroconv.tools.importing import get_package


def test_guide_attributes():
    """The GUIDE fetches this information from each class to render the selection of interfaces."""
    summaries = get_format_summaries()

    # Blocking assertion when adding new interfaces
    for name, summary in summaries.items():
        for key, value in summary.items():
            assert value is not None, f"{name} is missing GUIDE related attribute {key}."
            if key == "keywords":
                assert isinstance(
                    value, tuple
                ), f"{name} incorrectly specified GUIDE-related attribute 'keywords' (must be tuple)."
            elif key == "display_name":
                assert isinstance(
                    value, str
                ), f"{name} incorrectly specified GUIDE-related attribute 'display_name' (must be str)."
            elif key == "info":
                assert isinstance(
                    value, str
                ), f"{name} incorrectly specified GUIDE-related attribute 'info' (must be str)."
            elif key == "associated_suffixes":
                assert isinstance(
                    value, tuple
                ), f"{name} incorrectly specified GUIDE-related attribute 'associated_suffixes' (must be tuple)."
            if isinstance(value, tuple):
                assert len(value) > 0, f"{name} is missing entries in GUIDE related attribute {key}."


def test_get_package_missing():
    package_name = "nonexistent_package_abc123"
    with pytest.raises(ModuleNotFoundError) as excinfo:
        get_package(package_name)
    assert package_name in str(excinfo.value)


def test_get_package_existing():
    module = get_package("json")
    assert module.__name__ == "json"
