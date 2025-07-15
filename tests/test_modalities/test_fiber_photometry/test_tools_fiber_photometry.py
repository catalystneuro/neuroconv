from neuroconv.tools.fiber_photometry import add_fiber_photometry_device
import re
from pynwb.testing.mock.file import mock_NWBFile
import pytest


# TODO: remove skip when https://github.com/catalystneuro/neuroconv/issues/1429 is fixed
# ruff: noqa: I001
from packaging import version
import pynwb


pytestmark = pytest.mark.skipif(
    version.parse(pynwb.__version__) >= version.parse("3.1.0"),
    reason="TestTDTFiberPhotometryInterface doesn't work with pynwb>=3.1.0.",
)


def test_add_fiber_photometry_device_invalid_device_type():
    nwbfile = mock_NWBFile()
    valid_device_types = [
        "OpticalFiber",
        "ExcitationSource",
        "Photodetector",
        "BandOpticalFilter",
        "EdgeOpticalFilter",
        "DichroicMirror",
        "Indicator",
    ]
    with pytest.raises(AssertionError, match=re.escape(f"device_type must be one of {valid_device_types}")):
        add_fiber_photometry_device(
            nwbfile=nwbfile,
            device_metadata={},
            device_type="invalid_device_type",
        )


def test_add_fiber_photometry_device_twice():
    nwbfile = mock_NWBFile()
    device_metadata = {
        "name": "optical_fiber",
        "description": "description",
        "manufacturer": "Doric Lenses",
        "model": "Fiber Optic Implant",
        "numerical_aperture": 0.48,
        "core_diameter_in_um": 400.0,
    }
    add_fiber_photometry_device(nwbfile=nwbfile, device_metadata=device_metadata, device_type="OpticalFiber")
    add_fiber_photometry_device(nwbfile=nwbfile, device_metadata=device_metadata, device_type="OpticalFiber")
    assert len(nwbfile.devices) == 1
    assert "optical_fiber" in nwbfile.devices
    assert nwbfile.devices["optical_fiber"].name == "optical_fiber"
    assert nwbfile.devices["optical_fiber"].description == "description"
    assert nwbfile.devices["optical_fiber"].manufacturer == "Doric Lenses"
    assert nwbfile.devices["optical_fiber"].model == "Fiber Optic Implant"
    assert nwbfile.devices["optical_fiber"].numerical_aperture == 0.48
    assert nwbfile.devices["optical_fiber"].core_diameter_in_um == 400.0
    assert nwbfile.devices["optical_fiber"].__class__.__name__ == "OpticalFiber"
