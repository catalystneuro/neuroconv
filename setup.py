from setuptools import setup, find_packages
from codecs import open
from pathlib import Path
import os
from shutil import copy

path = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(path, "README.md")) as f:
    long_description = f.read()
with open(os.path.join(path, "requirements-minimal.txt")) as f:
    install_requires = f.readlines()
with open(os.path.join(path, "requirements-full.txt")) as f:
    full_dependencies = f.readlines()
with open(os.path.join(path, "requirements-rtd.txt")) as f:
    documentation_dependencies = f.readlines()

testing_suite_dependencies = [
    "pytest",
    "pytest-cov",
    "ndx-events==0.2.0",
    "parameterized==0.8.1",
    "ndx-dandi-icephys>=0.4.0",
]
extras_require = dict(full=full_dependencies, test=testing_suite_dependencies, docs=documentation_dependencies)

# Create a local copy for the gin test configuration file based on the master file `base_gin_test_config.json`
gin_config_file_base = Path("./base_gin_test_config.json")
gin_config_file_local = Path("./tests/test_on_data/gin_test_config.json")
if not gin_config_file_local.exists():
    copy(src=gin_config_file_base, dst=gin_config_file_local)

setup(
    name="nwb-conversion-tools",
    version="0.11.22",
    description="Convert data from proprietary formats to NWB format.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ben Dichter, Cody Baker, and Luiz Tauffer",
    author_email="ben.dichter@gmail.com",
    url="https://github.com/catalystneuro/nwb-conversion-tools",
    keywords="nwb",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,  # Includes files described in MANIFEST.in in the installation.
    python_requires=">=3.7",
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": ["nwb-gui=nwb_conversion_tools.gui.command_line:main"],
    },
)
