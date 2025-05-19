import importlib
import platform

import pytest
import copy

from neuroconv.datainterfaces import (
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    ExtractSegmentationInterface,
    InscopixSegmentationInterface,
    Suite2pSegmentationInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    SegmentationExtractorInterfaceTestMixin,
)

try:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH

skip_on_darwin_arm64 = pytest.mark.skipif(
    platform.system() == "Darwin" and platform.machine() == "arm64",
    reason="Tests are skipped on macOS ARM64 due to platform limitations.",
)

skip_if_isx_not_installed = pytest.mark.skipif(
    not importlib.util.find_spec("isx"),
    reason="Tests are skipped because the 'isx' module is not installed.",
)


class TestCaimanSegmentationInterface(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = CaimanSegmentationInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "caiman" / "caiman_analysis.hdf5")
    )
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            {"mask_type": "image", "include_background_segmentation": True},
            {"mask_type": "pixel", "include_background_segmentation": True},
            {"mask_type": "voxel", "include_background_segmentation": True},
            # {"mask_type": None, "include_background_segmentation": True}, # Uncomment when https://github.com/catalystneuro/neuroconv/issues/530 is resolved
            {"include_roi_centroids": False, "include_background_segmentation": True},
            {"include_roi_acceptance": False, "include_background_segmentation": True},
            {"include_background_segmentation": False},
        ],
        ids=[
            "mask_type_image",
            "mask_type_pixel",
            "mask_type_voxel",
            "exclude_roi_centroids",
            "exclude_roi_acceptance",
            "exclude_background_segmentation",
        ],
    )
    def setup_interface(self, request):

        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = self.interface_kwargs
        self.conversion_options = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name


class TestCnmfeSegmentationInterface(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = CnmfeSegmentationInterface
    interface_kwargs = dict(
        file_path=str(
            OPHYS_DATA_PATH / "segmentation_datasets" / "cnmfe" / "2014_04_01_p203_m19_check01_cnmfeAnalysis.mat"
        )
    )
    save_directory = OUTPUT_PATH


class TestExtractSegmentationInterface(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = ExtractSegmentationInterface
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            dict(
                file_path=str(
                    OPHYS_DATA_PATH
                    / "segmentation_datasets"
                    / "extract"
                    / "2014_04_01_p203_m19_check01_extractAnalysis.mat"
                ),
                sampling_frequency=15.0,  # typically provided by user
            ),
            dict(
                file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "extract" / "extract_public_output.mat"),
                sampling_frequency=15.0,  # typically provided by user
            ),
        ],
        ids=["dataset_1", "dataset_2"],
    )
    def setup_interface(self, request):
        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name


def test_extract_segmentation_interface_non_default_output_struct_name():
    """Test that the value for 'output_struct_name' is propagated to the extractor level
    where an error is raised."""
    file_path = OPHYS_DATA_PATH / "segmentation_datasets" / "extract" / "extract_public_output.mat"

    with pytest.raises(AssertionError, match="Output struct name 'not_output' not found in file."):
        ExtractSegmentationInterface(
            file_path=str(file_path),
            sampling_frequency=15.0,
            output_struct_name="not_output",
        )


