import platform
from pathlib import Path

import pytest
from packaging import version

from tests.test_on_data.setup_paths import (
    BEHAVIOR_DATA_PATH,
    ECEPHY_DATA_PATH,
    OPHYS_DATA_PATH,
    TEXT_DATA_PATH,
)


@pytest.fixture(autouse=True)
def add_data_space(doctest_namespace, tmp_path):
    doctest_namespace["ECEPHY_DATA_PATH"] = ECEPHY_DATA_PATH
    doctest_namespace["BEHAVIOR_DATA_PATH"] = BEHAVIOR_DATA_PATH
    doctest_namespace["OPHYS_DATA_PATH"] = OPHYS_DATA_PATH
    doctest_namespace["TEXT_DATA_PATH"] = TEXT_DATA_PATH

    doctest_namespace["path_to_save_nwbfile"] = Path(tmp_path) / "doctest_file.nwb"
    doctest_namespace["output_folder"] = Path(tmp_path)



python_version = platform.python_version()
os = platform.system()
# Hook to conditionally skip doctests in deeplabcut.rst for Python 3.9 on macOS (Darwin)
def pytest_runtest_setup(item):
    if isinstance(item, pytest.DoctestItem):
        # Check if we are running the doctest from deeplabcut.rst
        test_file = Path(item.fspath)
        if test_file.name == "deeplabcut.rst":
            # Check if Python version is 3.9 and platform is Darwin (macOS)
            if version.parse(python_version) < version.parse("3.10") and os == "Darwin":
                pytest.skip("Skipping doctests for deeplabcut.rst on Python 3.9 and macOS")
