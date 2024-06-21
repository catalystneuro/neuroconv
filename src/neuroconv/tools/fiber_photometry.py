from typing import Literal

from ndx_fiber_photometry import (
    BandOpticalFilter,
    DichroicMirror,
    EdgeOpticalFilter,
    ExcitationSource,
    Indicator,
    OpticalFiber,
    Photodetector,
)
from pynwb import NWBFile


def add_fiber_photometry_device(
    *,
    nwbfile: NWBFile,
    device_metadata: dict,
    device_type: Literal[
        "OpticalFiber",
        "ExcitationSource",
        "Photodetector",
        "BandOpticalFilter",
        "EdgeOpticalFilter",
        "DichroicMirror",
        "Indicator",
    ],
):
    """Add a photometry device to an NWBFile object."""
    valid_device_types = [
        "OpticalFiber",
        "ExcitationSource",
        "Photodetector",
        "BandOpticalFilter",
        "EdgeOpticalFilter",
        "DichroicMirror",
        "Indicator",
    ]
    assert device_type in valid_device_types, f"device_type must be one of {valid_device_types}"

    device_name = device_metadata["name"]
    if device_name in nwbfile.devices:
        return

    photometry_device = dict(
        OpticalFiber=OpticalFiber,
        ExcitationSource=ExcitationSource,
        Photodetector=Photodetector,
        BandOpticalFilter=BandOpticalFilter,
        EdgeOpticalFilter=EdgeOpticalFilter,
        DichroicMirror=DichroicMirror,
        Indicator=Indicator,
    )[device_type](**device_metadata)

    nwbfile.add_device(photometry_device)
