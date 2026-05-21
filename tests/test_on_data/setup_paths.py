import os
import tempfile
from pathlib import Path
from shutil import copy

from neuroconv.utils import load_dict_from_file

# Output by default to a temporary directory
OUTPUT_PATH = Path(tempfile.mkdtemp())


# Load the configuration for the data tests
project_root_path = Path(__file__).parent.parent.parent

if os.getenv("CI"):
    LOCAL_PATH = Path(".")  # Must be set to "." for CI
    print("Running GIN tests on Github CI!")
else:
    # Override LOCAL_PATH in the `gin_test_config.json` file to a point on your system that contains the dataset folder
    # Use DANDIHub at hub.dandiarchive.org for open, free use of data found in the /shared/catalystneuro/ directory
    test_config_path = project_root_path / "tests" / "test_on_data" / "gin_test_config.json"
    config_file_exists = test_config_path.exists()
    if not config_file_exists:

        base_test_config_path = project_root_path / "base_gin_test_config.json"

        test_config_path.parent.mkdir(parents=True, exist_ok=True)
        copy(src=base_test_config_path, dst=test_config_path)

    test_config_dict = load_dict_from_file(test_config_path)
    LOCAL_PATH = Path(test_config_dict["LOCAL_PATH"])

    if test_config_dict["SAVE_OUTPUTS"]:
        OUTPUT_PATH = LOCAL_PATH / "neuroconv_test_outputs"
        OUTPUT_PATH.mkdir(exist_ok=True, parents=True)


BEHAVIOR_DATA_PATH = LOCAL_PATH / "behavior_testing_data"
ECEPHY_DATA_PATH = LOCAL_PATH / "ephy_testing_data"
OPHYS_DATA_PATH = LOCAL_PATH / "ophys_testing_data"

TEXT_DATA_PATH = project_root_path / "tests" / "test_modalities" / "test_text"

# Scratch directory for a locally downloaded Pinnacle sample (not committed).
PVFS_LOCAL_SCRATCH_PATH = project_root_path / "pvfs" / "example.pvfs"


def resolve_pvfs_test_file_path() -> Path | None:
    """Return the first existing PVFS sample path for ``test_on_data`` tests.

    Resolution order:

    1. ``PVFS_TEST_FILE`` environment variable (absolute or relative path set
       by the user after downloading a ``.pvfs`` file).
    2. ``<repo>/pvfs/example.pvfs`` -- local scratch copy (e.g. from Pinnacle's
       ``sleep_data.zip``); this directory is not part of the repository.
    3. ``ECEPHY_DATA_PATH/pvfs/example.pvfs`` or
       ``ECEPHY_DATA_PATH/pvfs/EEG_EMG_MOUSE_SCORED.pvfs`` (official GIN layout).

    Returns ``None`` when no candidate exists (tests should skip).
    """
    candidates: list[Path] = []
    env_path = os.getenv("PVFS_TEST_FILE")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.extend(
        [
            PVFS_LOCAL_SCRATCH_PATH,
            ECEPHY_DATA_PATH / "pvfs" / "example.pvfs",
            ECEPHY_DATA_PATH / "pvfs" / "EEG_EMG_MOUSE_SCORED.pvfs",
        ]
    )
    for path in candidates:
        if path.exists():
            return path.resolve()
    return None


PVFS_TEST_FILE_PATH = resolve_pvfs_test_file_path()

PVFS_TEST_FILE_SKIP_REASON = (
    "No PVFS sample file found. Download https://www.pinnaclet.com/data_sets/sleep_data.zip "
    "and either set PVFS_TEST_FILE to the .pvfs path, copy it to "
    f"{PVFS_LOCAL_SCRATCH_PATH}, or place it under {ECEPHY_DATA_PATH / 'pvfs'}."
)