class TestSuite2pSegmentationInterfaceChan1Plane0(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = Suite2pSegmentationInterface
    save_directory = OUTPUT_PATH
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"),
        channel_name="chan1",
        plane_name="plane0",
    )

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(self, request):
        cls = request.cls
        plane_suffix = "Chan1Plane0"
        cls.imaging_plane_names = "ImagingPlane" + plane_suffix
        cls.plane_segmentation_names = "PlaneSegmentation" + plane_suffix
        cls.mean_image_names = "MeanImage" + plane_suffix
        cls.correlation_image_names = "CorrelationImage" + plane_suffix
        cls.raw_traces_names = "RoiResponseSeries" + plane_suffix
        cls.neuropil_traces_names = "Neuropil" + plane_suffix
        cls.deconvolved_trace_name = "Deconvolved" + plane_suffix

    def test_check_extracted_metadata(self):
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        metadata = self.interface.get_metadata()

        assert metadata["Ophys"]["ImagingPlane"][0]["name"] == self.imaging_plane_names
        plane_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]
        plane_segmentation_name = self.plane_segmentation_names
        assert plane_segmentation_metadata["name"] == plane_segmentation_name
        summary_images_metadata = metadata["Ophys"]["SegmentationImages"][plane_segmentation_name]
        assert summary_images_metadata["correlation"]["name"] == self.correlation_image_names
        assert summary_images_metadata["mean"]["name"] == self.mean_image_names

        raw_traces_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["raw"]
        assert raw_traces_metadata["name"] == self.raw_traces_names
        neuropil_traces_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["neuropil"]
        assert neuropil_traces_metadata["name"] == self.neuropil_traces_names

        deconvolved_trace_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["deconvolved"]
        assert deconvolved_trace_metadata["name"] == self.deconvolved_trace_name


class TestSuite2pSegmentationInterfaceChan2Plane0(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = Suite2pSegmentationInterface
    save_directory = OUTPUT_PATH
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"),
        channel_name="chan2",
        plane_name="plane0",
    )

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(self, request):
        cls = request.cls

        plane_suffix = "Chan2Plane0"
        cls.imaging_plane_names = "ImagingPlane" + plane_suffix
        cls.plane_segmentation_names = "PlaneSegmentation" + plane_suffix
        cls.mean_image_names = "MeanImage" + plane_suffix
        cls.correlation_image_names = "CorrelationImage" + plane_suffix
        cls.raw_traces_names = "RoiResponseSeries" + plane_suffix
        cls.neuropil_traces_names = "Neuropil" + plane_suffix
        cls.deconvolved_trace_name = None

    def test_check_extracted_metadata(self):
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        metadata = self.interface.get_metadata()

        assert metadata["Ophys"]["ImagingPlane"][0]["name"] == self.imaging_plane_names
        plane_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]
        plane_segmentation_name = self.plane_segmentation_names
        assert plane_segmentation_metadata["name"] == plane_segmentation_name
        summary_images_metadata = metadata["Ophys"]["SegmentationImages"][plane_segmentation_name]
        assert summary_images_metadata["correlation"]["name"] == self.correlation_image_names
        assert summary_images_metadata["mean"]["name"] == self.mean_image_names

        raw_traces_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["raw"]
        assert raw_traces_metadata["name"] == self.raw_traces_names
        neuropil_traces_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["neuropil"]
        assert neuropil_traces_metadata["name"] == self.neuropil_traces_names

        if self.deconvolved_trace_name:
            deconvolved_trace_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["deconvolved"]
            assert deconvolved_trace_metadata["name"] == self.deconvolved_trace_name


class TestSuite2pSegmentationInterfaceWithStubTest(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = Suite2pSegmentationInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"),
        channel_name="chan1",
        plane_name="plane0",
    )
    save_directory = OUTPUT_PATH
    conversion_options = dict(stub_test=True)

