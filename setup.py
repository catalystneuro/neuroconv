from setuptools import setup, find_packages
import subprocess

# To use a consistent encoding
from codecs import open
import os


here = os.path.abspath(os.path.dirname(__file__))

# Get the long description from the README file
with open(os.path.join(here, "README.md")) as f:
    long_description = f.read()

# Get requirements
if os.environ.get("NWB_CONVERSION_INSTALL_MODE", None) == "development":
    req_file = "requirements-dev.txt"
    print("installing nwb_conversion_tools on development mode")
else:
    req_file = "requirements.txt"

with open(os.path.join(here, req_file)) as f:
    install_requires = f.read().strip().split("\n")

# Get remote version
remote_version = subprocess.run(["git", "describe", "--tags"], stdout=subprocess.PIPE).stdout.decode("utf-8").strip()
assert "." in remote_version

setup(
    name="nwb-conversion-tools",
    version="0.9.4",
    description="Convert data from proprietary formats to NWB format.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ben Dichter, Cody Baker, and Luiz Tauffer",
    author_email="ben.dichter@gmail.com",
    url="https://github.com/catalystneuro/nwb-conversion-tools",
    keywords="nwb",
    packages=find_packages(),
    package_data={"": ["template_metafile.yml"]},
    include_package_data=True,
    python_requires=">=3.7",
    install_requires=install_requires,
    entry_points={
        "console_scripts": ["nwb-gui=nwb_conversion_tools.gui.command_line:main"],
    },
)
