[![PyPI version](https://badge.fury.io/py/nwb-conversion-tools.svg)](https://badge.fury.io/py/nwb-conversion-tools)
![Partial (lazy) Tests](https://github.com/catalystneuro/nwb-conversion-tools/actions/workflows/partial-tests.yml/badge.svg)
![Full Tests](https://github.com/catalystneuro/nwb-conversion-tools/actions/workflows/full-tests-linux.yml/badge.svg)
![Auto-release](https://github.com/catalystneuro/nwb-conversion-tools/actions/workflows/auto-publish.yml/badge.svg)
[![codecov](https://codecov.io/github/catalystneuro/nwb-conversion-tools/coverage.svg?branch=main)](https://codecov.io/github/catalystneuro/nwb-conversion-tools?branch=master)
[![documentation](https://readthedocs.org/projects/nwb-conversion-tools/badge/?version=master)](https://nwb-conversion-tools.readthedocs.io/en/master/)
[![License](https://img.shields.io/pypi/l/pynwb.svg)](https://github.com/catalystneuro/nwb-conversion-tools/license.txt)

# NWB conversion tools

NWB Conversion Tools is a package for creating NWB files by converting and 
combining neural data in proprietary formats and adding essential metadata.

**Under heavy construction. API is changing rapidly.**


Features:
* Command line interface
* Python API
* Leverages SpikeExtractor to support conversion from a number or proprietary formats.

## Installation
To install the latest stable release of **nwb-conversion-tools** though PyPI, type:
```shell
pip install nwb-conversion-tools
```

For more flexibility we recommend installing the latest version directly from GitHub. The following commands create an environment with all the required dependencies and the latest updates:

```shell
git clone https://github.com/catalystneuro/nwb-conversion-tools
cd nwb-conversion-tools
conda env create -f make_env.yml
conda activate nwb_conversion_env
```
Note that this will install the package in [editable mode](https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs). 

Finally, if you prefer to avoid `conda` altogether, the following commands provide a clean installation within the current environment:
```shell
pip install git+https://github.com/catalystneuro/nwb-conversion-tools.git@master
```

## Dependencies
NWB Conversion Tools relies heavily on [SpikeExtractors](https://github.com/SpikeInterface/spikeextractors) for electrophysiology and on [ROIExtractors](https://github.com/catalystneuro/roiextractors) for optophysiology data.

You can use a graphical interface for your converter with [NWB Web GUI](https://github.com/catalystneuro/nwb-web-gui).


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
`nwb-conversion-tools` verifies the integrity of all code changes by running a full test suite on short examples of real data from the formats we support. There are two classes of tests in this regard; `tests/test_internals` does not require any data to be present and represents the 'minimal' expected behavior for our package, whereas `tests/test_on_data` requires the user to both perform a full install of dependencies (`pip install -r requirements-full.txt`) as well as download the associated data for each modality. 

### Install testing dependencies
We provide two easy ways of installing all the dependencies required for testing:

1) The first is a `conda` based solution that creates an environment with all the dependencies already installed.

```shell
git clone https://github.com/catalystneuro/nwb-conversion-tools
cd nwb-conversion-tools
conda env create -f make_env_testing.yml
conda activate nwb_conversion_testing_env
```

Note that this will also install `datalad` which is the endorsed way of downloading the testing data plus `pytest` and `pytest-cov` which are the tools that we use on our continuous integration suit. 

2) The same can be accomplished by using `pip`. In a clean environment run:

```shell
git clone https://github.com/catalystneuro/nwb-conversion-tools
cd nwb-conversion-tools
pip install .[test_full]
```

Notice that this method does not install `datalad`.
### Downloading the data
[Datalad](https://www.datalad.org/) (`conda install datalad`) is the recommended way for downloading the data. To do this; simply call:

```shell
datalad install -rg https://gin.g-node.org/NeuralEnsemble/ephy_testing_data
```
to install the `ecephys` data, and

```shell
datalad install -rg https://gin.g-node.org/CatalystNeuro/ophys_testing_data
```
for `ophys` data.


### Test configuration file
Once the data is downloaded to your system, you must manually modify the [config file](https://github.com/catalystneuro/nwb-conversion-tools/blob/main/tests/test_on_data/gin_test_config.json) located in `./tests/test_on_data/gin_test_config.json` so its corresponding `LOCAL_PATH` key points to the correct folder on your system that contains the dataset folder (e.g., `ephy_testing_data` for testing `ecephys`). The code will automatically detect that the tests are being run locally, so all you need to do ensure the path is correct to your specific system.

The output of these tests is, by default, stored in a temporary directory that is then cleaned after the tests finish running. To examine these files for quality assessment purposes, set the flag `SAVE_OUTPUTS=true` in the same `gin_test_config.json` file mentioned in the last paragraph and modify the variable `OUTPUT_PATH` in the respective test if necessary.

## Rebuilding on Read the Docs
As a maintainer, once the changes to the documentation are on the master branch, go to [https://readthedocs.org/projects/nwb-conversion-tools/](https://readthedocs.org/projects/nwb-conversion-tools/) and click "Build version". Check the console output and its log for any errors.