@skip_on_darwin_arm64
@skip_if_isx_not_installed
class TestInscopixSegmentationInterface(SegmentationExtractorInterfaceTestMixin):
    data_interface_cls = InscopixSegmentationInterface
    interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "inscopix" / "cellset.isxd"))
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            {"mask_type": "image", "include_background_segmentation": True},
            {"mask_type": "pixel", "include_background_segmentation": True},
            {"include_roi_centroids": False, "include_background_segmentation": True},
            {"include_roi_acceptance": False, "include_background_segmentation": True},
            {"include_background_segmentation": False},
        ],
        ids=[
            "mask_type_image",
            "mask_type_pixel",
            "exclude_roi_centroids",
            "exclude_roi_acceptance",
            "exclude_background_segmentation",
        ],
    )
    def setup_interface(self, request):
        test_id = request.node.callspec.id
        self.test_name = test_id
        self.conversion_options = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name

    def test_no_metadata_mutation(self):
        """Test that the interface does not mutate the metadata dictionary."""
        interface = self.data_interface_cls(**self.interface_kwargs)
        
        # Get the original metadata
        original_metadata = interface.get_metadata()
        
        # Create a deep copy for comparison after operations
        original_copy = copy.deepcopy(original_metadata)
        
        # Run a conversion with the metadata
        nwbfile_path = self.create_nwbfile_path("metadata_mutation_test")
        
        # Use the metadata in the conversion
        interface.run_conversion(
            nwbfile_path=nwbfile_path,
            metadata=original_metadata,
            overwrite=True,
            **self.conversion_options
        )
        
        # Verify the metadata wasn't changed
        assert original_metadata == original_copy, "Metadata was mutated during conversion"

    def test_check_extracted_metadata(self):
        """Test that the extracted metadata contains expected values."""
        interface = self.data_interface_cls(**self.interface_kwargs)
        metadata = interface.get_metadata()

        # Check basic NWB metadata
        assert "NWBFile" in metadata
        assert "Ophys" in metadata

        # Check device metadata
        assert "Device" in metadata["Ophys"]

        # Check imaging plane metadata
        assert "ImagingPlane" in metadata["Ophys"]
        assert len(metadata["Ophys"]["ImagingPlane"]) > 0

        # Check image segmentation metadata
        assert "ImageSegmentation" in metadata["Ophys"]
        assert "plane_segmentations" in metadata["Ophys"]["ImageSegmentation"]
        
        # Check that plane segmentation has a name
        plane_segmentation = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]
        assert "name" in plane_segmentation

        # Check fluorescence metadata
        assert "Fluorescence" in metadata["Ophys"]


# @skip_on_darwin_arm64
# @skip_if_isx_not_installed
# class TestInscopixSegmentationInterfaceCellSet(SegmentationExtractorInterfaceTestMixin):
#     """Test InscopixSegmentationInterface with cellset.isxd"""

#     data_interface_cls = InscopixSegmentationInterface
#     save_directory = OUTPUT_PATH
#     interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "inscopix" / "cellset.isxd"))

#     @pytest.fixture(scope="class", autouse=True)
#     def setup_metadata(self, request):
#         """Set up metadata for Inscopix CellSet test based on the provided footer."""
#         cls = request.cls

#         # Extract relevant information from the footer
#         cls.device_name = "Microscope"
#         cls.imaging_plane_name = "ImagingPlane"
#         cls.image_segmentation_name = "ImageSegmentation"
#         cls.plane_segmentation_name = "PlaneSegmentation"
#         cls.fluorescence_name = "Fluorescence"
#         cls.roi_response_series_name = "RoiResponseSeries"

#         # Use animal information from footer
#         cls.animal_id = "FV4581"
#         cls.animal_species = "CaMKIICre"
#         cls.animal_sex = "m"
#         cls.animal_description = "Retrieval day"

#         # Use microscope information from footer
#         cls.microscope_type = "NVista3"
#         cls.microscope_serial = "11132301"
#         cls.system_serial = "AC-11137705"

#         # Use imaging parameters from footer
#         cls.exp_time = 33
#         cls.focus = 1000
#         cls.gain = 6
#         cls.fps = 30
#         cls.led_power = 1.3

#         # Use ROI information from footer
#         cls.cell_names = ["C0", "C1", "C2", "C3"]
#         cls.cell_status = [0, 0, 0, 2]  # 0 = active, 2 = inactive

#         # Use image dimensions from footer
#         cls.image_width = 398
#         cls.image_height = 366

#         # Detailed metadata structures for validation
#         cls.device_metadata = dict(
#             name=cls.device_name, description=f"Inscopix {cls.microscope_type} Microscope (SN: {cls.microscope_serial})"
#         )

#         cls.imaging_plane_metadata = dict(
#             name=cls.imaging_plane_name,
#             description=f"Inscopix imaging plane at {cls.focus}um focus",
#             device=cls.device_name,
#             optical_channel=[
#                 dict(name="OpticalChannel", description="Green fluorescence channel", emission_lambda=np.nan)
#             ],
#             excitation_lambda=np.nan,
#             indicator="GCaMP",
#             location="brain region",
#         )

