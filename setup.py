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

extras_require = defaultdict(list)
extras_require.update(test=testing_suite_dependencies, docs=documentation_dependencies)
for modality in ["ophys", "ecephys", "icephys", "behavior"]:
    modality_path = root / "src" / "neuroconv" / "datainterfaces" / modality
    modality_requirement_file = modality_path / "requirements.txt"
    if modality_requirement_file.exists():
        with open(modality_requirement_file) as f:
            modality_requirements = f.readlines()
            extras_require["full"].extend(modality_requirements)
            extras_require[modality].extend(modality_requirements)

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

setup(
    name="neuroconv",
    version="0.2.1",
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
