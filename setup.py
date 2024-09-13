import platform
import sys
from collections import defaultdict
from pathlib import Path
from shutil import copy

from setuptools import setup

root = Path(__file__).parent


def read_requirements(file):
    """Read requirements from a file."""
    with open(root / file) as f:
        return f.readlines()


extras_require = defaultdict(list)
extras_require["full"] = ["dandi>=0.58.1", "hdf5plugin", "boto3"]

for modality in ["ophys", "ecephys", "icephys", "behavior", "text"]:
    modality_path = root / "src" / "neuroconv" / "datainterfaces" / modality
    modality_requirement_file = modality_path / "requirements.txt"
    if modality_requirement_file.exists():
        modality_requirements = read_requirements(modality_requirement_file)
        extras_require["full"].extend(modality_requirements)
        extras_require[modality] = modality_requirements
    else:
        modality_requirements = []

    format_subpaths = [path for path in modality_path.iterdir() if path.is_dir() and path.name != "__pycache__"]
    for format_subpath in format_subpaths:
        format_requirement_file = format_subpath / "requirements.txt"
        extras_require[format_subpath.name] = modality_requirements.copy()
        if format_requirement_file.exists():
            format_requirements = read_requirements(format_requirement_file)
            extras_require["full"].extend(format_requirements)
            extras_require[modality].extend(format_requirements)
            extras_require[format_subpath.name].extend(format_requirements)

# Create a local copy for the gin test configuration file based on the master file `base_gin_test_config.json`
gin_config_file_base = root / "base_gin_test_config.json"
gin_config_file_local = root / "tests/test_on_data/gin_test_config.json"
if not gin_config_file_local.exists():
    gin_config_file_local.parent.mkdir(parents=True, exist_ok=True)
    copy(src=gin_config_file_base, dst=gin_config_file_local)

# Bug related to sonpy on M1 Mac being installed but not running properly
if sys.platform == "darwin" and platform.processor() == "arm":
    extras_require.pop("spike2", None)
    extras_require["ecephys"] = [req for req in extras_require["ecephys"] if "sonpy" not in req]
    extras_require["full"] = [req for req in extras_require["full"] if "sonpy" not in req]

setup(
    extras_require=extras_require,
)
