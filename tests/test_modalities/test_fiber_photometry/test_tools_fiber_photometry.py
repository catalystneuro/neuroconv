from neuroconv.tools.fiber_photometry import add_fiber_photometry_device
import re
from pynwb.testing.mock.file import mock_NWBFile
import pytest

from neuroconv.tools.fiber_photometry import add_ophys_device, add_ophys_device_model


@pytest.mark.parametrize(
    "device_type, device_metadata",
    [
        (
            "OpticalFiberModel",
            {
                "name": "optical_fiber_model",
                "description": "Fiber optic implant model specifications from Doric Lenses.",
                "manufacturer": "Doric Lenses",
                "model_number": "Fiber Optic Implant",
                "numerical_aperture": 0.48,
                "core_diameter_in_um": 400.0,
            },
        ),
        (
            "ExcitationSourceModel",
            {
                "name": "excitation_source_model",
                "description": "Connectorized LED model specifications from Doric Lenses.",
                "manufacturer": "Doric Lenses",
                "model_number": "Connectorized LED",
                "source_type": "LED",
                "excitation_mode": "one-photon",
                "wavelength_range_in_nm": [400.0, 470.0],
            },
        ),
        (
            "PhotodetectorModel",
            {
                "name": "photodetector_model",
                "description": "Newport Visible Femtowatt Photoreceiver Module specifications.",
                "manufacturer": "Doric Lenses",
                "model_number": "Newport Visible Femtowatt Photoreceiver Module",
                "detector_type": "photodiode",
                "wavelength_range_in_nm": [400.0, 700.0],
                "gain": 1.0e10,
                "gain_unit": "V/W",
            },
        ),
        (
            "BandOpticalFilterModel",
            {
                "name": "emission_filter_model",
                "description": "Emission bandpass filter model for GCaMP fluorescence detection.",
                "manufacturer": "Doric Lenses",
                "model_number": "4 ports Fluorescence Mini Cube - GCaMP Emission Filter",
                "filter_type": "Bandpass",
                "center_wavelength_in_nm": 525.0,
                "bandwidth_in_nm": 50.0,
            },
        ),
        (
            "EdgeOpticalFilterModel",
            {
                "name": "excitation_filter_model",
                "description": "Excitation longpass filter model for 465nm light.",
                "manufacturer": "Doric Lenses",
                "model_number": "4 ports Fluorescence Mini Cube - GCaMP Excitation Filter",
                "filter_type": "Longpass",
                "cut_wavelength_in_nm": 475.0,
                "slope_in_percent_cut_wavelength": 1.0,
                "slope_starting_transmission_in_percent": 10.0,
                "slope_ending_transmission_in_percent": 80.0,
            },
        ),
        (
            "DichroicMirrorModel",
            {
                "name": "dichroic_mirror_model",
                "description": "Dichroic mirror model specifications from Doric Lenses.",
                "manufacturer": "Doric Lenses",
                "model_number": "4 ports Fluorescence Mini Cube - GCaMP",
                "cut_on_wavelength_in_nm": 495.0,
                "reflection_band_in_nm": [400.0, 495.0],
                "transmission_band_in_nm": [505.0, 700.0],
                "angle_of_incidence_in_degrees": 45.0,
            },
        ),
    ],
)
def test_add_ophys_device_model(device_type, device_metadata):
    nwbfile = mock_NWBFile()
    add_ophys_device_model(nwbfile=nwbfile, device_metadata=device_metadata, device_type=device_type)
    assert len(nwbfile.devices) == 1
    assert device_metadata["name"] in nwbfile.devices
    device_model = nwbfile.devices[device_metadata["name"]]
    assert device_model.name == device_metadata["name"]
    assert device_model.description == device_metadata["description"]
    assert device_model.manufacturer == device_metadata["manufacturer"]
    assert device_model.model_number == device_metadata["model_number"]

    if device_type == "OpticalFiberModel":
        assert device_model.numerical_aperture == device_metadata["numerical_aperture"]
        assert device_model.core_diameter_in_um == device_metadata["core_diameter_in_um"]
    elif device_type == "ExcitationSourceModel":
        assert device_model.source_type == device_metadata["source_type"]
        assert device_model.excitation_mode == device_metadata["excitation_mode"]
        assert device_model.wavelength_range_in_nm == device_metadata["wavelength_range_in_nm"]
    elif device_type == "PhotodetectorModel":
        assert device_model.detector_type == device_metadata["detector_type"]
        assert device_model.wavelength_range_in_nm == device_metadata["wavelength_range_in_nm"]
        assert device_model.gain == device_metadata["gain"]
        assert device_model.gain_unit == device_metadata["gain_unit"]
    elif device_type == "BandOpticalFilterModel":
        assert device_model.filter_type == device_metadata["filter_type"]
        assert device_model.center_wavelength_in_nm == device_metadata["center_wavelength_in_nm"]
        assert device_model.bandwidth_in_nm == device_metadata["bandwidth_in_nm"]
    elif device_type == "EdgeOpticalFilterModel":
        assert device_model.filter_type == device_metadata["filter_type"]
        assert device_model.cut_wavelength_in_nm == device_metadata["cut_wavelength_in_nm"]
        assert device_model.slope_in_percent_cut_wavelength == device_metadata["slope_in_percent_cut_wavelength"]
        assert (
            device_model.slope_starting_transmission_in_percent
            == device_metadata["slope_starting_transmission_in_percent"]
        )
        assert (
            device_model.slope_ending_transmission_in_percent == device_metadata["slope_ending_transmission_in_percent"]
        )
    elif device_type == "DichroicMirrorModel":
        assert device_model.cut_on_wavelength_in_nm == device_metadata["cut_on_wavelength_in_nm"]
        assert device_model.reflection_band_in_nm == device_metadata["reflection_band_in_nm"]
        assert device_model.transmission_band_in_nm == device_metadata["transmission_band_in_nm"]
        assert device_model.angle_of_incidence_in_degrees == device_metadata["angle_of_incidence_in_degrees"]

    assert device_model.__class__.__name__ == device_type


