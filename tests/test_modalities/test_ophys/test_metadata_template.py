"""``get_metadata_template()`` on the two ophys bases, checked against what it claims to adapt to."""

import pytest
from pynwb import read_nwb

from neuroconv.tools.testing.mock_interfaces import (
    MockImagingInterface,
    MockSegmentationInterface,
)
from neuroconv.utils import DeepDict


def _fill_microscope(metadata: dict) -> None:
    """Answer every blank of the microscope and its model, so a test can get past them."""
    metadata["DeviceModels"]["microscope_model"].update(
        name="MicroscopeModel",
        manufacturer="Bruker",
        model_number="Ultima IV",
        description="Two-photon microscope.",
    )
    metadata["Devices"]["microscope"].update(
        name="Microscope", description="The lab's two-photon microscope.", serial_number="1234"
    )


def _fill_imaging_plane(imaging_plane_metadata: dict) -> None:
    """Answer every blank of an imaging plane, so a test can get past it to what it is about."""
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
    imaging_plane_metadata["optical_channel"][0].update(
        name="Green", description="GCaMP emission.", emission_lambda=510.0
    )


class TestImagingMetadataTemplate:
    def test_the_chain_is_wired(self):
        # The tedious part to reconstruct by hand, and the part a user cannot check by reading it back:
        # every cross-reference has to resolve to an entry that is actually in the template.
        interface = MockImagingInterface(metadata_key="visual_cortex")

        template = interface.get_metadata_template()

        imaging_plane_metadata = template["Ophys"]["ImagingPlanes"]["visual_cortex"]
        series_metadata = template["Ophys"]["MicroscopySeries"]["visual_cortex"]
        assert series_metadata["imaging_plane_metadata_key"] in template["Ophys"]["ImagingPlanes"]
        assert imaging_plane_metadata["device_metadata_key"] in template["Devices"]
        device_metadata = template["Devices"][imaging_plane_metadata["device_metadata_key"]]
        assert device_metadata["device_model_metadata_key"] in template["DeviceModels"]

    def test_blanks_only_what_the_source_cannot_answer(self):
        # The blanks are the checklist, so whatever the source does know has to survive into the template
        # instead of being blanked along with the rest.
        interface = MockImagingInterface(metadata_key="visual_cortex")

        template = interface.get_metadata_template()

        assert template["Ophys"]["MicroscopySeries"]["visual_cortex"]["name"] == "MicroscopySeries"
        assert (
            template["Ophys"]["MicroscopySeries"]["visual_cortex"]["description"] == "Imaging data from mock generator."
        )
        imaging_plane_metadata = template["Ophys"]["ImagingPlanes"]["visual_cortex"]
        assert imaging_plane_metadata["excitation_lambda"] is None
        assert imaging_plane_metadata["indicator"] is None
        assert imaging_plane_metadata["location"] is None
        assert imaging_plane_metadata["optical_channel"][0]["emission_lambda"] is None
        assert template["Devices"]["microscope"]["name"] is None

    def test_the_device_is_the_one_the_interface_already_names(self):
        # An interface that read its microscope out of the source names it, and the template has to fill
        # that entry's blanks. A second, invented entry would be linked to by nothing, and the ophys
        # writer drops a device nothing links to, so the user would be filling in a device that never
        # reaches the file.
        class MicroscopeNamingImagingInterface(MockImagingInterface):
            def get_metadata(self, *, use_new_metadata_format: bool = False) -> DeepDict:
                metadata = super().get_metadata(use_new_metadata_format=use_new_metadata_format)
                if use_new_metadata_format:
                    metadata["Devices"] = {"scan_image_microscope": dict(name="Microscope")}
                    metadata["Ophys"] = dict(
                        metadata["Ophys"],
                        ImagingPlanes={self.metadata_key: dict(device_metadata_key="scan_image_microscope")},
                    )
                return metadata

        interface = MicroscopeNamingImagingInterface(metadata_key="visual_cortex")

        template = interface.get_metadata_template()

        assert list(template["Devices"]) == ["scan_image_microscope"]
        assert template["Devices"]["scan_image_microscope"]["name"] == "Microscope"
        assert template["Devices"]["scan_image_microscope"]["serial_number"] is None
        assert template["Ophys"]["ImagingPlanes"]["visual_cortex"]["device_metadata_key"] == "scan_image_microscope"
        assert list(template["DeviceModels"]) == ["scan_image_microscope_model"]

    @pytest.mark.parametrize(
        "photon_series_type, expected_fields",
        [
            ("TwoPhotonSeries", {"field_of_view", "pmt_gain", "scan_line_rate"}),
            ("OnePhotonSeries", {"exposure_time", "binning", "power", "intensity"}),
        ],
    )
    def test_the_optional_series_fields_follow_the_photon_series_type(self, photon_series_type, expected_fields):
        # A template is a discovery aid, and the fields worth discovering differ: a one-photon
        # acquisition describes its camera exposure where a two-photon one describes its scanner.
        interface = MockImagingInterface(metadata_key="visual_cortex", photon_series_type=photon_series_type)

        template = interface.get_metadata_template()

        series_metadata = template["Ophys"]["MicroscopySeries"]["visual_cortex"]
        assert expected_fields <= set(series_metadata)

    def test_the_template_as_it_comes_is_refused(self):
        # The other half of what a blank is for: an entry whose fields are all satisfied is written as
        # stated, so an unfilled template has to fail rather than write the blanks it offered.
        interface = MockImagingInterface(metadata_key="visual_cortex")

        with pytest.raises(Exception):
            interface.create_nwbfile(metadata=interface.get_metadata_template())

    def test_filled_template_round_trips(self, tmp_path):
        # The template's actual promise: fill in the blanks that apply, delete the ones that do not, and
        # convert, with nothing left to add.
        interface = MockImagingInterface(metadata_key="visual_cortex")
        metadata = interface.get_metadata_template()

        _fill_microscope(metadata)
        _fill_imaging_plane(metadata["Ophys"]["ImagingPlanes"]["visual_cortex"])
        metadata["Ophys"]["MicroscopySeries"]["visual_cortex"].update(
            unit="n.a.", field_of_view=[1e-4, 1e-4], pmt_gain=1.0, scan_line_rate=1000.0
        )

        nwbfile_path = tmp_path / "filled_imaging_template.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        read_nwbfile = read_nwb(nwbfile_path)
        assert "Microscope" in read_nwbfile.devices
        imaging_plane = read_nwbfile.imaging_planes["ImagingPlane"]
        assert imaging_plane.indicator == "GCaMP6s"
        assert imaging_plane.device.name == "Microscope"
        assert read_nwbfile.acquisition["MicroscopySeries"].imaging_plane is imaging_plane


