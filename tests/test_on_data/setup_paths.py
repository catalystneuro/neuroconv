from pathlib import Path
import tempfile
import os

import pytest

from neuroconv.utils import load_dict_from_file


# Load the configuration for the data tests
file_path = Path(__file__).parent.parent.parent / "tests" / "test_on_data" / "gin_test_config.json"
test_config_dict = load_dict_from_file(file_path)

#  GIN dataset: https://gin.g-node.org/CatalystNeuro/behavior_testing_data
if os.getenv("CI"):
    LOCAL_PATH = Path(".")  # Must be set to "." for CI
    print("Running GIN tests on Github CI!")
else:
    # Override LOCAL_PATH in the `gin_test_config.json` file to a point on your system that contains the dataset folder
    # Use DANDIHub at hub.dandiarchive.org for open, free use of data found in the /shared/catalystneuro/ directory
    LOCAL_PATH = Path(test_config_dict["LOCAL_PATH"])
    print("Running GIN tests locally!")

BEHAVIOR_DATA_PATH = LOCAL_PATH / "behavior_testing_data"
ECEPHY_DATA_PATH = LOCAL_PATH / "ephy_testing_data"
OPHYS_DATA_PATH = LOCAL_PATH / "ophys_testing_data"

TEXT_DATA_PATH = file_path = Path(__file__).parent.parent.parent / "tests" / "test_text"


if test_config_dict["SAVE_OUTPUTS"]:
    OUTPUT_PATH = LOCAL_PATH / "example_nwb_output"
    OUTPUT_PATH.mkdir(exist_ok=True)
else:
    OUTPUT_PATH = Path(tempfile.mkdtemp())
