from copy import deepcopy
from typing import Literal

from pynwb import NWBFile

from neuroconv.tools import get_package


def add_ophys_device_model(
    *,
    nwbfile: NWBFile,
    device_metadata: dict,
    device_type: Literal[
        "OpticalFiberModel",
        "ExcitationSourceModel",
        "PhotodetectorModel",
        "BandOpticalFilterModel",
        "EdgeOpticalFilterModel",
        "DichroicMirrorModel",
    ],
):
    """Add an optical physiology device model to an NWBFile object."""
    valid_device_types = [
        "OpticalFiberModel",
        "ExcitationSourceModel",
        "PhotodetectorModel",
        "BandOpticalFilterModel",
        "EdgeOpticalFilterModel",
        "DichroicMirrorModel",
    ]
    assert device_type in valid_device_types, f"device_type must be one of {valid_device_types}"
    ndx_ophys_devices = get_package("ndx_ophys_devices")

    device_name = device_metadata["name"]
    if device_name in nwbfile.device_models:
        return

    ophys_device_model = dict(
        OpticalFiberModel=ndx_ophys_devices.OpticalFiberModel,
        ExcitationSourceModel=ndx_ophys_devices.ExcitationSourceModel,
        PhotodetectorModel=ndx_ophys_devices.PhotodetectorModel,
        BandOpticalFilterModel=ndx_ophys_devices.BandOpticalFilterModel,
        EdgeOpticalFilterModel=ndx_ophys_devices.EdgeOpticalFilterModel,
        DichroicMirrorModel=ndx_ophys_devices.DichroicMirrorModel,
    )[device_type](**device_metadata)

    nwbfile.add_device_model(ophys_device_model)


def add_ophys_device(
    *,
    nwbfile: NWBFile,
    device_metadata: dict,
    device_type: Literal[
        "ExcitationSource",
        "Photodetector",
        "BandOpticalFilter",
        "EdgeOpticalFilter",
        "DichroicMirror",
    ],
):
    """Add an optical physiology device instance to an NWBFile object."""
    valid_device_types = [
        "ExcitationSource",
        "Photodetector",
        "BandOpticalFilter",
        "EdgeOpticalFilter",
        "DichroicMirror",
    ]
    assert device_type in valid_device_types, f"device_type must be one of {valid_device_types}"
    ndx_ophys_devices = get_package("ndx_ophys_devices")

    device_name = device_metadata["name"]
    if device_name in nwbfile.devices:
        return

    if isinstance(device_metadata["model"], str):
        assert (
            device_metadata["model"] in nwbfile.device_models
        ), f"Device model {device_metadata['model']} not found in NWBFile devices for {device_name}."
        device_model = nwbfile.device_models[device_metadata["model"]]
        device_metadata = deepcopy(device_metadata)
        device_metadata["model"] = device_model

    ophys_device = dict(
        OpticalFiber=ndx_ophys_devices.OpticalFiber,
        ExcitationSource=ndx_ophys_devices.ExcitationSource,
        Photodetector=ndx_ophys_devices.Photodetector,
        BandOpticalFilter=ndx_ophys_devices.BandOpticalFilter,
        EdgeOpticalFilter=ndx_ophys_devices.EdgeOpticalFilter,
        DichroicMirror=ndx_ophys_devices.DichroicMirror,
    )[device_type](**device_metadata)

    nwbfile.add_device(ophys_device)
