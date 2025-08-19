"""Tests for the new dictionary-based ophys metadata structure."""

import math

from neuroconv import ConverterPipe
from neuroconv.tools.testing.mock_interfaces import (
    MockImagingInterface,
    MockSegmentationInterface,
)


def remove_nan_for_comparison(data):
    """
    Recursively remove NaN values from a dictionary structure for comparison.

    The ophys metadata has things like emission and excitation lambda that can be NaN.
    We have defaults of Nan for those and therefore we need to remove before comparing
    the dictionary of values.

    NaN values cannot be compared in Python since NaN != NaN is always True.
    This function removes all NaN values from nested dictionaries and lists
    so that metadata structures can be compared for equality in tests.

    Parameters
    ----------
    data : dict, list, or any
        The data structure to clean of NaN values

    Returns
    -------
    dict, list, or any
        The same structure with NaN values removed
    """
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            if isinstance(value, float) and math.isnan(value):
                continue  # Skip NaN values
            else:
                cleaned[key] = remove_nan_for_comparison(value)
        return cleaned
    elif isinstance(data, list):
        return [remove_nan_for_comparison(item) for item in data]
    else:
        return data


class TestOphysInterfacesGetMetadata:
    """Test suite for ophys interfaces get_metadata() methods with dictionary structure."""

    def test_single_imaging_interface_metadata_structure(self):
        """Test that a single imaging interface creates proper dictionary metadata."""
        metadata_key = "interface_metadata_key"
        interface = MockImagingInterface(metadata_key=metadata_key)
        metadata = interface.get_metadata()

        # Expected structure for ImagingPlanes (NaN values of excitation/emission lambda excluded for comparison)
        expected_imaging_planes = {
            "default_imaging_plane_metadata_key": {
                "name": "ImagingPlane",
                "description": "The plane or volume being imaged by the microscope.",
                "indicator": "unknown",
                "location": "unknown",
                "device": "Microscope",
                "optical_channel": [{"name": "channel_num_0", "description": "An optical channel of the microscope."}],
            }
        }

        # Expected structure for TwoPhotonSeries
        expected_two_photon_series = {
            metadata_key: {
                "name": "TwoPhotonSeries",
                "description": "Imaging data from two-photon excitation microscopy.",
                "unit": "n.a.",
                "imaging_plane_metadata_key": "default_imaging_plane_metadata_key",  # References the default imaging plane
                "dimension": [10, 10],  # Mock data dimensions
            }
        }

        # Verify ImagingPlanes structure matches expected (NaN values of excitation/emission lambda removed for comparison)
        ophys_metadata = metadata["Ophys"]
        actual_imaging_planes = remove_nan_for_comparison(ophys_metadata["ImagingPlanes"].to_dict())
        assert actual_imaging_planes == expected_imaging_planes

        # Verify TwoPhotonSeries structure matches expected exactly
        actual_two_photon_series = remove_nan_for_comparison(ophys_metadata["TwoPhotonSeries"].to_dict())
        assert actual_two_photon_series == expected_two_photon_series

    def test_single_segmentation_interface_metadata_structure(self):
        """Test that a single segmentation interface creates proper dictionary metadata."""
        metadata_key = "roi_analysis"
        interface = MockSegmentationInterface(metadata_key=metadata_key)
        metadata = interface.get_metadata()

        # Expected structure for ImageSegmentation
        expected_image_segmentation = {
            "name": "ImageSegmentation",
            metadata_key: {
                "name": "PlaneSegmentation",
                "description": "Segmented ROIs",
                "imaging_plane_metadata_key": "default_imaging_plane_metadata_key",
            },
        }

        # Expected structure for ImagingPlanes (NaN values of excitation/emission lambda excluded for comparison)
        expected_imaging_planes = {
            "default_imaging_plane_metadata_key": {
                "name": "ImagingPlane",
                "description": "The plane or volume being imaged by the microscope.",
                "indicator": "unknown",
                "location": "unknown",
                "device": "Microscope",
                "optical_channel": [{"name": "channel_num_0", "description": "An optical channel of the microscope."}],
            }
        }

        # Verify ImageSegmentation structure matches expected exactly
        actual_image_segmentation = remove_nan_for_comparison(metadata["Ophys"]["ImageSegmentation"])
        assert actual_image_segmentation == expected_image_segmentation

        # Verify ImagingPlanes structure matches expected (NaN values of excitation/emission lambda removed for comparison)
        actual_imaging_planes = remove_nan_for_comparison(metadata["Ophys"]["ImagingPlanes"])
        assert actual_imaging_planes == expected_imaging_planes

    def test_multiple_interfaces_with_converter(self):
        """Test combining one imaging and one segmentation interface with ConverterPipe."""
        imaging_metadata_key = "visual_cortex"
        segmentation_metadata_key = "visual_cortex_suite2p"

        imaging_interface = MockImagingInterface(metadata_key=imaging_metadata_key)
        segmentation_interface = MockSegmentationInterface(metadata_key=segmentation_metadata_key)

        # Create ConverterPipe with imaging and segmentation interfaces
        converter = ConverterPipe(data_interfaces=[imaging_interface, segmentation_interface])

        metadata = converter.get_metadata()

        # Expected structure for ImagingPlanes (NaN values of excitation/emission lambda excluded for comparison)
        # Now there's only one default imaging plane that all interfaces share
        expected_imaging_planes = {
            "default_imaging_plane_metadata_key": {
                "name": "ImagingPlane",
                "description": "The plane or volume being imaged by the microscope.",
                "indicator": "unknown",
                "location": "unknown",
                "device": "Microscope",
                "optical_channel": [{"name": "channel_num_0", "description": "An optical channel of the microscope."}],
            },
        }

        # Expected structure for TwoPhotonSeries
        expected_two_photon_series = {
            imaging_metadata_key: {
                "name": "TwoPhotonSeries",
                "description": "Imaging data from two-photon excitation microscopy.",
                "unit": "n.a.",
                "imaging_plane_metadata_key": "default_imaging_plane_metadata_key",
                "dimension": [10, 10],
            },
        }

        # Expected structure for ImageSegmentation
        expected_image_segmentation = {
            "name": "ImageSegmentation",
            segmentation_metadata_key: {
                "name": "PlaneSegmentation",
                "description": "Segmented ROIs",
                "imaging_plane_metadata_key": "default_imaging_plane_metadata_key",
            },
        }

        # Verify structures match expected (NaN values of excitation/emission lambda removed for comparison)
        actual_imaging_planes = remove_nan_for_comparison(metadata["Ophys"]["ImagingPlanes"].to_dict())
        assert actual_imaging_planes == expected_imaging_planes

        actual_two_photon_series = remove_nan_for_comparison(metadata["Ophys"]["TwoPhotonSeries"].to_dict())
        assert actual_two_photon_series == expected_two_photon_series

        actual_image_segmentation = remove_nan_for_comparison(metadata["Ophys"]["ImageSegmentation"])
        assert actual_image_segmentation == expected_image_segmentation

    def test_two_imaging_interfaces_metadata_structure(self):
        """Test that two imaging interfaces create proper combined dictionary metadata."""
        imaging1_metadata_key = "visual_cortex"
        imaging2_metadata_key = "hippocampus"

        imaging1_interface = MockImagingInterface(metadata_key=imaging1_metadata_key)
        imaging2_interface = MockImagingInterface(metadata_key=imaging2_metadata_key)

        # Create ConverterPipe with two imaging interfaces
        converter = ConverterPipe(data_interfaces=[imaging1_interface, imaging2_interface])

        metadata = converter.get_metadata()

        # Expected structure for ImagingPlanes (NaN values of excitation/emission lambda excluded for comparison)
        expected_imaging_planes = {
            "default_imaging_plane_metadata_key": {
                "name": "ImagingPlane",
                "description": "The plane or volume being imaged by the microscope.",
                "indicator": "unknown",
                "location": "unknown",
                "device": "Microscope",
                "optical_channel": [{"name": "channel_num_0", "description": "An optical channel of the microscope."}],
            },
        }

        # Expected structure for TwoPhotonSeries
        expected_two_photon_series = {
            imaging1_metadata_key: {
                "name": "TwoPhotonSeries",
                "description": "Imaging data from two-photon excitation microscopy.",
                "unit": "n.a.",
                "imaging_plane_metadata_key": "default_imaging_plane_metadata_key",
                "dimension": [10, 10],
            },
            imaging2_metadata_key: {
                "name": "TwoPhotonSeries",
                "description": "Imaging data from two-photon excitation microscopy.",
                "unit": "n.a.",
                "imaging_plane_metadata_key": "default_imaging_plane_metadata_key",
                "dimension": [10, 10],
            },
        }

        # Verify structures match expected (NaN values of excitation/emission lambda removed for comparison)
        actual_imaging_planes = remove_nan_for_comparison(metadata["Ophys"]["ImagingPlanes"].to_dict())
        assert actual_imaging_planes == expected_imaging_planes

        actual_two_photon_series = remove_nan_for_comparison(metadata["Ophys"]["TwoPhotonSeries"].to_dict())
        assert actual_two_photon_series == expected_two_photon_series

    def test_two_segmentation_interfaces_metadata_structure(self):
        """Test that two segmentation interfaces create proper combined dictionary metadata."""
        segmentation1_metadata_key = "analysis1"
        segmentation2_metadata_key = "analysis2"

        segmentation1_interface = MockSegmentationInterface(metadata_key=segmentation1_metadata_key)
        segmentation2_interface = MockSegmentationInterface(metadata_key=segmentation2_metadata_key)

        # Create ConverterPipe with two segmentation interfaces
        converter = ConverterPipe(data_interfaces=[segmentation1_interface, segmentation2_interface])

        metadata = converter.get_metadata()

        # Expected structure for ImagingPlanes (NaN values of excitation/emission lambda excluded for comparison)
        expected_imaging_planes = {
            "default_imaging_plane_metadata_key": {
                "name": "ImagingPlane",
                "description": "The plane or volume being imaged by the microscope.",
                "indicator": "unknown",
                "location": "unknown",
                "device": "Microscope",
                "optical_channel": [{"name": "channel_num_0", "description": "An optical channel of the microscope."}],
            },
        }

        # Expected structure for ImageSegmentation
        expected_image_segmentation = {
            "name": "ImageSegmentation",
            segmentation1_metadata_key: {
                "name": "PlaneSegmentation",
                "description": "Segmented ROIs",
                "imaging_plane_metadata_key": "default_imaging_plane_metadata_key",
            },
            segmentation2_metadata_key: {
                "name": "PlaneSegmentation",
                "description": "Segmented ROIs",
                "imaging_plane_metadata_key": "default_imaging_plane_metadata_key",
            },
        }

        # Verify structures match expected (NaN values of excitation/emission lambda removed for comparison)
        actual_imaging_planes = remove_nan_for_comparison(metadata["Ophys"]["ImagingPlanes"].to_dict())
        assert actual_imaging_planes == expected_imaging_planes

        actual_image_segmentation = remove_nan_for_comparison(metadata["Ophys"]["ImageSegmentation"])
        assert actual_image_segmentation == expected_image_segmentation


