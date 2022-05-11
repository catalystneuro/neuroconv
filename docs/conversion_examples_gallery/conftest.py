from pathlib import Path
import pytest

from tests.test_on_data.setup_paths import ECEPHY_DATA_PATH, BEHAVIOR_DATA_PATH, OPHYS_DATA_PATH


@pytest.fixture(autouse=True)
def add_data_space(doctest_namespace, tmp_path):
    doctest_namespace["ECEPHY_DATA_PATH"] = ECEPHY_DATA_PATH
    doctest_namespace["BEHAVIOR_DATA_PATH"] = BEHAVIOR_DATA_PATH
    doctest_namespace["OPHYS_DATA_PATH"] = OPHYS_DATA_PATH
    doctest_namespace["path_to_save_nwbfile"] = Path(tmp_path) / "file.nwb"
