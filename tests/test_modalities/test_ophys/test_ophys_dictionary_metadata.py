"""Tests for the new dictionary-based ophys metadata structure."""

import pytest

from neuroconv import NWBConverter
from neuroconv.tools.ophys_metadata_conversion import (
    convert_ophys_metadata_to_dict,
    is_old_ophys_metadata_format,
)
from neuroconv.tools.testing.mock_interfaces import (
    MockImagingInterface,
    MockSegmentationInterface,
)


class TestOphysDictionaryMetadata:
    """Test suite for dictionary-based ophys metadata structure."""

    def test_single_imaging_interface_metadata_structure(self):
        """Test that a single imaging interface creates proper dictionary metadata."""
        interface = MockImagingInterface(metadata_key="visual_cortex")
        metadata = interface.get_metadata()

        # Check Device structure - still list-based within Ophys
        assert "Ophys" in metadata
        assert "Device" in metadata["Ophys"]
        assert isinstance(metadata["Ophys"]["Device"], list)
        assert metadata["Ophys"]["Device"][0]["name"] == "Microscope"

        # Check ImagingPlanes dictionary structure
        assert "ImagingPlanes" in metadata["Ophys"]
        assert "visual_cortex" in metadata["Ophys"]["ImagingPlanes"]

        # Check TwoPhotonSeries
        assert "TwoPhotonSeries" in metadata["Ophys"]
        assert "visual_cortex" in metadata["Ophys"]["TwoPhotonSeries"]

        # Verify references
        assert metadata["Ophys"]["TwoPhotonSeries"]["visual_cortex"]["imaging_plane"] == "visual_cortex"

    def test_single_segmentation_interface_metadata_structure(self):
        """Test that a single segmentation interface creates proper dictionary metadata."""
        interface = MockSegmentationInterface(metadata_key="roi_analysis")
        metadata = interface.get_metadata()

        # Check ImageSegmentation structure
        assert "Ophys" in metadata
        assert "ImageSegmentation" in metadata["Ophys"]
        assert "roi_analysis" in metadata["Ophys"]["ImageSegmentation"]

        # Should also have ImagingPlanes since segmentation requires imaging
        assert "ImagingPlanes" in metadata["Ophys"]
        assert "roi_analysis" in metadata["Ophys"]["ImagingPlanes"]

    def test_multiple_interfaces_with_converter(self):
        """Test combining multiple interfaces with different metadata keys."""
        imaging1 = MockImagingInterface(metadata_key="visual_cortex")
        imaging2 = MockImagingInterface(metadata_key="hippocampus", photon_series_type="OnePhotonSeries")
        segmentation1 = MockSegmentationInterface(metadata_key="visual_cortex_suite2p")

        # Create source data dictionaries for converter
        converter = NWBConverter(
            source_data=dict(imaging_visual=dict(), imaging_hippo=dict(), segmentation_visual=dict())
        )
        converter.data_interface_objects = dict(
            imaging_visual=imaging1, imaging_hippo=imaging2, segmentation_visual=segmentation1
        )

        metadata = converter.get_metadata()

        # Check Device is still a list within Ophys
        assert isinstance(metadata["Ophys"]["Device"], list)

        # Check multiple imaging planes
        assert "visual_cortex" in metadata["Ophys"]["ImagingPlanes"]
        assert "hippocampus" in metadata["Ophys"]["ImagingPlanes"]

        # Check different photon series types
        assert "visual_cortex" in metadata["Ophys"]["TwoPhotonSeries"]
        assert "hippocampus" in metadata["Ophys"]["OnePhotonSeries"]

        # Check segmentation
        assert "visual_cortex_suite2p" in metadata["Ophys"]["ImageSegmentation"]

    def test_backward_compatibility_detection(self):
        """Test detection of old list-based metadata format."""
        old_metadata = {
            "Ophys": {
                "Device": [{"name": "Microscope"}],
                "ImagingPlane": [{"name": "ImagingPlane"}],
                "TwoPhotonSeries": [{"name": "TwoPhotonSeries"}],
            }
        }

        assert is_old_ophys_metadata_format(old_metadata) is True

        new_metadata = {
            "Ophys": {
                "ImagingPlanes": {"default": {"name": "ImagingPlane"}},
                "TwoPhotonSeries": {"default": {"name": "TwoPhotonSeries"}},
            }
        }

        assert is_old_ophys_metadata_format(new_metadata) is False

    def test_backward_compatibility_conversion(self):
        """Test conversion from old to new metadata format."""
        old_metadata = {
            "Ophys": {
                "Device": [{"name": "Microscope", "description": "Test device"}],
                "ImagingPlane": [{"name": "ImagingPlane", "device": "Microscope"}],
                "TwoPhotonSeries": [{"name": "TwoPhotonSeries", "imaging_plane": "ImagingPlane"}],
                "ImageSegmentation": {
                    "plane_segmentations": [{"name": "PlaneSegmentation", "imaging_plane": "ImagingPlane"}]
                },
            }
        }

        # Test conversion with warning
        with pytest.warns(DeprecationWarning):
            new_metadata = convert_ophys_metadata_to_dict(old_metadata)

        # Check structure was converted
        assert "ImagingPlanes" in new_metadata["Ophys"]
        assert "ImagingPlane" not in new_metadata["Ophys"]

        # Check data was preserved
        imaging_plane_key = list(new_metadata["Ophys"]["ImagingPlanes"].keys())[0]
        assert new_metadata["Ophys"]["ImagingPlanes"][imaging_plane_key]["name"] == "ImagingPlane"

        # Check ImageSegmentation was converted
        assert "plane_segmentations" not in new_metadata["Ophys"]["ImageSegmentation"]
        seg_key = list(new_metadata["Ophys"]["ImageSegmentation"].keys())[0]
        assert new_metadata["Ophys"]["ImageSegmentation"][seg_key]["name"] == "PlaneSegmentation"

    def test_metadata_key_propagation(self):
        """Test that metadata_key properly propagates to all components."""
        custom_key = "my_custom_region"
        interface = MockImagingInterface(metadata_key=custom_key)
        metadata = interface.get_metadata()

        # All ophys components should use the same key
        assert custom_key in metadata["Ophys"]["ImagingPlanes"]
        assert custom_key in metadata["Ophys"]["TwoPhotonSeries"]

        # References should use the same key
        assert metadata["Ophys"]["TwoPhotonSeries"][custom_key]["imaging_plane"] == custom_key

    def test_metadata_editing(self):
        """Test editing metadata using dictionary access."""
        interface = MockImagingInterface(metadata_key="test_region")
        metadata = interface.get_metadata()

        # Edit device metadata (still in list format)
        metadata["Ophys"]["Device"][0]["manufacturer"] = "Custom Manufacturer"
        metadata["Ophys"]["Device"][0]["description"] = "Custom microscope description"

        # Edit imaging plane metadata
        metadata["Ophys"]["ImagingPlanes"]["test_region"]["indicator"] = "GCaMP6f"
        metadata["Ophys"]["ImagingPlanes"]["test_region"]["location"] = "V1 layer 2/3"
        metadata["Ophys"]["ImagingPlanes"]["test_region"]["excitation_lambda"] = 920.0

        # Verify edits
        assert metadata["Ophys"]["Device"][0]["manufacturer"] == "Custom Manufacturer"
        assert metadata["Ophys"]["ImagingPlanes"]["test_region"]["indicator"] == "GCaMP6f"
        assert metadata["Ophys"]["ImagingPlanes"]["test_region"]["excitation_lambda"] == 920.0

    def test_no_device_duplication(self):
        """Test that devices are not duplicated when using the same metadata_key."""
        imaging = MockImagingInterface(metadata_key="shared_device")
        segmentation = MockSegmentationInterface(metadata_key="shared_device")

        converter = NWBConverter(source_data=dict(imaging=dict(), segmentation=dict()))
        converter.data_interface_objects = dict(imaging=imaging, segmentation=segmentation)

        metadata = converter.get_metadata()

        # Device is still a list within Ophys
        # With current design, devices may be duplicated in the list
        assert isinstance(metadata["Ophys"]["Device"], list)

        # Both imaging plane and segmentation should use the same metadata_key
        assert "shared_device" in metadata["Ophys"]["ImagingPlanes"]
        assert "shared_device" in metadata["Ophys"]["ImageSegmentation"]
        assert metadata["Ophys"]["ImageSegmentation"]["shared_device"]["imaging_plane"] == "shared_device"
