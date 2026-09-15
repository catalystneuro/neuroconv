"""The metadata templates published in the user guide, checked against the methods they document.

``docs/user_guide/metadata_templates/`` holds the structures as files, which the documentation includes
verbatim. They are written by hand rather than generated, because the published block shows a fixed set
of everything while the methods size themselves to the recording. These tests are what keeps the two
from drifting apart, and what backs the claim the page makes: that you can copy a block, fill it in and
convert with it.
"""

import json
from pathlib import Path

import yaml
from pynwb import read_nwb

from neuroconv.tools.testing.mock_interfaces import (
    MockImagingInterface,
    MockSegmentationInterface,
)

PUBLISHED_TEMPLATES = Path(__file__).parents[3] / "docs" / "user_guide" / "metadata_templates"


def _key_paths(metadata: dict, prefix: tuple = ()) -> set:
    """Every path through a nested dictionary, so two structures compare by shape rather than value."""
    paths = set()
    for key, value in metadata.items():
        paths.add(prefix + (key,))
        if isinstance(value, dict):
            paths |= _key_paths(value, prefix + (key,))
    return paths


def _fill_imaging_plane(imaging_plane_metadata: dict) -> None:
    """Answer every blank of the published imaging plane, which both blocks carry."""
    imaging_plane_metadata.update(
        name="ImagingPlane",
        description="Imaging plane in V1.",
        excitation_lambda=920.0,
        indicator="GCaMP6s",
        location="V1",
        imaging_rate=30.0,
        origin_coords=[0.0, 0.0],
        grid_spacing=[1e-5, 1e-5],
        reference_frame="Bregma at the cortical surface.",
    )
    # The published block shows two channels where the method returns one, since this is where the
    # structure repeats. A recording imaged in one channel deletes the second.
    del imaging_plane_metadata["optical_channel"][1]
    imaging_plane_metadata["optical_channel"][0].update(
        name="Green", description="GCaMP emission.", emission_lambda=510.0
    )


def test_published_ophys_imaging_template_matches_the_method():
    # The page promises the two tabs are the same content, and that what it prints is what the method
    # returns. Compared by key path rather than by value, since the published block wires the links the
    # method resolves from the interface, so the values differ while the structure must not.
    published_yaml = yaml.safe_load((PUBLISHED_TEMPLATES / "ophys_imaging.yaml").read_text())
    published_json = json.loads((PUBLISHED_TEMPLATES / "ophys_imaging.json").read_text())
    assert published_yaml == published_json

    interface = MockImagingInterface(metadata_key="calcium_imaging")
    template = interface.get_metadata_template()
    template.pop("NWBFile")  # Session-level, and not what this block illustrates.

    assert _key_paths(published_yaml) == _key_paths(template)


def test_published_ophys_segmentation_template_matches_the_method():
    published_yaml = yaml.safe_load((PUBLISHED_TEMPLATES / "ophys_segmentation.yaml").read_text())
    published_json = json.loads((PUBLISHED_TEMPLATES / "ophys_segmentation.json").read_text())
    assert published_yaml == published_json

    interface = MockSegmentationInterface(metadata_key="calcium_segmentation")
    template = interface.get_metadata_template()
    template.pop("NWBFile")

    assert _key_paths(published_yaml) == _key_paths(template)


def test_published_ophys_imaging_template_converts_once_filled(tmp_path):
    # The page's actual promise: copy this, fill in the blanks that apply, delete what does not, convert.
    # The scanner fields stand for the half nobody exercises, the delete: a recording that did not record
    # them writes a series without them rather than one carrying blanks.
    metadata = yaml.safe_load((PUBLISHED_TEMPLATES / "ophys_imaging.yaml").read_text())
    interface = MockImagingInterface(metadata_key="calcium_imaging")
    metadata["NWBFile"] = interface.get_metadata()["NWBFile"]

    metadata["DeviceModels"]["microscope_model"].update(
        name="MicroscopeModel",
        manufacturer="Bruker",
        model_number="Ultima IV",
        description="Two-photon microscope.",
    )
    metadata["Devices"]["microscope"].update(
        name="Microscope", description="The lab's two-photon microscope.", serial_number="1234"
    )
    _fill_imaging_plane(metadata["Ophys"]["ImagingPlanes"]["calcium_imaging"])

    microscopy_series_metadata = metadata["Ophys"]["MicroscopySeries"]["calcium_imaging"]
    microscopy_series_metadata.update(name="TwoPhotonSeries", description="Calcium imaging in V1.", unit="n.a.")
    for unrecorded_field in ("field_of_view", "pmt_gain", "scan_line_rate"):
        del microscopy_series_metadata[unrecorded_field]

    nwbfile_path = tmp_path / "published_imaging_template.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

    read_nwbfile = read_nwb(nwbfile_path)
    two_photon_series = read_nwbfile.acquisition["TwoPhotonSeries"]
    assert two_photon_series.scan_line_rate is None
    assert two_photon_series.imaging_plane.indicator == "GCaMP6s"
    assert two_photon_series.imaging_plane.device.name == "Microscope"
    assert [channel.name for channel in two_photon_series.imaging_plane.optical_channel] == ["Green"]


def test_published_ophys_segmentation_template_converts_once_filled(tmp_path):
    # As above, with the delete that matters here: a pipeline that produced no df/F drops the entry
    # rather than naming a trace the file does not hold.
    metadata = yaml.safe_load((PUBLISHED_TEMPLATES / "ophys_segmentation.yaml").read_text())
    interface = MockSegmentationInterface(metadata_key="calcium_segmentation", has_dff_signal=False)
    metadata["NWBFile"] = interface.get_metadata()["NWBFile"]

    metadata["DeviceModels"]["microscope_model"].update(
        name="MicroscopeModel",
        manufacturer="Bruker",
        model_number="Ultima IV",
        description="Two-photon microscope.",
    )
    metadata["Devices"]["microscope"].update(
        name="Microscope", description="The lab's two-photon microscope.", serial_number="1234"
    )
    _fill_imaging_plane(metadata["Ophys"]["ImagingPlanes"]["calcium_segmentation"])
    metadata["Ophys"]["PlaneSegmentations"]["calcium_segmentation"].update(
        name="PlaneSegmentation", description="ROIs detected by the pipeline."
    )

    roi_responses_metadata = metadata["Ophys"]["RoiResponses"]["calcium_segmentation"]
    del roi_responses_metadata["dff"]
    for trace_name, trace_metadata in roi_responses_metadata.items():
        trace_metadata.update(name=trace_name.capitalize(), description=f"{trace_name} traces.", unit="n.a.")
    for image_name, image_metadata in metadata["Ophys"]["SegmentationImages"]["calcium_segmentation"].items():
        image_metadata.update(name=f"{image_name}_image", description=f"{image_name} image.")

    nwbfile_path = tmp_path / "published_segmentation_template.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

    read_nwbfile = read_nwb(nwbfile_path)
    ophys_module = read_nwbfile.processing["ophys"]
    assert set(ophys_module["Fluorescence"].roi_response_series) == {"Raw", "Neuropil", "Deconvolved"}
    assert set(ophys_module["SegmentationImages"].images) == {"mean_image", "correlation_image"}
    plane_segmentation = ophys_module["ImageSegmentation"].plane_segmentations["PlaneSegmentation"]
    assert plane_segmentation.imaging_plane.device.name == "Microscope"
