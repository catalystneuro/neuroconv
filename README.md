# NWB conversion tools
NWB Conversion Tools is a package for creating NWB files by converting and 
combining neural data in proprietary formats and adding essential metadata.

**Under heavy construction. API is changing rapidly.**


Features:
* Command line interface
* Python API
* Leverages SpikeExtractor to support conversion from a number or proprietary formats.

[![PyPI version](https://badge.fury.io/py/nwb-conversion-tools.svg)](https://badge.fury.io/py/nwb-conversion-tools)

## Installation
To install **nwb-conversion-tools** directly in an existing environment:
```
$ pip install nwb-conversion-tools
```

Alternatively, to clone the repository and set up a conda environment, do:
```
$ git clone https://github.com/catalystneuro/nwb-conversion-tools
$ cd nwb-conversion-tools
$ conda env create -f make_env.yml
$ conda activate nwb_conversion_env
$ pip install .
```

## Used by

* [Axel lab](https://www.axellab.columbia.edu/): [axel-lab-to-nwb](https://github.com/catalystneuro/axel-lab-to-nwb)
* [Buffalo lab](https://buffalomemorylab.com/): [buffalo-lab-data-to-nwb](https://github.com/catalystneuro/buffalo-lab-data-to-nwb)
* [Giocomo lab](https://giocomolab.weebly.com/): [giocomo-lab-to-nwb](https://github.com/catalystneuro/giocomo-lab-to-nwb)
* [Jaeger lab](https://scholarblogs.emory.edu/jaegerlab/): [jaeger-lab-to-nwb](https://github.com/catalystneuro/jaeger-lab-to-nwb)
* [Tolias lab](https://toliaslab.org/): [tolias-lab-to-nwb](https://github.com/catalystneuro/tolias-lab-to-nwb)
