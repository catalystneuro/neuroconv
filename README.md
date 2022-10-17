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


## Catalogue
### v0.9.3
#### [Buzsáki Lab](https://buzsakilab.com/wp/): [buzsaki-lab-to-nwb](https://github.com/catalystneuro/buzsaki-lab-to-nwb)
This project is an ongoing effort for the Ripple U19 conversion of extracellular electrophysiology data to NWB format, including final publishing of each dataset on DANDI. Currently spans 7 major publications and over 14 TB of data on the [DANDI Archive](https://www.dandiarchive.org/). Most of the data consists of raw recordings, LFP, spike sorted units, and behavior with can consist of a mix of mental state tracking, position tracking through mazes, and trial stimulus events.

#### [Shenoy lab](https://npsl.sites.stanford.edu): [shenoy-lab-to-nwb](https://github.com/catalystneuro/shenoy-lab-to-nwb):
The Shenoy lab is one of the pioneers in developing BCIs for people with paralysis. They are part of the [BrainGate](https://www.braingate.org) team
and were the winners of the 2019 [BCI award](https://www.bci-award.com/2019).
They use extracellular recordings from Utah arrays and Neuropixels in primates.

### v0.9.2
#### [Brody Lab](http://brodylab.org/): [brody-lab-to-nwb](https://github.com/catalystneuro/brody-lab-to-nwb)
The Brody lab has a long history with extracellular electrophysiology experiements spanning multiple acquisition systems. This project served two purposes - to allow the conversion of older data from Neuralynx and SpikeGadgets to NWB, and also their newer, larger data using Neuropixels (SpikeGLX). These recordings, some of which exceeded more than 250 GB (several hours worth!), were paired with rich trials tables containing catagorical events and temporal stimuli.

### v0.8.10
#### [Feldman Lab](https://www.feldmanlab.org/): [feldman-lab-to-nwb](https://github.com/catalystneuro/feldman-lab-to-nwb)
The Feldman lab utilizes a Neuropixels (SpikeGLX) system along with multiple sophisticated behavior systems for manipulating whisker stimulation in mice. These give rise to very complex trials tables tracking multiple event times throughout the experiments, including multiple event trains within trials.

### v0.8.1
#### Hussaini Lab: [hussaini-lab-to-nwb](https://github.com/catalystneuro/hussaini-lab-to-nwb)

### v0.7.2
#### [Movson lab](https://www.cns.nyu.edu/labs/movshonlab/): [movshon-lab-to-nwb](https://github.com/catalystneuro/movshon-lab-to-nwb)

### v0.7.0
#### [Tank Lab](https://pni.princeton.edu/faculty/david-tank): [tank-lab-to-nwb](https://github.com/catalystneuro/tank-lab-to-nwb)
Neuropixel (SpikeGLX) recordings of subjects navigating a virtual reality! Behavior contains a huge variety of NWB data types including positional and view angle over time,  collision detection, and more! Paired with a [specific extension](https://github.com/catalystneuro/ndx-tank-metadata) for parsing experiment metadata.

#### [Groh lab](https://www.uni-heidelberg.de/izn/researchgroups/groh/): [mease-lab-to-nwb](https://github.com/catalystneuro/mease-lab-to-nwb)
Utilizing the CED recording interface, this project paired ecephys channels with optogenetic stimulation via laser pulses, and mechnical pressure stimulation over time - all of which are channels of data extracted from the common `.smrx` files!

#### [Giocomo lab](https://giocomolab.weebly.com/): [giocomo-lab-to-nwb](https://github.com/catalystneuro/giocomo-lab-to-nwb/tree/master/giocomo_lab_to_nwb/mallory21)


### Other labs that use NWB standard
* [Axel lab](https://www.axellab.columbia.edu/): [axel-lab-to-nwb](https://github.com/catalystneuro/axel-lab-to-nwb)
* [Brunton lab](https://www.bingbrunton.com/): [brunton-lab-to-nwb](https://github.com/catalystneuro/brunton-lab-to-nwb)
* [Buffalo lab](https://buffalomemorylab.com/): [buffalo-lab-data-to-nwb](https://github.com/catalystneuro/buffalo-lab-data-to-nwb)
* [Jaeger lab](https://scholarblogs.emory.edu/jaegerlab/): [jaeger-lab-to-nwb](https://github.com/catalystneuro/jaeger-lab-to-nwb)
* [Tolias lab](https://toliaslab.org/): [tolias-lab-to-nwb](https://github.com/catalystneuro/tolias-lab-to-nwb)


# For Developers
## Running GIN tests locally
`neuroconv` verifies the integrity of all code changes by running a full test suite on short examples of real data from the formats we support. There are two classes of tests in this regard; `tests/test_internals` does not require any data to be present and represents the 'minimal' expected behavior for our package, whereas `tests/test_on_data` requires the user to both perform a full install of dependencies (`pip install -r requirements-full.txt`) as well as download the associated data for each modality.

### Install testing dependencies
In a clean environment run:

```shell
git clone https://github.com/catalystneuro/neuroconv
cd neuroconv
pip install .[test,full]
```

### Downloading the data
[Datalad](https://www.datalad.org/) (`conda install datalad`) is the recommended way for downloading the data. To do this; simply call:

For electrophysiology data:
```shell
datalad install -rg https://gin.g-node.org/NeuralEnsemble/ephy_testing_data
```

For optical physiology data:
```shell
datalad install -rg https://gin.g-node.org/CatalystNeuro/ophys_testing_data
```

For behavioral data:
```shell
datalad install -rg https://gin.g-node.org/CatalystNeuro/behavior_testing_data
```


### Test configuration file
Once the data is downloaded to your system, you must manually modify the config file ([example](https://github.com/catalystneuro/nwb-conversion-tools/blob/main/base_gin_test_config.json)) located in `./tests/test_on_data/gin_test_config.json` so its corresponding `LOCAL_PATH` key points to the correct folder on your system that contains the dataset folder (e.g., `ephy_testing_data` for testing `ecephys`). The code will automatically detect that the tests are being run locally, so all you need to do ensure the path is correct to your specific system.

The output of these tests is, by default, stored in a temporary directory that is then cleaned after the tests finish running. To examine these files for quality assessment purposes, set the flag `SAVE_OUTPUTS=true` in the `gin_test_config.json` file and modify the variable `OUTPUT_PATH` in the respective test if necessary.

## Build the documentation
For building the documentation locally, the following procedure can be followed. Create a clean environment and type
the following commands in your terminal:
```shell
git clone https://github.com/catalystneuro/neuroconv
cd neuroconv
pip install -e .[docs]
```
These commands install both the latest version of the repo and the dependencies necessary to build the documentation.
Note that the argument `-e` makes you install [editable](https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs)

Now, to build the documention issue the following command in your terminal:
```shell
sphinx-build -b html docs ./docs/_build/
```

This builds the html under `/docs/_build/` (from your root directory, where you have installed `neuroconv`). This allows you to review the outcome of the process localy before commiting code.