#         cls.image_segmentation_metadata = dict(
#             name=cls.image_segmentation_name,
#             plane_segmentations=[
#                 dict(
#                     name=cls.plane_segmentation_name,
#                     # description="Segmented ROIs from Inscopix CNMFE analysis",
#                     imaging_plane=cls.imaging_plane_name,
#                 )
#             ],
#         )

#         cls.fluorescence_metadata = dict(
#             name=cls.fluorescence_name,
#             roi_response_series=dict(
#                 name=cls.roi_response_series_name,
#                 # description="Fluorescence trace of segmented ROIs (dF over noise)",
#                 unit="dF over noise",
#             ),
#         )

#     def check_extracted_metadata(self, metadata: dict):
#         """Check that metadata is correctly extracted from Inscopix CellSet file."""
#         # Check overall ophys structure
#         assert "Ophys" in metadata, "Ophys not found in extracted metadata"

#         # Check required components exist
#         for category in ["Device", "ImagingPlane", "ImageSegmentation"]:
#             assert category in metadata["Ophys"], f"{category} not found in Ophys metadata"

#         # Validate Device
#         device = metadata["Ophys"]["Device"][0]
#         assert (
#             device["name"] == self.device_name
#         ), f"Device name mismatch: expected '{self.device_name}', got '{device['name']}'"

#         # Validate ImagingPlane
#         imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
#         assert (
#             imaging_plane["name"] == self.imaging_plane_name
#         ), f"ImagingPlane name mismatch: expected '{self.imaging_plane_name}', got '{imaging_plane['name']}'"
#         assert (
#             imaging_plane["device"] == self.device_name
#         ), f"ImagingPlane device mismatch: expected '{self.device_name}', got '{imaging_plane['device']}'"

#         # Validate ImageSegmentation
#         image_segmentation = metadata["Ophys"]["ImageSegmentation"]
#         assert (
#             "plane_segmentations" in image_segmentation
#         ), "plane_segmentations not found in ImageSegmentation metadata"

#         # Check for subject info in NWBFile metadata
#         if "Subject" in metadata.get("NWBFile", {}):
#             subject = metadata["NWBFile"]["Subject"]
#             assert (
#                 subject.get("subject_id") == self.animal_id
#             ), f"Subject ID mismatch: expected '{self.animal_id}', got '{subject.get('subject_id')}'"
#             assert (
#                 subject.get("species") == self.animal_species
#             ), f"Species mismatch: expected '{self.animal_species}', got '{subject.get('species')}'"
#             assert (
#                 subject.get("sex") == self.animal_sex
#             ), f"Sex mismatch: expected '{self.animal_sex}', got '{subject.get('sex')}'"

#     def run_custom_checks(self):
#         """Run additional custom checks for CellSet file."""
#         # Verify the segmentation extractor has valid ROIs
#         roi_ids = self.interface.segmentation_extractor.get_roi_ids()

#         # Check number of ROIs matches expected count
#         assert len(roi_ids) == len(
#             self.cell_names
#         ), f"ROI count mismatch: expected {len(self.cell_names)}, got {len(roi_ids)}"

#         # Check that image masks can be retrieved
#         for roi_id in roi_ids:
#             mask = self.interface.segmentation_extractor.get_roi_image_masks(roi_ids=[roi_id])
#             assert mask is not None, f"Could not retrieve image mask for ROI {roi_id}"
#             assert mask.shape[-2:] == (
#                 self.image_height,
#                 self.image_width,
#             ), f"Mask shape mismatch: expected ({self.image_height}, {self.image_width}), got {mask.shape[-2:]}"


# @skip_on_darwin_arm64
# @skip_if_isx_not_installed
# class TestInscopixSegmentationInterfaceCellSetPart1(SegmentationExtractorInterfaceTestMixin):
#     """Test InscopixSegmentationInterface with cellset_series_part1.isxd"""

