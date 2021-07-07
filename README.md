# NWB conversion tools
[![PyPI version](https://badge.fury.io/py/nwb-conversion-tools.svg)](https://badge.fury.io/py/nwb-conversion-tools)

NWB Conversion Tools is a package for creating NWB files by converting and 
combining neural data in proprietary formats and adding essential metadata.

**Under heavy construction. API is changing rapidly.**


Features:
* Command line interface
* Python API
* Leverages SpikeExtractor to support conversion from a number or proprietary formats.

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

## Dependencies
NWB Conversion Tools relies heavily on [SpikeExtractors](https://github.com/SpikeInterface/spikeextractors) for electrophysiology and on [ROIExtractors](https://github.com/catalystneuro/roiextractors) for optophysiology data.

You can use a graphical interface for your converter with [NWB Web GUI](https://github.com/catalystneuro/nwb-web-gui).


## Rebuilding on Read the Docs
As a maintainer, once the changes to the documentation are on the master branch, go to [https://readthedocs.org/projects/nwb-conversion-tools/](https://readthedocs.org/projects/nwb-conversion-tools/) and click "Build version". Check the console output and its log for any errors.


## Used by

* [Axel lab](https://www.axellab.columbia.edu/): [axel-lab-to-nwb](https://github.com/catalystneuro/axel-lab-to-nwb)
* Brunton lab: [brunton-lab-to-nwb](https://github.com/catalystneuro/brunton-lab-to-nwb)
* [Buffalo lab](https://buffalomemorylab.com/): [buffalo-lab-data-to-nwb](https://github.com/catalystneuro/buffalo-lab-data-to-nwb)
* [Buzsáki Lab](https://buzsakilab.com/wp/): [buzsaki-lab-to-nwb](https://github.com/catalystneuro/buzsaki-lab-to-nwb)
* [Giocomo lab](https://giocomolab.weebly.com/): [giocomo-lab-to-nwb](https://github.com/catalystneuro/giocomo-lab-to-nwb)
* [Jaeger lab](https://scholarblogs.emory.edu/jaegerlab/): [jaeger-lab-to-nwb](https://github.com/catalystneuro/jaeger-lab-to-nwb)
* Mease lab: [mease-lab-to-nwb](https://github.com/catalystneuro/mease-lab-to-nwb)
* [Movson lab](https://www.cns.nyu.edu/labs/movshonlab/): [movshon-lab-to-nwb](https://github.com/catalystneuro/movshon-lab-to-nwb)
* [Tolias lab](https://toliaslab.org/): [tolias-lab-to-nwb](https://github.com/catalystneuro/tolias-lab-to-nwb)
