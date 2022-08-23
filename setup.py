import os
from glob import glob

from setuptools import setup, find_packages
from pathlib import Path
from shutil import copy
from collections import defaultdict

root = Path(__file__).parent

with open(root / "README.md") as f:
    long_description = f.read()
with open(root / "requirements-minimal.txt") as f:
    install_requires = f.readlines()
with open(root / "requirements-rtd.txt") as f:
    documentation_dependencies = f.readlines()
with open(root / "requirements-testing.txt") as f:
    testing_suite_dependencies = f.readlines()

full_dependencies = set(install_requires)
with open(root / "requirements-full.txt") as f:
    full_dependencies.update(f.readlines())

extras_require = defaultdict(list)
modality_to_glob = dict()
for modality in ["ophys", "ecephys", "icephys", "behavior"]:
    modality_path = root / "src" / "neuroconv" / "datainterfaces" / modality

    for source_type_path in glob(os.path.join(modality_path, "*", "")):
        if "__pycache__" in source_type_path:
            continue
        source_type_requirements_path = Path(source_type_path) / "requirements.txt"
        if os.path.exists(source_type_requirements_path):
            with open(source_type_requirements_path) as f:
                source_type_requirements = f.read().splitlines()
        else:
            source_type_requirements = []
        full_dependencies.update(source_type_requirements)
        extras_require[modality].extend(source_type_requirements)
        extras_require[Path(source_type_path).name].extend(source_type_requirements)

extras_require.update(full=list(full_dependencies), test=testing_suite_dependencies, docs=documentation_dependencies)

# Create a local copy for the gin test configuration file based on the master file `base_gin_test_config.json`
gin_config_file_base = Path("./base_gin_test_config.json")
gin_config_file_local = Path("./tests/test_on_data/gin_test_config.json")
if not gin_config_file_local.exists():
    copy(src=gin_config_file_base, dst=gin_config_file_local)

setup(
    name="neuroconv",
    version="0.1.1",
    description="Convert data from proprietary formats to NWB format.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Cody Baker, Szonja Weigl, Heberto Mayorquin, Luiz Tauffer, and Ben Dichter.",
    author_email="ben.dichter@catalystneuro.com",
    url="https://github.com/catalystneuro/neuroconv",
    keywords="nwb",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,  # Includes files described in MANIFEST.in in the installation.
    python_requires=">=3.7",
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "neuroconv = neuroconv.tools.yaml_conversion_specification.yaml_conversion_specification:run_conversion_from_yaml_cli",
        ],
    },
)