class TestOphysMetadataPropagation:
    """Test suite for ophys metadata propagation to NWB files and data handling."""

    def test_two_imaging_interfaces_default_behavior(self):
        """When adding multiple imaging interfaces, the link to the same plane by default"""
        region1_metadata_key = "region1"
        region2_metadata_key = "region2"

        interface1 = MockImagingInterface(metadata_key=region1_metadata_key)
        interface2 = MockImagingInterface(metadata_key=region2_metadata_key)

        # Create ConverterPipe with both interfaces
        converter = ConverterPipe(data_interfaces=[interface1, interface2])

        metadata = converter.get_metadata()

        # Modify TwoPhotonSeries names to make them unique for NWB creation
        region1_series_name = "TwoPhotonSeriesRegion1"
        region2_series_name = "TwoPhotonSeriesRegion2"

        metadata["Ophys"]["TwoPhotonSeries"][region1_metadata_key]["name"] = region1_series_name
        metadata["Ophys"]["TwoPhotonSeries"][region2_metadata_key]["name"] = region2_series_name

        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Should have only one imaging plane because both imaging planes have the same name
        assert len(nwbfile.imaging_planes) == 1
        assert "ImagingPlane" in nwbfile.imaging_planes

        # Should have two TwoPhotonSeries
        two_photon_series_list = [
            obj for obj in nwbfile.acquisition.values() if obj.neurodata_type == "TwoPhotonSeries"
        ]
        assert len(two_photon_series_list) == 2

        # Both should reference the same imaging plane object
        plane_names = {series.imaging_plane.name for series in two_photon_series_list}
        assert plane_names == {"ImagingPlane"}

        # Series should have different names
        series_names = {series.name for series in two_photon_series_list}
        assert series_names == {region1_series_name, region2_series_name}

    def test_multiple_imaging_interfaces_linking_to_same_imaging_plane(self):
        """ "Adding multiple imaging interfaces and explicitly linking to the same imaging plane."""
        series1_metadata_key = "series1"
        series2_metadata_key = "series2"
        shared_plane_key = "shared_plane"

        # Create two imaging interfaces with different metadata_keys but will reference same plane
        interface1 = MockImagingInterface(metadata_key=series1_metadata_key)
        interface2 = MockImagingInterface(metadata_key=series2_metadata_key)

        # Create ConverterPipe with both interfaces
        converter = ConverterPipe(data_interfaces=[interface1, interface2])

        # Get metadata and modify it so both series reference the same plane
        metadata = converter.get_metadata()

        # First: Create a new imaging plane entry in the metadata
        shared_plane_metadata = dict(
            metadata["Ophys"]["ImagingPlanes"]["default_imaging_plane_metadata_key"]
        )  # Use default plane as template
        shared_plane_metadata["name"] = "ImagingPlaneShared"  # Set the plane name
        metadata["Ophys"]["ImagingPlanes"][shared_plane_key] = shared_plane_metadata

        # Then: Modify the TwoPhotonSeries to have unique names and reference the new shared plane
        metadata["Ophys"]["TwoPhotonSeries"][series1_metadata_key]["name"] = "TwoPhotonSeries1"
        metadata["Ophys"]["TwoPhotonSeries"][series2_metadata_key]["name"] = "TwoPhotonSeries2"
        metadata["Ophys"]["TwoPhotonSeries"][series1_metadata_key]["imaging_plane_metadata_key"] = shared_plane_key
        metadata["Ophys"]["TwoPhotonSeries"][series2_metadata_key]["imaging_plane_metadata_key"] = shared_plane_key

        # Create NWB file to verify structure
        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Should have only one imaging plane since both series reference the same plane
        assert len(nwbfile.imaging_planes) == 1
        assert "ImagingPlaneShared" in nwbfile.imaging_planes

        # Should have two TwoPhotonSeries, both referencing the same plane
        two_photon_series_list = [
            obj for obj in nwbfile.acquisition.values() if obj.neurodata_type == "TwoPhotonSeries"
        ]
        assert len(two_photon_series_list) == 2

        # Both should reference the same imaging plane
        plane_names = {series.imaging_plane.name for series in two_photon_series_list}
        assert plane_names == {"ImagingPlaneShared"}

        # Series should have different names
        series_names = {series.name for series in two_photon_series_list}
        assert series_names == {"TwoPhotonSeries1", "TwoPhotonSeries2"}

    def test_multiple_imaging_interfaces_linking_to_different_imaging_planes(self):
        """Test multiple imaging interfaces linking to different planes."""
        visual_cortex_metadata_key = "visual_cortex"
        hippocampus_metadata_key = "hippocampus"

        # Create two imaging interfaces with different metadata_keys (different planes)
        interface1 = MockImagingInterface(metadata_key=visual_cortex_metadata_key)
        interface2 = MockImagingInterface(metadata_key=hippocampus_metadata_key)

        # Create ConverterPipe with both interfaces
        converter = ConverterPipe(data_interfaces=[interface1, interface2])

        # Get metadata and modify it to create distinct imaging planes
        metadata = converter.get_metadata()

        # First: Create new imaging plane entries with unique names
        visual_cortex_plane_key = "VisualCortexPlane"
        hippocampus_plane_key = "HippocampusPlane"

        # Create visual cortex plane entry explicitly
        metadata["Ophys"]["ImagingPlanes"][visual_cortex_plane_key] = {
            "name": "ImagingPlaneVisualCortex",
            "description": "Visual cortex imaging plane",
            "indicator": "GCaMP6f",
            "location": "visual cortex",
            "device": "Microscope",
            "excitation_lambda": 488.0,
            "optical_channel": [
                {
                    "name": "channel_num_0",
                    "description": "An optical channel of the microscope.",
                    "emission_lambda": 520.0,
                }
            ],
        }

        # Create hippocampus plane entry explicitly
        metadata["Ophys"]["ImagingPlanes"][hippocampus_plane_key] = {
            "name": "ImagingPlaneHippocampus",
            "description": "Hippocampus imaging plane",
            "indicator": "GCaMP6f",
            "location": "hippocampus",
            "device": "Microscope",
            "excitation_lambda": 488.0,
            "optical_channel": [
                {
                    "name": "channel_num_0",
                    "description": "An optical channel of the microscope.",
                    "emission_lambda": 520.0,
                }
            ],
        }

        # Then: Modify the TwoPhotonSeries to have unique names and reference the new planes
        metadata["Ophys"]["TwoPhotonSeries"][visual_cortex_metadata_key]["name"] = "TwoPhotonSeriesVisualCortex"
        metadata["Ophys"]["TwoPhotonSeries"][hippocampus_metadata_key]["name"] = "TwoPhotonSeriesHippocampus"
        metadata["Ophys"]["TwoPhotonSeries"][visual_cortex_metadata_key][
            "imaging_plane_metadata_key"
        ] = visual_cortex_plane_key
        metadata["Ophys"]["TwoPhotonSeries"][hippocampus_metadata_key][
            "imaging_plane_metadata_key"
        ] = hippocampus_plane_key

        # Create NWB file to verify structure
        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Should have two imaging planes with the new unique names
        assert len(nwbfile.imaging_planes) == 2
        visual_cortex_plane_metadata = metadata["Ophys"]["ImagingPlanes"][visual_cortex_plane_key]
        hippocampus_plane_metadata = metadata["Ophys"]["ImagingPlanes"][hippocampus_plane_key]

        assert visual_cortex_plane_metadata["name"] in nwbfile.imaging_planes
        assert hippocampus_plane_metadata["name"] in nwbfile.imaging_planes

        # Verify visual cortex imaging plane has all the attributes from metadata
        visual_cortex_plane = nwbfile.imaging_planes[visual_cortex_plane_metadata["name"]]
        assert visual_cortex_plane.name == visual_cortex_plane_metadata["name"]
        assert visual_cortex_plane.description == visual_cortex_plane_metadata["description"]
        assert visual_cortex_plane.indicator == visual_cortex_plane_metadata["indicator"]
        assert visual_cortex_plane.location == visual_cortex_plane_metadata["location"]
        assert visual_cortex_plane.device.name == visual_cortex_plane_metadata["device"]
        assert visual_cortex_plane.excitation_lambda == visual_cortex_plane_metadata["excitation_lambda"]
        assert len(visual_cortex_plane.optical_channel) == len(visual_cortex_plane_metadata["optical_channel"])
        assert visual_cortex_plane.optical_channel[0].name == visual_cortex_plane_metadata["optical_channel"][0]["name"]
        assert (
            visual_cortex_plane.optical_channel[0].emission_lambda
            == visual_cortex_plane_metadata["optical_channel"][0]["emission_lambda"]
        )

        # Verify hippocampus imaging plane has all the attributes from metadata
        hippocampus_plane = nwbfile.imaging_planes[hippocampus_plane_metadata["name"]]
        assert hippocampus_plane.name == hippocampus_plane_metadata["name"]
        assert hippocampus_plane.description == hippocampus_plane_metadata["description"]
        assert hippocampus_plane.indicator == hippocampus_plane_metadata["indicator"]
        assert hippocampus_plane.location == hippocampus_plane_metadata["location"]
        assert hippocampus_plane.device.name == hippocampus_plane_metadata["device"]
        assert hippocampus_plane.excitation_lambda == hippocampus_plane_metadata["excitation_lambda"]
        assert len(hippocampus_plane.optical_channel) == len(hippocampus_plane_metadata["optical_channel"])
        assert hippocampus_plane.optical_channel[0].name == hippocampus_plane_metadata["optical_channel"][0]["name"]
        assert (
            hippocampus_plane.optical_channel[0].emission_lambda
            == hippocampus_plane_metadata["optical_channel"][0]["emission_lambda"]
        )

        # Should have two TwoPhotonSeries, each referencing different planes
        two_photon_series_list = [
            obj for obj in nwbfile.acquisition.values() if obj.neurodata_type == "TwoPhotonSeries"
        ]
        assert len(two_photon_series_list) == 2

        # Collect the referenced plane names
        referenced_planes = {series.imaging_plane.name for series in two_photon_series_list}
        expected_plane_names = {visual_cortex_plane_metadata["name"], hippocampus_plane_metadata["name"]}
        assert referenced_planes == expected_plane_names

    def test_multiple_segmentation_interfaces_default_behavior(self):
        """Test multiple segmentation interfaces sharing the same plane by default."""
        analysis1_metadata_key = "analysis1"
        analysis2_metadata_key = "analysis2"

        # Create two segmentation interfaces with different metadata_keys but same default plane name
        interface1 = MockSegmentationInterface(metadata_key=analysis1_metadata_key)
        interface2 = MockSegmentationInterface(metadata_key=analysis2_metadata_key)

        # Create ConverterPipe with both interfaces
        converter = ConverterPipe(data_interfaces=[interface1, interface2])

        # Get metadata and make PlaneSegmentation names unique (but keep same plane names)
        metadata = converter.get_metadata()
        metadata["Ophys"]["ImageSegmentation"][analysis1_metadata_key]["name"] = "PlaneSegmentationAnalysis1"
        metadata["Ophys"]["ImageSegmentation"][analysis2_metadata_key]["name"] = "PlaneSegmentationAnalysis2"

        # Create NWB file to verify structure
        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Should have only ONE imaging plane since both interfaces reference the same plane name
        assert len(nwbfile.imaging_planes) == 1
        assert "ImagingPlane" in nwbfile.imaging_planes

        # Should have multiple plane segmentations with unique names
        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        plane_segmentations = list(image_segmentation.plane_segmentations.values())
        assert len(plane_segmentations) == 2

        # Both should have plane segmentations with unique names
        expected_names = {"PlaneSegmentationAnalysis1", "PlaneSegmentationAnalysis2"}
        found_names = {ps.name for ps in plane_segmentations}
        assert found_names == expected_names

        # Both plane segmentations should reference the same shared imaging plane
        plane_names = {ps.imaging_plane.name for ps in plane_segmentations}
        assert plane_names == {"ImagingPlane"}

    def test_multiple_segmentation_interfaces_linking_to_same_imaging_plane(self):
        """Test multiple segmentation interfaces explicitly linking to the same imaging plane."""
        analysis1_metadata_key = "analysis1"
        analysis2_metadata_key = "analysis2"
        shared_plane_key = "shared_plane"

        # Create two segmentation interfaces with different metadata_keys but will reference same plane
        interface1 = MockSegmentationInterface(metadata_key=analysis1_metadata_key)
        interface2 = MockSegmentationInterface(metadata_key=analysis2_metadata_key)

        # Create ConverterPipe with both interfaces
        converter = ConverterPipe(data_interfaces=[interface1, interface2])

        # Get metadata and modify it so both segmentations reference the same plane
        metadata = converter.get_metadata()

        # First: Create a new imaging plane entry explicitly
        metadata["Ophys"]["ImagingPlanes"][shared_plane_key] = {
            "name": "ImagingPlaneShared",
            "description": "Shared imaging plane for segmentation",
            "indicator": "GCaMP6f",
            "location": "cortex",
            "device": "Microscope",
            "excitation_lambda": 488.0,
            "optical_channel": [
                {
                    "name": "channel_num_0",
                    "description": "An optical channel of the microscope.",
                    "emission_lambda": 520.0,
                }
            ],
        }

        # Then: Modify the PlaneSegmentation entries to have unique names and reference the new shared plane
        metadata["Ophys"]["ImageSegmentation"][analysis1_metadata_key]["name"] = "PlaneSegmentationAnalysis1"
        metadata["Ophys"]["ImageSegmentation"][analysis2_metadata_key]["name"] = "PlaneSegmentationAnalysis2"
        metadata["Ophys"]["ImageSegmentation"][analysis1_metadata_key]["imaging_plane_metadata_key"] = shared_plane_key
        metadata["Ophys"]["ImageSegmentation"][analysis2_metadata_key]["imaging_plane_metadata_key"] = shared_plane_key

        # Create NWB file to verify structure
        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Should have only one imaging plane since both segmentations reference the same plane
        assert len(nwbfile.imaging_planes) == 1
        assert "ImagingPlaneShared" in nwbfile.imaging_planes

        # Should have two PlaneSegmentations, both referencing the same plane
        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        plane_segmentations = list(image_segmentation.plane_segmentations.values())
        assert len(plane_segmentations) == 2

        # Both should reference the same imaging plane
        plane_names = {ps.imaging_plane.name for ps in plane_segmentations}
        assert plane_names == {"ImagingPlaneShared"}

        # Segmentations should have different names
        segmentation_names = {ps.name for ps in plane_segmentations}
        assert segmentation_names == {"PlaneSegmentationAnalysis1", "PlaneSegmentationAnalysis2"}

    def test_multiple_segmentation_interfaces_linking_to_different_imaging_planes(self):
        """Test multiple segmentation interfaces linking to different planes."""
        visual_cortex_metadata_key = "visual_cortex"
        hippocampus_metadata_key = "hippocampus"

        # Create two segmentation interfaces with different metadata_keys
        interface1 = MockSegmentationInterface(metadata_key=visual_cortex_metadata_key)
        interface2 = MockSegmentationInterface(metadata_key=hippocampus_metadata_key)

        # Create ConverterPipe with both interfaces
        converter = ConverterPipe(data_interfaces=[interface1, interface2])

        # Get metadata and modify it to create distinct imaging planes
        metadata = converter.get_metadata()

        # First: Create new imaging plane entries with unique names
        visual_cortex_plane_key = "VisualCortexPlane"
        hippocampus_plane_key = "HippocampusPlane"

        # Create visual cortex plane entry explicitly
        metadata["Ophys"]["ImagingPlanes"][visual_cortex_plane_key] = {
            "name": "ImagingPlaneVisualCortex",
            "description": "Visual cortex imaging plane",
            "indicator": "GCaMP6f",
            "location": "visual cortex",
            "device": "Microscope",
            "excitation_lambda": 488.0,
            "optical_channel": [
                {
                    "name": "channel_num_0",
                    "description": "An optical channel of the microscope.",
                    "emission_lambda": 520.0,
                }
            ],
        }

        # Create hippocampus plane entry explicitly
        metadata["Ophys"]["ImagingPlanes"][hippocampus_plane_key] = {
            "name": "ImagingPlaneHippocampus",
            "description": "Hippocampus imaging plane",
            "indicator": "GCaMP6f",
            "location": "hippocampus",
            "device": "Microscope",
            "excitation_lambda": 488.0,
            "optical_channel": [
                {
                    "name": "channel_num_0",
                    "description": "An optical channel of the microscope.",
                    "emission_lambda": 520.0,
                }
            ],
        }

        # Then: Modify the PlaneSegmentation entries to have unique names and reference the new planes
        metadata["Ophys"]["ImageSegmentation"][visual_cortex_metadata_key]["name"] = "PlaneSegmentationVisualCortex"
        metadata["Ophys"]["ImageSegmentation"][hippocampus_metadata_key]["name"] = "PlaneSegmentationHippocampus"
        metadata["Ophys"]["ImageSegmentation"][visual_cortex_metadata_key][
            "imaging_plane_metadata_key"
        ] = visual_cortex_plane_key
        metadata["Ophys"]["ImageSegmentation"][hippocampus_metadata_key][
            "imaging_plane_metadata_key"
        ] = hippocampus_plane_key

        # Create NWB file to verify structure
        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Should have two imaging planes with the new unique names
        assert len(nwbfile.imaging_planes) == 2
        visual_cortex_plane_metadata = metadata["Ophys"]["ImagingPlanes"][visual_cortex_plane_key]
        hippocampus_plane_metadata = metadata["Ophys"]["ImagingPlanes"][hippocampus_plane_key]

        assert visual_cortex_plane_metadata["name"] in nwbfile.imaging_planes
        assert hippocampus_plane_metadata["name"] in nwbfile.imaging_planes

        # Verify visual cortex imaging plane has all the attributes from metadata
        visual_cortex_plane = nwbfile.imaging_planes[visual_cortex_plane_metadata["name"]]
        assert visual_cortex_plane.name == visual_cortex_plane_metadata["name"]
        assert visual_cortex_plane.description == visual_cortex_plane_metadata["description"]
        assert visual_cortex_plane.indicator == visual_cortex_plane_metadata["indicator"]
        assert visual_cortex_plane.location == visual_cortex_plane_metadata["location"]
        assert visual_cortex_plane.device.name == visual_cortex_plane_metadata["device"]
        assert visual_cortex_plane.excitation_lambda == visual_cortex_plane_metadata["excitation_lambda"]
        assert len(visual_cortex_plane.optical_channel) == len(visual_cortex_plane_metadata["optical_channel"])
        assert visual_cortex_plane.optical_channel[0].name == visual_cortex_plane_metadata["optical_channel"][0]["name"]
        assert (
            visual_cortex_plane.optical_channel[0].emission_lambda
            == visual_cortex_plane_metadata["optical_channel"][0]["emission_lambda"]
        )

        # Verify hippocampus imaging plane has all the attributes from metadata
        hippocampus_plane = nwbfile.imaging_planes[hippocampus_plane_metadata["name"]]
        assert hippocampus_plane.name == hippocampus_plane_metadata["name"]
        assert hippocampus_plane.description == hippocampus_plane_metadata["description"]
        assert hippocampus_plane.indicator == hippocampus_plane_metadata["indicator"]
        assert hippocampus_plane.location == hippocampus_plane_metadata["location"]
        assert hippocampus_plane.device.name == hippocampus_plane_metadata["device"]
        assert hippocampus_plane.excitation_lambda == hippocampus_plane_metadata["excitation_lambda"]
        assert len(hippocampus_plane.optical_channel) == len(hippocampus_plane_metadata["optical_channel"])
        assert hippocampus_plane.optical_channel[0].name == hippocampus_plane_metadata["optical_channel"][0]["name"]
        assert (
            hippocampus_plane.optical_channel[0].emission_lambda
            == hippocampus_plane_metadata["optical_channel"][0]["emission_lambda"]
        )

        # Should have multiple plane segmentations from different interfaces
        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        plane_segmentations = list(image_segmentation.plane_segmentations.values())
        assert len(plane_segmentations) == 2

        # Verify plane segmentations reference the correct imaging planes
        visual_cortex_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"][visual_cortex_metadata_key]
        hippocampus_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"][hippocampus_metadata_key]

        # Find the plane segmentations by name
        segmentation_by_name = {ps.name: ps for ps in plane_segmentations}
        assert visual_cortex_segmentation_metadata["name"] in segmentation_by_name
        assert hippocampus_segmentation_metadata["name"] in segmentation_by_name

        # Verify each segmentation references the correct imaging plane
        visual_cortex_segmentation = segmentation_by_name[visual_cortex_segmentation_metadata["name"]]
        hippocampus_segmentation = segmentation_by_name[hippocampus_segmentation_metadata["name"]]

        assert visual_cortex_segmentation.imaging_plane.name == visual_cortex_plane_metadata["name"]
        assert hippocampus_segmentation.imaging_plane.name == hippocampus_plane_metadata["name"]