#     data_interface_cls = InscopixSegmentationInterface
#     save_directory = OUTPUT_PATH
#     interface_kwargs = dict(
#         file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "inscopix" / "cellset_series_part1.isxd")
#     )

#     # Skip the tests that are failing due to the column length mismatch
#     @pytest.mark.skip(reason="Known issue with column length mismatch in PlaneSegmentation table")
#     def test_no_metadata_mutation(self, setup_interface):
#         super().test_no_metadata_mutation(setup_interface)

#     @pytest.mark.skip(reason="Known issue with column length mismatch in PlaneSegmentation table")
#     def test_run_conversion_with_backend(self, setup_interface, tmp_path, backend):
#         super().test_run_conversion_with_backend(setup_interface, tmp_path, backend)

#     @pytest.mark.skip(reason="Known issue with column length mismatch in PlaneSegmentation table")
#     def test_all_conversion_checks(self, setup_interface, tmp_path):
#         pass

#     @pytest.fixture(scope="class", autouse=True)
#     def setup_metadata(self, request):
#         """Set up metadata for CellSetPart1 test."""
#         cls = request.cls

#         # Basic metadata for CellSetPart1
#         cls.device_name = "Microscope"
#         cls.imaging_plane_name = "ImagingPlane"
#         cls.image_segmentation_name = "ImageSegmentation"
#         cls.plane_segmentation_name = "PlaneSegmentation"
#         cls.fluorescence_name = "Fluorescence"
#         cls.roi_response_series_name = "RoiResponseSeries"

#         # Device metadata
#         cls.device_metadata = dict(
#             name=cls.device_name,
#             description="Inscopix Microscope for time series data"
#         )

#         # Imaging plane metadata
#         cls.imaging_plane_metadata = dict(
#             name=cls.imaging_plane_name,
#             description="Inscopix Imaging Plane for time series",
#             device=cls.device_name,
#             optical_channel=[
#                 dict(
#                     name="OpticalChannel",
#                     description="Inscopix Optical Channel",
#                     emission_lambda=np.nan
#                 )
#             ],
#             excitation_lambda=np.nan,
#             indicator="GCaMP",
#             location="brain region",
#         )

#         # ImageSegmentation metadata
#         cls.image_segmentation_metadata = dict(
#             name=cls.image_segmentation_name,
#             plane_segmentations=[
#                 dict(
#                     name=cls.plane_segmentation_name,
#                     description="Segmented ROIs from time series",
#                     imaging_plane=cls.imaging_plane_name,
#                 )
#             ],
#         )

#         # Fluorescence metadata
#         cls.fluorescence_metadata = dict(
#             name=cls.fluorescence_name,
#             roi_response_series=dict(
#                 name=cls.roi_response_series_name,
#                 description="Fluorescence trace of segmented ROIs from time series",
#                 unit="dF over noise",
#             ),
#         )

#     def check_extracted_metadata(self, metadata: dict):
#         """Check that metadata is correctly extracted from CellSetPart1 file."""
#         # Check overall ophys structure
#         assert "Ophys" in metadata, "Ophys not found in extracted metadata"

#         # Check required components exist
#         for category in ["Device", "ImagingPlane", "ImageSegmentation"]:
#             assert category in metadata["Ophys"], f"{category} not found in Ophys metadata"

#         # Validate Device
#         device = metadata["Ophys"]["Device"][0]
#         assert device["name"] == self.device_name, \
#             f"Device name mismatch: expected '{self.device_name}', got '{device['name']}'"

#         # Validate ImagingPlane
#         imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
#         assert imaging_plane["name"] == self.imaging_plane_name, \
#             f"ImagingPlane name mismatch: expected '{self.imaging_plane_name}', got '{imaging_plane['name']}'"
#         assert imaging_plane["device"] == self.device_name, \
#             f"ImagingPlane device mismatch: expected '{self.device_name}', got '{imaging_plane['device']}'"


