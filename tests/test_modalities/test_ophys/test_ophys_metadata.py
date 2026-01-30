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
    We have defaults of NaN for those and therefore we need to remove before comparing
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
    """Test suite for ophys interfaces get_metadata() methods with dictionary structure.

    These tests verify that get_metadata() returns provenance-only data with the user's
    metadata_key directly as the dictionary key.
    """

    def test_single_imaging_interface(self):
        """Test that a single imaging interface creates proper dictionary metadata.

        get_metadata() should return only source-extracted data (provenance), keyed by
        the user's metadata_key directly (e.g., "visual_cortex" not "visual_cortex_microscopy_series_metadata_key").
        """
        metadata_key = "visual_cortex"
        interface = MockImagingInterface(metadata_key=metadata_key)
        metadata = interface.get_metadata()

        # Verify the metadata uses the metadata_key directly as the key
        ophys_metadata = metadata["Ophys"]

        # MicroscopySeries should have an entry keyed by metadata_key
        assert "MicroscopySeries" in ophys_metadata
        assert metadata_key in ophys_metadata["MicroscopySeries"]

        # Verify MicroscopySeries contains source-extracted data
        microscopy_series = ophys_metadata["MicroscopySeries"][metadata_key]
        assert "dimension" in microscopy_series  # This comes from the extractor

        # ImagingPlanes should also be keyed by metadata_key (if optical channels exist)
        if "ImagingPlanes" in ophys_metadata and ophys_metadata["ImagingPlanes"]:
            assert metadata_key in ophys_metadata["ImagingPlanes"]
            imaging_plane = ophys_metadata["ImagingPlanes"][metadata_key]
            # If optical channels exist, they should be present
            if imaging_plane:
                assert "optical_channel" in imaging_plane

    def test_single_segmentation_interface(self):
        """Test that a single segmentation interface creates proper dictionary metadata.

        get_metadata() should return only source-extracted data (provenance), keyed by
        the user's metadata_key directly.
        """
        metadata_key = "suite2p_analysis"
        interface = MockSegmentationInterface(metadata_key=metadata_key)
        metadata = interface.get_metadata()

        ophys_metadata = metadata["Ophys"]

        # PlaneSegmentations should have an entry keyed by metadata_key
        assert "PlaneSegmentations" in ophys_metadata
        assert metadata_key in ophys_metadata["PlaneSegmentations"]

        # RoiResponses should have entries for available traces keyed by metadata_key
        if "RoiResponses" in ophys_metadata and ophys_metadata["RoiResponses"]:
            assert metadata_key in ophys_metadata["RoiResponses"]
            # The trace types that exist in the extractor should be present
            roi_responses = ophys_metadata["RoiResponses"][metadata_key]
            # MockSegmentationInterface has raw and dff traces
            assert isinstance(roi_responses, dict)

        # SegmentationImages keyed by metadata_key (if images exist)
        if "SegmentationImages" in ophys_metadata and ophys_metadata["SegmentationImages"]:
            assert metadata_key in ophys_metadata["SegmentationImages"]

    def test_multiple_mixing_imaging_and_segmentation_in_converter(self):
        """Test combining one imaging and one segmentation interface with ConverterPipe."""
        imaging_metadata_key = "imaging_data"
        segmentation_metadata_key = "segmentation_data"

        imaging_interface = MockImagingInterface(metadata_key=imaging_metadata_key)
        segmentation_interface = MockSegmentationInterface(metadata_key=segmentation_metadata_key)

        # Create ConverterPipe with imaging and segmentation interfaces
        converter = ConverterPipe(data_interfaces=[imaging_interface, segmentation_interface])

        metadata = converter.get_metadata()

        ophys_metadata = metadata["Ophys"]

        # MicroscopySeries should have entry for imaging interface
        assert imaging_metadata_key in ophys_metadata["MicroscopySeries"]

        # PlaneSegmentations should have entry for segmentation interface
        assert segmentation_metadata_key in ophys_metadata["PlaneSegmentations"]

        # RoiResponses should have entry for segmentation interface
        if "RoiResponses" in ophys_metadata and ophys_metadata["RoiResponses"]:
            assert segmentation_metadata_key in ophys_metadata["RoiResponses"]

    def test_two_imaging_interfaces_in_converter(self):
        """Test that two imaging interfaces create proper combined dictionary metadata."""
        imaging1_metadata_key = "visual_cortex"
        imaging2_metadata_key = "hippocampus"

        imaging1_interface = MockImagingInterface(metadata_key=imaging1_metadata_key)
        imaging2_interface = MockImagingInterface(metadata_key=imaging2_metadata_key)

        # Create ConverterPipe with two imaging interfaces
        converter = ConverterPipe(data_interfaces=[imaging1_interface, imaging2_interface])

        metadata = converter.get_metadata()

        ophys_metadata = metadata["Ophys"]

        # MicroscopySeries should have entries for both interfaces
        assert imaging1_metadata_key in ophys_metadata["MicroscopySeries"]
        assert imaging2_metadata_key in ophys_metadata["MicroscopySeries"]

        # Both should have dimension from extractor
        assert "dimension" in ophys_metadata["MicroscopySeries"][imaging1_metadata_key]
        assert "dimension" in ophys_metadata["MicroscopySeries"][imaging2_metadata_key]

    def test_two_segmentation_interfaces_metadata_structure(self):
        """Test that two segmentation interfaces create proper combined dictionary metadata."""
        segmentation1_metadata_key = "analysis1"
        segmentation2_metadata_key = "analysis2"

        segmentation1_interface = MockSegmentationInterface(metadata_key=segmentation1_metadata_key)
        segmentation2_interface = MockSegmentationInterface(metadata_key=segmentation2_metadata_key)

        # Create ConverterPipe with two segmentation interfaces
        converter = ConverterPipe(data_interfaces=[segmentation1_interface, segmentation2_interface])

        metadata = converter.get_metadata()

        ophys_metadata = metadata["Ophys"]

        # PlaneSegmentations should have entries for both interfaces
        assert segmentation1_metadata_key in ophys_metadata["PlaneSegmentations"]
        assert segmentation2_metadata_key in ophys_metadata["PlaneSegmentations"]


