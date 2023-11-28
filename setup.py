import platform
import sys
from collections import defaultdict
from pathlib import Path
from shutil import copy

from setuptools import find_packages, setup

root = Path(__file__).parent

with open(root / "README.md") as f:
    long_description = f.read()
with open(root / "requirements-minimal.txt") as f:
    install_requires = f.readlines()
with open(root / "requirements-rtd.txt") as f:
    documentation_dependencies = f.readlines()
with open(root / "requirements-testing.txt") as f:
    testing_suite_dependencies = f.readlines()

extras_require = defaultdict(list)
extras_require["dandi"].append("dandi>=0.58.1")
extras_require["full"].extend(extras_require["dandi"])

extras_require.update(test=testing_suite_dependencies, docs=documentation_dependencies)
for modality in ["ophys", "ecephys", "icephys", "behavior", "text"]:
    modality_path = root / "src" / "neuroconv" / "datainterfaces" / modality
    modality_requirement_file = modality_path / "requirements.txt"
    if modality_requirement_file.exists():
        with open(modality_requirement_file) as f:
            modality_requirements = f.readlines()
            extras_require["full"].extend(modality_requirements)
            extras_require[modality].extend(modality_requirements)
    else:
        modality_requirements = list()

    format_subpaths = [path for path in modality_path.iterdir() if path.is_dir() and path.name != "__pycache__"]
    for format_subpath in format_subpaths:
        format_requirement_file = format_subpath / "requirements.txt"
        extras_require[format_subpath.name].extend(modality_requirements)
        if format_requirement_file.exists():
            with open(format_requirement_file) as f:
                format_requirements = f.readlines()
                extras_require["full"].extend(format_requirements)
                extras_require[modality].extend(format_requirements)
                extras_require[format_subpath.name].extend(format_requirements)

# Create a local copy for the gin test configuration file based on the master file `base_gin_test_config.json`
gin_config_file_base = Path("./base_gin_test_config.json")
gin_config_file_local = Path("./tests/test_on_data/gin_test_config.json")
if not gin_config_file_local.exists():
    copy(src=gin_config_file_base, dst=gin_config_file_local)

# Bug related to sonpy on M1 Mac being installed but not running properly
if sys.platform == "darwin" and platform.processor() == "arm":
    extras_require.pop("spike2")

    extras_require["ecephys"].remove(
        next(requirement for requirement in extras_require["ecephys"] if "sonpy" in requirement)
    )
    extras_require["full"].remove(next(requirement for requirement in extras_require["full"] if "sonpy" in requirement))

setup(
    name="neuroconv",
    version="0.4.6",
    description="Convert data from proprietary formats to NWB format.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Cody Baker, Szonja Weigl, Heberto Mayorquin, Luiz Tauffer, and Ben Dichter.",
    author_email="ben.dichter@catalystneuro.com",
    url="https://github.com/catalystneuro/neuroconv",
    keywords="nwb",
    license_files=("license.txt",),
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,  # Includes files described in MANIFEST.in in the installation.
    python_requires=">=3.8",
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "neuroconv = neuroconv.tools.yaml_conversion_specification._yaml_conversion_specification:run_conversion_from_yaml_cli",
        ],
    },
    license="BSD-3-Clause",
)
