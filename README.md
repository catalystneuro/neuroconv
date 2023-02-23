[![PyPI version](https://badge.fury.io/py/neuroconv.svg)](https://badge.fury.io/py/neuroconv.svg)
![Full Tests](https://github.com/catalystneuro/neuroconv/actions/workflows/testing.yml/badge.svg)
![Auto-release](https://github.com/catalystneuro/neuroconv/actions/workflows/auto-publish.yml/badge.svg)
[![codecov](https://codecov.io/github/catalystneuro/neuroconv/coverage.svg?branch=main)](https://codecov.io/github/catalystneuro/neuroconv?branch=main)
[![documentation](https://readthedocs.org/projects/neuroconv/badge/?version=main)](https://neuroconv.readthedocs.io/en/main/)
[![License](https://img.shields.io/pypi/l/pynwb.svg)](https://github.com/catalystneuro/neuroconv/license.txt)

# NeuroConv

NeuroConv is a package for creating NWB files by converting and
combining neural data in proprietary formats and adding essential metadata.


Features:
* Command line interface
* Python API
* Leverages SpikeExtractor to support conversion from a number or proprietary formats.

## Installation
To install the latest stable release of **neuroconv** though PyPI, type:
```shell
pip install neuroconv
```

For more flexibility we recommend installing the latest version directly from GitHub. The following commands create an environment with all the required dependencies and the latest updates:

```shell
git clone https://github.com/catalystneuro/neuroconv
cd neuroconv
conda env create -f make_environment.yml
conda activate neuroconv_environment
```
Note that this will install the package in [editable mode](https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs).

Finally, if you prefer to avoid `conda` altogether, the following commands provide a clean installation within the current environment:
```shell
pip install git+https://github.com/catalystneuro/neuroconv.git@master
```

## Dependencies
NeuroConv relies heavily on [SpikeInterface](https://github.com/SpikeInterface/spikeinterface) and [SpikeExtractors](https://github.com/SpikeInterface/spikeextractors) for electrophysiology and on [ROIExtractors](https://github.com/catalystneuro/roiextractors) for optophysiology data.
