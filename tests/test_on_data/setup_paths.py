import os
import tempfile
from pathlib import Path

from neuroconv.utils import load_dict_from_file

# Output by default to a temporary directory
OUTPUT_PATH = Path(tempfile.mkdtemp())


# Load the configuration for the data tests


if os.getenv("CI"):
    LOCAL_PATH = Path(".")  # Must be set to "." for CI
    print("Running GIN tests on Github CI!")
else:
    # Override LOCAL_PATH in the `gin_test_config.json` file to a point on your system that contains the dataset folder
    # Use DANDIHub at hub.dandiarchive.org for open, free use of data found in the /shared/catalystneuro/ directory
    file_path = Path(__file__).parent / "gin_test_config.json"
    assert file_path.exists(), f"File not found: {file_path}"
    test_config_dict = load_dict_from_file(file_path)
    LOCAL_PATH = Path(test_config_dict["LOCAL_PATH"])

    if test_config_dict["SAVE_OUTPUTS"]:
        OUTPUT_PATH = LOCAL_PATH / "neuroconv_test_outputs"
        OUTPUT_PATH.mkdir(exist_ok=True, parents=True)


BEHAVIOR_DATA_PATH = LOCAL_PATH / "behavior_testing_data"
ECEPHY_DATA_PATH = LOCAL_PATH / "ephy_testing_data"
OPHYS_DATA_PATH = LOCAL_PATH / "ophys_testing_data"

TEXT_DATA_PATH = Path(__file__).parent.parent.parent / "tests" / "test_text"
