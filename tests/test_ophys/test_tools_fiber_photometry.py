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
