from .nwbconverter import NWBConverter
from .tools import spikeinterface, roiextractors, neo
from .tools.yaml_conversion_specification import run_conversion_from_yaml


def __getattr__(name: str):
    from importlib import import_module

    interface_location = dict(DeepLabCutInterface="datainterfaces.behavior.deeplabcut")
    if name == "DeepLabCutInterface":
        return getattr(import_module("." + interface_location[name], __name__), name)