class TestOphysMetadataPropagation:
    """Test suite for ophys metadata propagation to NWB files and data handling.

    These tests verify that the conversion process works correctly, with defaults
    being applied at NWB object creation time when needed.
    """

    def test_two_imaging_interfaces_default_behavior(self):
        """When adding multiple imaging interfaces, they link to the same default plane."""
        region1_metadata_key = "region1"
        region2_metadata_key = "region2"

        interface1 = MockImagingInterface(metadata_key=region1_metadata_key)
        interface2 = MockImagingInterface(metadata_key=region2_metadata_key)

        # Create ConverterPipe with both interfaces
        converter = ConverterPipe(data_interfaces=[interface1, interface2])

        metadata = converter.get_metadata()

        # Modify MicroscopySeries names to make them unique for NWB creation
        region1_series_name = "MicroscopySeriesRegion1"
        region2_series_name = "MicroscopySeriesRegion2"

        metadata["Ophys"]["MicroscopySeries"][region1_metadata_key]["name"] = region1_series_name
        metadata["Ophys"]["MicroscopySeries"][region2_metadata_key]["name"] = region2_series_name

        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Should have only one imaging plane (default)
        assert len(nwbfile.imaging_planes) == 1
        assert "ImagingPlane" in nwbfile.imaging_planes

        # Should have two TwoPhotonSeries (the actual NWB type)
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
        """Adding multiple imaging interfaces and explicitly linking to the same imaging plane."""
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
        metadata["Ophys"]["ImagingPlanes"][shared_plane_key] = {
            "name": "ImagingPlaneShared",
            "description": "Shared imaging plane",
            "indicator": "GCaMP6f",
            "location": "cortex",
            "device_metadata_key": "default_metadata_key",
            "excitation_lambda": 488.0,
            "optical_channel": [
                {
                    "name": "channel_num_0",
                    "description": "An optical channel of the microscope.",
                    "emission_lambda": 520.0,
                }
            ],
        }

        # Then: Modify the MicroscopySeries to have unique names and reference the new shared plane
        metadata["Ophys"]["MicroscopySeries"][series1_metadata_key]["name"] = "MicroscopySeries1"
        metadata["Ophys"]["MicroscopySeries"][series2_metadata_key]["name"] = "MicroscopySeries2"
        metadata["Ophys"]["MicroscopySeries"][series1_metadata_key]["imaging_plane_metadata_key"] = shared_plane_key
        metadata["Ophys"]["MicroscopySeries"][series2_metadata_key]["imaging_plane_metadata_key"] = shared_plane_key

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
        assert series_names == {"MicroscopySeries1", "MicroscopySeries2"}

    def test_multiple_imaging_interfaces_linking_to_different_imaging_planes(self):
        """Test multiple imaging interfaces linking to different planes with different devices."""
        visual_cortex_metadata_key = "visual_cortex"
        hippocampus_metadata_key = "hippocampus"

        # Create two imaging interfaces with different metadata_keys (different planes)
        interface1 = MockImagingInterface(metadata_key=visual_cortex_metadata_key)
        interface2 = MockImagingInterface(metadata_key=hippocampus_metadata_key)

        # Create ConverterPipe with both interfaces
        converter = ConverterPipe(data_interfaces=[interface1, interface2])

        # Get metadata and modify it to create distinct imaging planes with different devices
        metadata = converter.get_metadata()

        # Create different device metadata at top level following new schema
        visual_cortex_device_key = "visual_cortex_device"
        hippocampus_device_key = "hippocampus_device"

        # Add devices to top-level Devices
        metadata["Devices"][visual_cortex_device_key] = {
            "name": "VisualCortexMicroscope",
            "description": "Microscope for visual cortex imaging",
        }
        metadata["Devices"][hippocampus_device_key] = {
            "name": "HippocampusMicroscope",
            "description": "Microscope for hippocampus imaging",
        }

        # Create new imaging plane entries with unique names and different devices
        visual_cortex_plane_key = "visual_cortex_plane"
        hippocampus_plane_key = "hippocampus_plane"

        # Create visual cortex plane entry explicitly
        metadata["Ophys"]["ImagingPlanes"][visual_cortex_plane_key] = {
            "name": "ImagingPlaneVisualCortex",
            "description": "Visual cortex imaging plane",
            "indicator": "GCaMP6f",
            "location": "visual cortex",
            "device_metadata_key": visual_cortex_device_key,
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
            "device_metadata_key": hippocampus_device_key,
            "excitation_lambda": 488.0,
            "optical_channel": [
                {
                    "name": "channel_num_0",
                    "description": "An optical channel of the microscope.",
                    "emission_lambda": 520.0,
                }
            ],
        }

        # Then: Modify the MicroscopySeries to have unique names and reference the new planes
        metadata["Ophys"]["MicroscopySeries"][visual_cortex_metadata_key]["name"] = "MicroscopySeriesVisualCortex"
        metadata["Ophys"]["MicroscopySeries"][hippocampus_metadata_key]["name"] = "MicroscopySeriesHippocampus"
        metadata["Ophys"]["MicroscopySeries"][visual_cortex_metadata_key][
            "imaging_plane_metadata_key"
        ] = visual_cortex_plane_key
        metadata["Ophys"]["MicroscopySeries"][hippocampus_metadata_key][
            "imaging_plane_metadata_key"
        ] = hippocampus_plane_key

        # Create NWB file to verify structure
        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Should have two imaging planes with the new unique names
        assert len(nwbfile.imaging_planes) == 2
        assert "ImagingPlaneVisualCortex" in nwbfile.imaging_planes
        assert "ImagingPlaneHippocampus" in nwbfile.imaging_planes

        # Verify visual cortex imaging plane has expected device
        visual_cortex_plane = nwbfile.imaging_planes["ImagingPlaneVisualCortex"]
        assert visual_cortex_plane.device.name == "VisualCortexMicroscope"

        # Verify hippocampus imaging plane has expected device
        hippocampus_plane = nwbfile.imaging_planes["ImagingPlaneHippocampus"]
        assert hippocampus_plane.device.name == "HippocampusMicroscope"

        # Should have two TwoPhotonSeries, each referencing different planes
        two_photon_series_list = [
            obj for obj in nwbfile.acquisition.values() if obj.neurodata_type == "TwoPhotonSeries"
        ]
        assert len(two_photon_series_list) == 2

        # Collect the referenced plane names
        referenced_planes = {series.imaging_plane.name for series in two_photon_series_list}
        assert referenced_planes == {"ImagingPlaneVisualCortex", "ImagingPlaneHippocampus"}

        # Verify both devices are propagated to NWB file
        assert len(nwbfile.devices) == 2
        assert "VisualCortexMicroscope" in nwbfile.devices
        assert "HippocampusMicroscope" in nwbfile.devices

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
        metadata["Ophys"]["PlaneSegmentations"][analysis1_metadata_key]["name"] = "PlaneSegmentationAnalysis1"
        metadata["Ophys"]["PlaneSegmentations"][analysis2_metadata_key]["name"] = "PlaneSegmentationAnalysis2"

        # Create NWB file to verify structure
        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Should have only ONE imaging plane since both interfaces use defaults
        assert len(nwbfile.imaging_planes) == 1
        assert "ImagingPlane" in nwbfile.imaging_planes

        # Should have plane segmentations
        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        plane_segmentations = list(image_segmentation.plane_segmentations.values())
        assert len(plane_segmentations) == 2

        # All plane segmentations should reference the same shared imaging plane
        plane_names = {ps.imaging_plane.name for ps in plane_segmentations}
        assert plane_names == {"ImagingPlane"}

        # Verify Fluorescence containers are created properly
        fluorescence = ophys_module["Fluorescence"]
        found_fluorescence_names = set(fluorescence.roi_response_series.keys())
        assert "RoiResponseSeries" in found_fluorescence_names  # raw traces

        # Verify DfOverF containers are created properly
        df_over_f = ophys_module["DfOverF"]
        found_dff_names = set(df_over_f.roi_response_series.keys())
        assert "DfOverFSeries" in found_dff_names  # dff traces

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
            "device_metadata_key": "default_metadata_key",
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
        metadata["Ophys"]["PlaneSegmentations"][analysis1_metadata_key]["name"] = "PlaneSegmentationAnalysis1"
        metadata["Ophys"]["PlaneSegmentations"][analysis1_metadata_key]["imaging_plane_metadata_key"] = shared_plane_key
        metadata["Ophys"]["PlaneSegmentations"][analysis2_metadata_key]["name"] = "PlaneSegmentationAnalysis2"
        metadata["Ophys"]["PlaneSegmentations"][analysis2_metadata_key]["imaging_plane_metadata_key"] = shared_plane_key

        # Create NWB file to verify structure
        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Should have only one imaging plane since both segmentations reference the same plane
        assert len(nwbfile.imaging_planes) == 1
        assert "ImagingPlaneShared" in nwbfile.imaging_planes

        # Should have PlaneSegmentations referencing the same plane
        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        plane_segmentations = list(image_segmentation.plane_segmentations.values())
        assert len(plane_segmentations) == 2

        # All should reference the same imaging plane
        plane_names = {ps.imaging_plane.name for ps in plane_segmentations}
        assert plane_names == {"ImagingPlaneShared"}

    def test_multiple_segmentation_interfaces_linking_to_different_imaging_planes(self):
        """Test multiple segmentation interfaces linking to different planes with different devices."""
        visual_cortex_metadata_key = "visual_cortex"
        hippocampus_metadata_key = "hippocampus"

        # Create two segmentation interfaces with different metadata_keys
        interface1 = MockSegmentationInterface(metadata_key=visual_cortex_metadata_key)
        interface2 = MockSegmentationInterface(metadata_key=hippocampus_metadata_key)

        # Create ConverterPipe with both interfaces
        converter = ConverterPipe(data_interfaces=[interface1, interface2])

        # Get metadata and modify it to create distinct imaging planes with different devices
        metadata = converter.get_metadata()

        # Create different device metadata at top level following new schema
        visual_cortex_device_key = "visual_cortex_device"
        hippocampus_device_key = "hippocampus_device"

        # Add devices to top-level Devices
        metadata["Devices"][visual_cortex_device_key] = {
            "name": "VisualCortexMicroscope",
            "description": "Microscope for visual cortex segmentation",
        }
        metadata["Devices"][hippocampus_device_key] = {
            "name": "HippocampusMicroscope",
            "description": "Microscope for hippocampus segmentation",
        }

        # Create new imaging plane entries with unique names and different devices
        visual_cortex_plane_key = "visual_cortex_plane"
        hippocampus_plane_key = "hippocampus_plane"

        # Create visual cortex plane entry explicitly
        metadata["Ophys"]["ImagingPlanes"][visual_cortex_plane_key] = {
            "name": "ImagingPlaneVisualCortex",
            "description": "Visual cortex imaging plane",
            "indicator": "GCaMP6f",
            "location": "visual cortex",
            "device_metadata_key": visual_cortex_device_key,
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
            "device_metadata_key": hippocampus_device_key,
            "excitation_lambda": 488.0,
            "optical_channel": [
                {
                    "name": "channel_num_0",
                    "description": "An optical channel of the microscope.",
                    "emission_lambda": 520.0,
                }
            ],
        }

        # Modify the PlaneSegmentation entries to have unique names and reference the new planes
        metadata["Ophys"]["PlaneSegmentations"][visual_cortex_metadata_key]["name"] = "PlaneSegmentationVisualCortex"
        metadata["Ophys"]["PlaneSegmentations"][visual_cortex_metadata_key][
            "imaging_plane_metadata_key"
        ] = visual_cortex_plane_key
        metadata["Ophys"]["PlaneSegmentations"][hippocampus_metadata_key]["name"] = "PlaneSegmentationHippocampus"
        metadata["Ophys"]["PlaneSegmentations"][hippocampus_metadata_key][
            "imaging_plane_metadata_key"
        ] = hippocampus_plane_key

        # Create NWB file to verify structure
        nwbfile = converter.create_nwbfile(metadata=metadata)

        # Should have two imaging planes with the new unique names
        assert len(nwbfile.imaging_planes) == 2
        assert "ImagingPlaneVisualCortex" in nwbfile.imaging_planes
        assert "ImagingPlaneHippocampus" in nwbfile.imaging_planes

        # Verify imaging planes have expected devices
        visual_cortex_plane = nwbfile.imaging_planes["ImagingPlaneVisualCortex"]
        assert visual_cortex_plane.device.name == "VisualCortexMicroscope"

        hippocampus_plane = nwbfile.imaging_planes["ImagingPlaneHippocampus"]
        assert hippocampus_plane.device.name == "HippocampusMicroscope"

        # Should have plane segmentations
        ophys_module = nwbfile.processing["ophys"]
        image_segmentation = ophys_module["ImageSegmentation"]
        plane_segmentations = list(image_segmentation.plane_segmentations.values())
        assert len(plane_segmentations) == 2

        # Verify devices are propagated
        assert len(nwbfile.devices) == 2
        assert "VisualCortexMicroscope" in nwbfile.devices
        assert "HippocampusMicroscope" in nwbfile.devices
