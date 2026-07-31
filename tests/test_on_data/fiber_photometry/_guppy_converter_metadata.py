"""The user-supplied ``FiberPhotometry`` provenance chain, shared by the GuPPy converter tests.

No interface fabricates this chain -- every fiber photometry conversion requires the caller to
supply it -- so each converter test has to build one. These builders are parameterized by recording
site, which is the only thing that differs between the Doric and NPM fixtures.
"""


def build_device_metadata(recording_sites):
    """The Devices/DeviceModels chain, with one optical fiber per recording site."""
    devices = {
        "excitation_source_signal": {
            "type": "ExcitationSource",
            "name": "excitation_source_signal",
            "device_model_metadata_key": "excitation_source_model",
        },
        "excitation_source_control": {
            "type": "ExcitationSource",
            "name": "excitation_source_control",
            "device_model_metadata_key": "excitation_source_model",
        },
        "photodetector": {
            "type": "Photodetector",
            "name": "photodetector",
            "device_model_metadata_key": "photodetector_model",
        },
    }
    for recording_site in recording_sites:
        devices[f"optical_fiber_{recording_site}"] = {
            "type": "OpticalFiber",
            "name": f"optical_fiber_{recording_site}",
            "device_model_metadata_key": "optical_fiber_model",
            "fiber_insertion": {"depth_in_mm": 2.8},
        }
    return {
        "DeviceModels": {
            "optical_fiber_model": {
                "type": "OpticalFiberModel",
                "name": "optical_fiber_model",
                "manufacturer": "Doric Lenses",
                "numerical_aperture": 0.48,
            },
            "excitation_source_model": {
                "type": "ExcitationSourceModel",
                "name": "excitation_source_model",
                "manufacturer": "Doric Lenses",
                "source_type": "LED",
                "excitation_mode": "one-photon",
            },
            "photodetector_model": {
                "type": "PhotodetectorModel",
                "name": "photodetector_model",
                "manufacturer": "Doric Lenses",
                "detector_type": "photodiode",
            },
        },
        "Devices": devices,
    }


def build_fiber_photometry_metadata(recording_sites):
    """One FiberPhotometryTable row per store, ordered signal-then-control within each site."""
    rows = {}
    for recording_site in recording_sites:
        for role, wavelength in (("signal", 465.0), ("control", 405.0)):
            rows[f"{recording_site}_{role}"] = {
                "location": recording_site.upper(),
                "excitation_wavelength_in_nm": wavelength,
                "emission_wavelength_in_nm": 525.0,
                "indicator_metadata_key": "gcamp",
                "optical_fiber_metadata_key": f"optical_fiber_{recording_site}",
                "excitation_source_metadata_key": f"excitation_source_{role}",
                "photodetector_metadata_key": "photodetector",
            }
    return {
        "FiberPhotometryIndicators": {
            "gcamp": {"name": "gcamp", "label": "GCaMP7b", "description": "GCaMP7b calcium indicator."},
        },
        "FiberPhotometryTable": {
            "name": "fiber_photometry_table",
            "description": "Doric fiber photometry setup.",
            "rows": rows,
        },
    }


def build_series_metadata(recording_sites):
    """Each role series names one table row per stacked column, in recording-site order."""
    return {
        role: {
            "fiber_photometry_table_region": [f"{recording_site}_{role}" for recording_site in recording_sites],
            "fiber_photometry_table_region_description": f"The {role} fibers.",
        }
        for role in ("signal", "control")
    }
