from .nwbconverter import NWBConverter
from .tools import spikeinterface, roiextractors, neo
from .tools.yaml_conversion_specification import run_conversion_from_yaml

interface_location = dict(
    DeepLabCutInterface="datainterfaces.behavior.deeplabcut",
    NeuroscopeRecordingInterface="datainterfaces.ecephys.neuroscope",
)

__all__ = [
    "NWBConverter",
    "run_conversion_from_yaml",
    "neo",
    "roiextractors",
    "spikeinterface",
    "tools",
    "utils",
] + list(interface_location.keys())


def __getattr__(name: str):
    from importlib import import_module

    if name in interface_location:
        return getattr(import_module("." + interface_location[name], __name__), name)


def __dir__():
    return __all__
