import re

import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.fiber_photometry import add_fiber_photometry_device


@pytest.mark.parametrize(
    "device_type, device_metadata",
    [
        (
            "OpticalFiber",
            {
                "name": "optical_fiber",
                "description": "description",
                "manufacturer": "Doric Lenses",
                "model": "Fiber Optic Implant",
                "numerical_aperture": 0.48,
                "core_diameter_in_um": 400.0,
            },
        ),
        (
            "ExcitationSource",
            {
                "name": "excitation_source",
                "description": "description",
                "manufacturer": "Doric Lenses",
                "model": "Connectorized LED",
                "illumination_type": "LED",
                "excitation_wavelength_in_nm": 405.0,
            },
        ),
        (
            "Photodetector",
            {
                "name": "photodetector",
                "description": "description",
                "manufacturer": "Doric Lenses",
                "model": "Newport Visible Femtowatt Photoreceiver Module",
                "detector_type": "photodiode",
                "detected_wavelength_in_nm": 525.0,
                "gain": 1.0e10,
            },
        ),
        (
            "BandOpticalFilter",
            {
                "name": "emission_filter",
                "description": "description",
                "manufacturer": "Doric Lenses",
                "model": "4 ports Fluorescence Mini Cube - GCaMP",
                "center_wavelength_in_nm": 525.0,
                "bandwidth_in_nm": 50.0,
                "filter_type": "Bandpass",
            },
        ),
        (
            "EdgeOpticalFilter",
            {
                "name": "excitation_filter",
                "description": "description",
                "manufacturer": "Doric Lenses",
                "model": "4 ports Fluorescence Mini Cube - GCaMP",
                "cut_wavelength_in_nm": 475.0,
                "slope_in_percent_cut_wavelength": 1.0,
                "slope_starting_transmission_in_percent": 10.0,
                "slope_ending_transmission_in_percent": 80.0,
                "filter_type": "Longpass",
            },
        ),
        (
            "DichroicMirror",
            {
                "name": "dichroic_mirror",
                "description": "description",
                "manufacturer": "Doric Lenses",
                "model": "4 ports Fluorescence Mini Cube - GCaMP",
            },
        ),
        (
            "Indicator",
            {
                "name": "indicator",
                "description": "description",
                "manufacturer": "Addgene",
                "label": "GCaMP7b",
                "injection_location": "medial SNc",
                "injection_coordinates_in_mm": [3.1, 0.8, 4.7],
            },
        ),
    ],
)
def test_add_fiber_photometry_device(device_type, device_metadata):
    nwbfile = mock_NWBFile()
    add_fiber_photometry_device(nwbfile=nwbfile, device_metadata=device_metadata, device_type=device_type)
    assert len(nwbfile.devices) == 1
    assert device_metadata["name"] in nwbfile.devices
    assert nwbfile.devices[device_metadata["name"]].name == device_metadata["name"]
    assert nwbfile.devices[device_metadata["name"]].description == device_metadata["description"]
    assert nwbfile.devices[device_metadata["name"]].manufacturer == device_metadata["manufacturer"]
    if device_type == "OpticalFiber":
        assert nwbfile.devices[device_metadata["name"]].numerical_aperture == device_metadata["numerical_aperture"]
        assert nwbfile.devices[device_metadata["name"]].core_diameter_in_um == device_metadata["core_diameter_in_um"]
        assert nwbfile.devices[device_metadata["name"]].model == device_metadata["model"]
    elif device_type == "ExcitationSource":
        assert nwbfile.devices[device_metadata["name"]].illumination_type == device_metadata["illumination_type"]
        assert (
            nwbfile.devices[device_metadata["name"]].excitation_wavelength_in_nm
            == device_metadata["excitation_wavelength_in_nm"]
        )
        assert nwbfile.devices[device_metadata["name"]].model == device_metadata["model"]
    elif device_type == "Photodetector":
        assert nwbfile.devices[device_metadata["name"]].detector_type == device_metadata["detector_type"]
        assert (
            nwbfile.devices[device_metadata["name"]].detected_wavelength_in_nm
            == device_metadata["detected_wavelength_in_nm"]
        )
        assert nwbfile.devices[device_metadata["name"]].gain == device_metadata["gain"]
        assert nwbfile.devices[device_metadata["name"]].model == device_metadata["model"]
    elif device_type == "BandOpticalFilter":
        assert (
            nwbfile.devices[device_metadata["name"]].center_wavelength_in_nm
            == device_metadata["center_wavelength_in_nm"]
        )
        assert nwbfile.devices[device_metadata["name"]].bandwidth_in_nm == device_metadata["bandwidth_in_nm"]
        assert nwbfile.devices[device_metadata["name"]].filter_type == device_metadata["filter_type"]
        assert nwbfile.devices[device_metadata["name"]].model == device_metadata["model"]
    elif device_type == "EdgeOpticalFilter":
        assert nwbfile.devices[device_metadata["name"]].cut_wavelength_in_nm == device_metadata["cut_wavelength_in_nm"]
        assert (
            nwbfile.devices[device_metadata["name"]].slope_in_percent_cut_wavelength
            == device_metadata["slope_in_percent_cut_wavelength"]
        )
        assert (
            nwbfile.devices[device_metadata["name"]].slope_starting_transmission_in_percent
            == device_metadata["slope_starting_transmission_in_percent"]
        )
        assert (
            nwbfile.devices[device_metadata["name"]].slope_ending_transmission_in_percent
            == device_metadata["slope_ending_transmission_in_percent"]
        )
        assert nwbfile.devices[device_metadata["name"]].filter_type == device_metadata["filter_type"]
        assert nwbfile.devices[device_metadata["name"]].model == device_metadata["model"]
    elif device_type == "DichroicMirror":
        assert nwbfile.devices[device_metadata["name"]].model == device_metadata["model"]
    elif device_type == "Indicator":
        assert nwbfile.devices[device_metadata["name"]].label == device_metadata["label"]
        assert nwbfile.devices[device_metadata["name"]].injection_location == device_metadata["injection_location"]
        assert (
            nwbfile.devices[device_metadata["name"]].injection_coordinates_in_mm
            == device_metadata["injection_coordinates_in_mm"]
        )
    assert nwbfile.devices[device_metadata["name"]].__class__.__name__ == device_type


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
