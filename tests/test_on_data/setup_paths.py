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

HDF5_PLUGIN_PATH = LOCAL_PATH / "hdf5_plugins"
if not HDF5_PLUGIN_PATH.exists():
    pytest.fail(f"No folder found in location: {HDF5_PLUGIN_PATH}!")

BEHAVIOR_DATA_PATH = LOCAL_PATH / "behavior_testing_data"
if not BEHAVIOR_DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {BEHAVIOR_DATA_PATH}!")

ECEPHY_DATA_PATH = LOCAL_PATH / "ephy_testing_data"
if not ECEPHY_DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {ECEPHY_DATA_PATH}!")

OPHYS_DATA_PATH = LOCAL_PATH / "ophys_testing_data"
if not OPHYS_DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {OPHYS_DATA_PATH}!")

if test_config_dict["SAVE_OUTPUTS"]:
    OUTPUT_PATH = LOCAL_PATH / "example_nwb_output"
    OUTPUT_PATH.mkdir(exist_ok=True)
else:
    OUTPUT_PATH = Path(tempfile.mkdtemp())