# @skip_on_darwin_arm64
# @skip_if_isx_not_installed
# class TestInscopixSegmentationInterfaceEmptyCellSet(SegmentationExtractorInterfaceTestMixin):
#     """Test InscopixSegmentationInterface with empty_cellset.isxd"""

#     data_interface_cls = InscopixSegmentationInterface
#     save_directory = OUTPUT_PATH
#     interface_kwargs = dict(
#         file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "inscopix" / "empty_cellset.isxd")
#     )

#     @pytest.fixture(scope="class", autouse=True)
#     def setup_metadata(self, request):
#         """Set up metadata for EmptyCellSet test."""
#         cls = request.cls

#         # Basic metadata for empty cellset
#         cls.device_name = "Microscope"
#         cls.imaging_plane_name = "ImagingPlane"
#         cls.image_segmentation_name = "ImageSegmentation"
#         cls.plane_segmentation_name = "PlaneSegmentation"
#         cls.fluorescence_name = "Fluorescence"
#         cls.roi_response_series_name = "RoiResponseSeries"

#         # Device metadata
#         cls.device_metadata = dict(
#             name=cls.device_name,
#             description="Inscopix Microscope (Empty Cell Set)"
#         )

#         # Imaging plane metadata
#         cls.imaging_plane_metadata = dict(
#             name=cls.imaging_plane_name,
#             description="Inscopix Imaging Plane (Empty Cell Set)",
#             device=cls.device_name,
#             optical_channel=[
#                 dict(
#                     name="OpticalChannel",
#                     description="Inscopix Optical Channel",
#                     emission_lambda=np.nan
#                 )
#             ],
#             excitation_lambda=np.nan,
#             indicator="GCaMP",
#             location="brain region",
#         )

#         # ImageSegmentation metadata
#         cls.image_segmentation_metadata = dict(
#             name=cls.image_segmentation_name,
#             plane_segmentations=[
#                 dict(
#                     name=cls.plane_segmentation_name,
#                     description="Segmented ROIs (Empty Cell Set)",
#                     imaging_plane=cls.imaging_plane_name,
#                 )
#             ],
#         )

#         # Fluorescence metadata
#         cls.fluorescence_metadata = dict(
#             name=cls.fluorescence_name,
#             roi_response_series=dict(
#                 name=cls.roi_response_series_name,
#                 description="Fluorescence trace of segmented ROIs (Empty Cell Set)",
#                 unit="dF over noise",
#             ),
#         )

#     def check_extracted_metadata(self, metadata: dict):
#         """Check that metadata is correctly extracted from EmptyCellSet file."""
#         # Check overall ophys structure
#         assert "Ophys" in metadata, "Ophys not found in extracted metadata"

#         # Check required components exist
#         for category in ["Device", "ImagingPlane", "ImageSegmentation"]:
#             assert category in metadata["Ophys"], f"{category} not found in Ophys metadata"

#         # Validate Device
#         device = metadata["Ophys"]["Device"][0]
#         assert device["name"] == self.device_name, \
#             f"Device name mismatch: expected '{self.device_name}', got '{device['name']}'"

#         # Validate ImagingPlane
#         imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
#         assert imaging_plane["name"] == self.imaging_plane_name, \
#             f"ImagingPlane name mismatch: expected '{self.imaging_plane_name}', got '{imaging_plane['name']}'"
#         assert imaging_plane["device"] == self.device_name, \
#             f"ImagingPlane device mismatch: expected '{self.device_name}', got '{imaging_plane['device']}'"

#     def run_custom_checks(self):
#         """Run additional custom checks for EmptyCellSet file."""
#         # For empty cellset, verify the segmentation extractor has no ROIs
#         roi_ids = self.interface.segmentation_extractor.get_roi_ids()
#         assert len(roi_ids) == 0, f"Expected 0 ROIs for empty cellset, got {len(roi_ids)}"

#     def check_nwbfile_temporal_alignment(self):
#         """Skip temporal alignment test for empty cellset."""
#         # Empty implementation since empty cellset doesn't have any ROIs with traces
#         pass