class TestSegmentationMetadataTemplate:
    def test_sized_to_the_traces_and_images_the_pipeline_produced(self):
        # Naming a trace the extractor does not hold writes nothing and warns, so an entry for it is a
        # blank nobody can fill. The template is measured off the data for the same reason the fiber
        # photometry one is: a fixed list would be wrong for every pipeline but the one it was written for.
        interface = MockSegmentationInterface(metadata_key="suite2p", has_dff_signal=False, has_summary_images=False)

        template = interface.get_metadata_template()

        assert set(template["Ophys"]["RoiResponses"]["suite2p"]) == {"raw", "neuropil", "deconvolved"}
        assert "SegmentationImages" not in template["Ophys"]

    def test_the_chain_is_wired(self):
        interface = MockSegmentationInterface(metadata_key="suite2p")

        template = interface.get_metadata_template()

        plane_segmentation_metadata = template["Ophys"]["PlaneSegmentations"]["suite2p"]
        assert plane_segmentation_metadata["imaging_plane_metadata_key"] in template["Ophys"]["ImagingPlanes"]
        assert template["Ophys"]["ImagingPlanes"]["suite2p"]["device_metadata_key"] in template["Devices"]

        # The writer resolves the segmentation, its traces and its images through the one key, so the
        # template has to key all three the same way or the entries it hands back are never read.
        assert "suite2p" in template["Ophys"]["RoiResponses"]
        assert "suite2p" in template["Ophys"]["SegmentationImages"]

    def test_the_template_as_it_comes_is_refused(self):
        interface = MockSegmentationInterface(metadata_key="suite2p")

        with pytest.raises(Exception):
            interface.create_nwbfile(metadata=interface.get_metadata_template())

    def test_filled_template_round_trips(self, tmp_path):
        interface = MockSegmentationInterface(metadata_key="suite2p")
        metadata = interface.get_metadata_template()

        _fill_microscope(metadata)
        _fill_imaging_plane(metadata["Ophys"]["ImagingPlanes"]["suite2p"])
        metadata["Ophys"]["PlaneSegmentations"]["suite2p"].update(
            name="PlaneSegmentationSuite2p", description="ROIs detected by Suite2p."
        )
        for trace_name, trace_metadata in metadata["Ophys"]["RoiResponses"]["suite2p"].items():
            trace_metadata.update(
                name=trace_name.capitalize(), description=f"Suite2p {trace_name} traces.", unit="n.a."
            )
        for image_name, image_metadata in metadata["Ophys"]["SegmentationImages"]["suite2p"].items():
            image_metadata.update(name=f"{image_name}_image", description=f"Suite2p {image_name} image.")

        nwbfile_path = tmp_path / "filled_segmentation_template.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        read_nwbfile = read_nwb(nwbfile_path)
        ophys_module = read_nwbfile.processing["ophys"]
        plane_segmentation = ophys_module["ImageSegmentation"].plane_segmentations["PlaneSegmentationSuite2p"]
        assert plane_segmentation.imaging_plane.indicator == "GCaMP6s"
        assert set(ophys_module["Fluorescence"].roi_response_series) == {
            "Raw",
            "Dff",
            "Neuropil",
            "Deconvolved",
        }
        assert set(ophys_module["SegmentationImages"].images) == {"mean_image", "correlation_image"}
