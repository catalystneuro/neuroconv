[![PyPI version](https://badge.fury.io/py/neuroconv.svg)](https://badge.fury.io/py/neuroconv.svg)
![Daily Tests](https://github.com/catalystneuro/neuroconv/actions/workflows/dailies.yml/badge.svg)
![Auto-release](https://github.com/catalystneuro/neuroconv/actions/workflows/auto-publish.yml/badge.svg)
[![codecov](https://codecov.io/github/catalystneuro/neuroconv/coverage.svg?branch=main)](https://codecov.io/github/catalystneuro/neuroconv?branch=main)
[![documentation](https://readthedocs.org/projects/neuroconv/badge/?version=main)](https://neuroconv.readthedocs.io/en/main/)
[![Python](https://img.shields.io/pypi/pyversions/neuroconv.svg)](https://pypi.python.org/pypi/neuroconv)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black)
[![License](https://img.shields.io/pypi/l/neuroconv.svg)](https://github.com/catalystneuro/neuroconv/license.txt)

<p align="center">
  <img src="https://raw.githubusercontent.com/catalystneuro/neuroconv/main/docs/img/neuroconv_logo.png" width="250" alt="NeuroConv logo"/>
  <h3 align="center">Automatically convert neurophysiology data to NWB</h3>
</p>

<p align="center">
   <a href="https://neuroconv.readthedocs.io/"><strong>Explore our documentation »</strong></a>
</p>


<!-- TABLE OF CONTENTS -->

## Table of Contents

- [About](#about)
- [Installation](#installation)
- [Documentation](#documentation)
- [License](#license)

## About

NeuroConv is a Python package for converting neurophysiology data in a variety of proprietary formats to the [Neurodata Without Borders (NWB)](http://nwb.org) standard.

Features:

* Reads data from 40 popular neurophysiology data formats and writes to NWB using best practices.
* Extracts relevant metadata from each format.
* Handles large data volume by reading datasets piece-wise.
* Minimizes the size of the NWB files by automatically applying chunking and lossless compression.
* Supports ensembles of multiple data streams, and supports common methods for temporal alignment of streams.

## Installation
We always recommend installing and running Python packages in a clean environment. One way to do this is via [conda environments](https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#activating-an-environment):

```shell
conda create --name <give the environment a name> --python <choose a version of Python to use>
conda activate <environment name>
```

To install the latest stable release of **neuroconv** though PyPI, run:

```shell
pip install neuroconv
```

To install the current unreleased `main` branch (requires `git` to be installed in your environment, such was via `conda install git`), run:

```shell
pip install git+https://github.com/catalystneuro/neuroconv.git@main
```

NeuroConv also supports a variety of extra dependencies that can be specified inside square brackets, such as

```shell
pip install "neuroconv[openephys, dandi]"
```

which will then install extra dependencies related to reading OpenEphys data as well as the usage of the DANDI CLI (such as automatic upload to the [DANDI Archive](https://www.dandiarchive.org/)).

You can read more about these options in the main [installation guide](https://neuroconv.readthedocs.io/en/main/user_guide/datainterfaces.html#installation).


## Documentation
See our [ReadTheDocs page](https://neuroconv.readthedocs.io/en/main/) for full documentation, including a gallery of all supported formats.

## License
NeuroConv is distributed under the BSD3 License. See [LICENSE](https://github.com/catalystneuro/neuroconv/blob/main/license.txt) for more information.
