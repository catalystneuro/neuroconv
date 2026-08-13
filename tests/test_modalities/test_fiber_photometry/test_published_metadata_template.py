"""The metadata template published in the user guide, checked against the method it documents.

``docs/user_guide/metadata_templates/`` holds the structure as files, which the documentation includes
verbatim. They are written by hand rather than generated, because the published block shows a fixed two
of everything while the method sizes itself to the recording. These tests are what keeps the two from
drifting apart, and what backs the claim the page makes: that you can copy a block, fill it in and
convert with it.
"""

import json
from pathlib import Path

import yaml
from pynwb import read_nwb

from neuroconv.tools.testing.mock_interfaces import MockFiberPhotometryInterface

PUBLISHED_TEMPLATES = Path(__file__).parents[3] / "docs" / "user_guide" / "metadata_templates"


def _key_paths(metadata: dict, prefix: tuple = ()) -> set:
    """Every path through a nested dictionary, so two structures compare by shape rather than value."""
    paths = set()
    for key, value in metadata.items():
        paths.add(prefix + (key,))
        if isinstance(value, dict):
            paths |= _key_paths(value, prefix + (key,))
    return paths


def test_published_fiber_photometry_template_matches_the_method():
    # The page promises the two tabs are the same content, and that what it prints is what the method
    # returns. Compared by key path rather than by value: the published block wires the optional links
    # the method leaves blank, on purpose, so the values differ while the structure must not.
    published_yaml = yaml.safe_load((PUBLISHED_TEMPLATES / "fiber_photometry.yaml").read_text())
    published_json = json.loads((PUBLISHED_TEMPLATES / "fiber_photometry.json").read_text())
    assert published_yaml == published_json

    interface = MockFiberPhotometryInterface(num_fibers=2, metadata_key="calcium_signal")
    template = interface.get_metadata_template()
    template.pop("NWBFile")  # Session-level, and not what this block illustrates.

    assert _key_paths(published_yaml) == _key_paths(template)


def test_published_fiber_photometry_template_converts_once_filled(tmp_path):
    # The page's actual promise: copy this, fill in the blanks that apply, delete what does not, convert.
    # The emission filter stands for the half nobody exercises, the delete: a rig without one drops the
    # device and every row that referenced it, and the file then has no emission filter rather than a
    # blank one.
    metadata = yaml.safe_load((PUBLISHED_TEMPLATES / "fiber_photometry.yaml").read_text())
    interface = MockFiberPhotometryInterface(num_fibers=2, metadata_key="calcium_signal")
    metadata["NWBFile"] = interface.get_metadata()["NWBFile"]

    fiber_photometry_metadata = metadata["FiberPhotometry"]
    for location, row_metadata in zip(
        ("DMS", "DLS"), fiber_photometry_metadata["FiberPhotometryTable"]["rows"].values()
    ):
        row_metadata["location"] = location
        row_metadata["excitation_wavelength_in_nm"] = 465.0
        row_metadata["emission_wavelength_in_nm"] = 525.0
        row_metadata["coordinates"] = (3.0, 1.0, 4.0)
        row_metadata["notes"] = f"Fiber in {location}."
        del row_metadata["emission_filter_metadata_key"]
    fiber_photometry_metadata["FiberPhotometryIndicators"]["indicator"].update(name="indicator", label="GCaMP6s")
    fiber_photometry_metadata["calcium_signal"]["description"] = "GCaMP6s at 465 nm in DMS and DLS."

    devices_metadata = metadata["Devices"]
    for device_metadata_key in ("optical_fiber_0", "optical_fiber_1"):
        devices_metadata[device_metadata_key]["fiber_insertion"] = dict(
            insertion_position_ap_in_mm=3.0,
            insertion_position_ml_in_mm=1.0,
            insertion_position_dv_in_mm=4.0,
            depth_in_mm=4.0,
        )
    for device_metadata_key in ("dichroic_mirror", "excitation_filter"):
        devices_metadata[device_metadata_key].pop("device_model_metadata_key")
    del devices_metadata["emission_filter"]

    # The name of every entry is blank, so keeping one costs naming it.
    for device_metadata_key, device_metadata in devices_metadata.items():
        device_metadata["name"] = device_metadata_key
    for model_metadata_key, model_metadata in metadata["DeviceModels"].items():
        model_metadata["name"] = model_metadata_key

    device_models_metadata = metadata["DeviceModels"]
    device_models_metadata["optical_fiber_model"].update(manufacturer="Doric Lenses", numerical_aperture=0.48)
    device_models_metadata["excitation_source_model"].update(
        manufacturer="Doric Lenses", source_type="LED", excitation_mode="one-photon"
    )
    device_models_metadata["photodetector_model"].update(manufacturer="Doric Lenses", detector_type="photodiode")

    nwbfile_path = tmp_path / "published_template.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

    read_nwbfile = read_nwb(nwbfile_path)

    # The blank emission filter wrote nothing, rather than a device named after an absent key.
    assert "emission_filter" not in read_nwbfile.devices
    assert "excitation_filter" in read_nwbfile.devices

    table = read_nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table
    assert list(table["location"][:]) == ["DMS", "DLS"]
    assert [fiber.name for fiber in table["optical_fiber"][:]] == ["optical_fiber_0", "optical_fiber_1"]
    assert read_nwbfile.acquisition["FiberPhotometryResponseSeries"].data.shape == (100, 2)
