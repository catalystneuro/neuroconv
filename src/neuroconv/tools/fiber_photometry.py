from typing import Literal

from pynwb import NWBFile

from neuroconv.tools import get_package


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
    ndx_fiber_photometry = get_package("ndx_fiber_photometry")

    device_name = device_metadata["name"]
    if device_name in nwbfile.devices:
        return

    photometry_device = dict(
        OpticalFiber=ndx_fiber_photometry.OpticalFiber,
        ExcitationSource=ndx_fiber_photometry.ExcitationSource,
        Photodetector=ndx_fiber_photometry.Photodetector,
        BandOpticalFilter=ndx_fiber_photometry.BandOpticalFilter,
        EdgeOpticalFilter=ndx_fiber_photometry.EdgeOpticalFilter,
        DichroicMirror=ndx_fiber_photometry.DichroicMirror,
        Indicator=ndx_fiber_photometry.Indicator,
    )[device_type](**device_metadata)

    nwbfile.add_device(photometry_device)
