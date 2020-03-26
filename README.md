# nwbn-conversion-tools
Shared tools for converting data from various formats to NWB:N 2.0

[![PyPI version](https://badge.fury.io/py/nwbn-conversion-tools.svg)](https://badge.fury.io/py/nwbn-conversion-tools)

## Installation
To install **nwbn-conversion-tools** directly in an existing environment:
```
$ pip install nwbn-conversion-tools
```

Alternatively, to clone the repository and set up a conda environment, do:
```
$ git clone https://github.com/NeurodataWithoutBorders/nwbn-conversion-tools
$ conda env create -f nwbn-conversion-tools/make_env.yml
$ source activate nwbn_conversion
```

## GUI
The Graphic User Interface of nwbn-conversion-tools provides an user-friendly way of editing metafiles for the conversion tasks and for exploring nwb files with [nwb-jupyter-widgets](https://github.com/NeurodataWithoutBorders/nwb-jupyter-widgets) and an embedded IPython console.

After activating the correct environment, nwbn_conversion_tools GUI can be called from command line:
```shell
nwbn-gui
```

To initiate the GUI with a specific metafile:
```shell
nwbn-gui metafile.yml
```

The GUI can also be imported and run from python scripts:
```python
from nwbn_conversion_tools.gui.nwbn_conversion_gui import nwbn_conversion_gui

# YAML metafile
metafile = 'metafile.yml'

# Conversion module
conversion_module = 'conversion_module.py'

# Source files path
source_paths = {}
source_paths['source_file_1'] = {'type': 'file', 'path': ''}
source_paths['source_file_2'] = {'type': 'file', 'path': ''}

# Other options
kwargs = {'option_1': True, 'option_2': False}

nwbn_conversion_gui(
    metafile=metafile,
    conversion_module=conversion_module,
    source_paths=source_paths,
    kwargs_fields=kwargs,
)
```
[Here](https://github.com/NeurodataWithoutBorders/nwbn-conversion-tools/tree/master/nwbn_conversion_tools/gui) you can find templates for `metafile.yml` and `conversion_module.py`.

<details>
  <summary>
    <strong>GUI demonstration</strong>
  </summary>

  ![](images/gif_gui_demonstration.gif)

</details>

## Converters
#### Optophysiology
* [CELLMax](https://github.com/NeurodataWithoutBorders/nwbn-conversion-tools/blob/master/nwbn_conversion_tools/ophys/processing/CELLMax/README.md)

#### Electrophysiology
* [SpikeGLX](https://github.com/NeurodataWithoutBorders/nwbn-conversion-tools/blob/master/nwbn_conversion_tools/ecephys/spikeglx/README.md)
* [Intan](https://github.com/NeurodataWithoutBorders/nwbn-conversion-tools/blob/master/nwbn_conversion_tools/ecephys/intan/README.md)

#### Behavior
* [Bpod](https://github.com/NeurodataWithoutBorders/nwbn-conversion-tools/blob/master/nwbn_conversion_tools/behavior/bpod/README.md)


## Used by

* [Axel lab](https://www.axellab.columbia.edu/)
* [Buffalo lab](https://buffalomemorylab.com/)
* [Giocomo lab](https://giocomolab.weebly.com/)
* [Jaeger lab](https://scholarblogs.emory.edu/jaegerlab/)
* [Tolias lab](https://toliaslab.org/)