@pytest.mark.parametrize(
    "device_type, device_metadata",
    [
        (
            "ExcitationSource",
            {
                "name": "excitation_source",
                "description": "465nm LED for calcium signal excitation.",
                "model": "excitation_source_model",
                "power_in_W": 0.001,
                "intensity_in_W_per_m2": 0.005,
                "exposure_time_in_s": 2.51e-13,
            },
        ),
        (
            "Photodetector",
            {
                "name": "photodetector",
                "description": "High-gain photoreceiver for fluorescence detection.",
                "model": "photodetector_model",
                "serial_number": "PD001",
            },
        ),
        (
            "BandOpticalFilter",
            {
                "name": "emission_filter",
                "description": "Bandpass filter for GCaMP emission detection.",
                "model": "emission_filter_model",
            },
        ),
        (
            "EdgeOpticalFilter",
            {
                "name": "excitation_filter",
                "description": "Longpass filter for excitation light.",
                "model": "excitation_filter_model",
            },
        ),
        (
            "DichroicMirror",
            {
                "name": "dichroic_mirror",
                "description": "Dichroic mirror for separating excitation and emission light.",
                "model": "dichroic_mirror_model",
                "serial_number": "DM001",
            },
        ),
    ],
)
def test_add_ophys_device(device_type, device_metadata):
    nwbfile = mock_NWBFile()

    # First add the device model that this device references
    model_metadata = {
        "name": device_metadata["model"],
        "description": f"Model for {device_metadata['name']}",
        "manufacturer": "Test Manufacturer",
        "model_number": "Test Model",
    }

    # Add type-specific model metadata
    if device_type == "ExcitationSource":
        model_metadata.update(
            {
                "source_type": "LED",
                "excitation_mode": "one-photon",
                "wavelength_range_in_nm": [400.0, 470.0],
            }
        )
        model_type = "ExcitationSourceModel"
    elif device_type == "Photodetector":
        model_metadata.update(
            {
                "detector_type": "photodiode",
                "wavelength_range_in_nm": [400.0, 700.0],
                "gain": 1.0e10,
                "gain_unit": "V/W",
            }
        )
        model_type = "PhotodetectorModel"
    elif device_type == "BandOpticalFilter":
        model_metadata.update(
            {
                "filter_type": "Bandpass",
                "center_wavelength_in_nm": 525.0,
                "bandwidth_in_nm": 50.0,
            }
        )
        model_type = "BandOpticalFilterModel"
    elif device_type == "EdgeOpticalFilter":
        model_metadata.update(
            {
                "filter_type": "Longpass",
                "cut_wavelength_in_nm": 475.0,
                "slope_in_percent_cut_wavelength": 1.0,
                "slope_starting_transmission_in_percent": 10.0,
                "slope_ending_transmission_in_percent": 80.0,
            }
        )
        model_type = "EdgeOpticalFilterModel"
    elif device_type == "DichroicMirror":
        model_metadata.update(
            {
                "cut_on_wavelength_in_nm": 495.0,
                "reflection_band_in_nm": [400.0, 495.0],
                "transmission_band_in_nm": [505.0, 700.0],
                "angle_of_incidence_in_degrees": 45.0,
            }
        )
        model_type = "DichroicMirrorModel"

    # Add the model first
    add_ophys_device_model(nwbfile=nwbfile, device_metadata=model_metadata, device_type=model_type)

    # Now add the device instance
    add_ophys_device(nwbfile=nwbfile, device_metadata=device_metadata, device_type=device_type)

    assert len(nwbfile.devices) == 2  # Model + device instance
    assert device_metadata["name"] in nwbfile.devices
    device = nwbfile.devices[device_metadata["name"]]
    assert device.name == device_metadata["name"]
    assert device.description == device_metadata["description"]

    # Check that the device references the correct model
    assert device.model is nwbfile.devices[device_metadata["model"]]

    # Check device-specific attributes
    if device_type == "ExcitationSource":
        assert device.power_in_W == device_metadata["power_in_W"]
        assert device.intensity_in_W_per_m2 == device_metadata["intensity_in_W_per_m2"]
        assert device.exposure_time_in_s == device_metadata["exposure_time_in_s"]
    elif device_type == "Photodetector":
        assert device.serial_number == device_metadata["serial_number"]
    elif device_type == "DichroicMirror":
        assert device.serial_number == device_metadata["serial_number"]

    assert device.__class__.__name__ == device_type


