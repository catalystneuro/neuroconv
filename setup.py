from setuptools import setup, find_packages
from codecs import open
import os

path = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(path, "README.md")) as f:
    long_description = f.read()
with open(os.path.join(path, "requirements-minimal.txt")) as f:
    install_requires = f.read().strip().split("\n")
setup(
    name="nwb-conversion-tools",
    version="0.9.9",
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