def test_add_ophys_device_model_invalid_device_type():
    nwbfile = mock_NWBFile()
    valid_device_types = [
        "OpticalFiberModel",
        "ExcitationSourceModel",
        "PhotodetectorModel",
        "BandOpticalFilterModel",
        "EdgeOpticalFilterModel",
        "DichroicMirrorModel",
    ]
    with pytest.raises(AssertionError, match=re.escape(f"device_type must be one of {valid_device_types}")):
        add_ophys_device_model(
            nwbfile=nwbfile,
            device_metadata={},
            device_type="invalid_device_type",
        )


def test_add_ophys_device_invalid_device_type():
    nwbfile = mock_NWBFile()
    valid_device_types = [
        "ExcitationSource",
        "Photodetector",
        "BandOpticalFilter",
        "EdgeOpticalFilter",
        "DichroicMirror",
    ]
    with pytest.raises(AssertionError, match=re.escape(f"device_type must be one of {valid_device_types}")):
        add_ophys_device(
            nwbfile=nwbfile,
            device_metadata={},
            device_type="invalid_device_type",
        )


def test_add_ophys_device_model_twice():
    nwbfile = mock_NWBFile()
    device_metadata = {
        "name": "optical_fiber_model",
        "description": "Fiber optic implant model specifications from Doric Lenses.",
        "manufacturer": "Doric Lenses",
        "model_number": "Fiber Optic Implant",
        "numerical_aperture": 0.48,
        "core_diameter_in_um": 400.0,
    }
    add_ophys_device_model(nwbfile=nwbfile, device_metadata=device_metadata, device_type="OpticalFiberModel")
    add_ophys_device_model(nwbfile=nwbfile, device_metadata=device_metadata, device_type="OpticalFiberModel")
    assert len(nwbfile.devices) == 1
    assert "optical_fiber_model" in nwbfile.devices
    device_model = nwbfile.devices["optical_fiber_model"]
    assert device_model.name == "optical_fiber_model"
    assert device_model.description == "Fiber optic implant model specifications from Doric Lenses."
    assert device_model.manufacturer == "Doric Lenses"
    assert device_model.model_number == "Fiber Optic Implant"
    assert device_model.numerical_aperture == 0.48
    assert device_model.core_diameter_in_um == 400.0
    assert device_model.__class__.__name__ == "OpticalFiberModel"


def test_add_ophys_device_twice():
    nwbfile = mock_NWBFile()

    # Add model first
    model_metadata = {
        "name": "excitation_source_model",
        "description": "Test model",
        "manufacturer": "Test Manufacturer",
        "model_number": "Test Model",
        "source_type": "LED",
        "excitation_mode": "one-photon",
        "wavelength_range_in_nm": [400.0, 470.0],
    }
    add_ophys_device_model(nwbfile=nwbfile, device_metadata=model_metadata, device_type="ExcitationSourceModel")

    # Add device twice
    device_metadata = {
        "name": "excitation_source",
        "description": "465nm LED for calcium signal excitation.",
        "model": "excitation_source_model",
        "power_in_W": 0.001,
        "intensity_in_W_per_m2": 0.005,
        "exposure_time_in_s": 2.51e-13,
    }
    add_ophys_device(nwbfile=nwbfile, device_metadata=device_metadata, device_type="ExcitationSource")
    add_ophys_device(nwbfile=nwbfile, device_metadata=device_metadata, device_type="ExcitationSource")

    assert len(nwbfile.devices) == 2  # Model + device instance
    assert "excitation_source" in nwbfile.devices
    device = nwbfile.devices["excitation_source"]
    assert device.name == "excitation_source"
    assert device.description == "465nm LED for calcium signal excitation."
    assert device.model is nwbfile.devices["excitation_source_model"]
    assert device.power_in_W == 0.001
    assert device.intensity_in_W_per_m2 == 0.005
    assert device.exposure_time_in_s == 2.51e-13
    assert device.__class__.__name__ == "ExcitationSource"
