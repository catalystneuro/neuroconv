import importlib
import platform

import numpy as np
import pytest
from pynwb import NWBHDF5IO

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
class TestInscopixSegmentationInterfaceCellSetPart1(SegmentationExtractorInterfaceTestMixin):
    """Test InscopixSegmentationInterface with cellset_series_part1.isxd"""

    data_interface_cls = InscopixSegmentationInterface
    save_directory = OUTPUT_PATH
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "inscopix" / "cellset_series_part1.isxd")
    )

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(cls, request):
        """Set up common metadata for Inscopix segmentation tests."""
        cls = request.cls

        # Device metadata
        cls.device_name = "Microscope"
        cls.device_metadata = dict(name=cls.device_name, description="Inscopix Microscope")

        # Imaging plane metadata
        cls.imaging_plane_name = "ImagingPlane"
        cls.imaging_plane_metadata = dict(
            name=cls.imaging_plane_name,
            description="Inscopix Imaging Plane",
            device=cls.device_name,
            optical_channel=[
                dict(name="OpticalChannel", description="Inscopix Optical Channel", emission_lambda=np.nan)
            ],
        )

        # ImageSegmentation metadata
        cls.image_segmentation_name = "ImageSegmentation"
        cls.plane_segmentation_name = "PlaneSegmentation"
        cls.image_segmentation_metadata = dict(
            name=cls.image_segmentation_name,
            plane_segmentations=[
                dict(
                    name=cls.plane_segmentation_name,
                    description="Segmented ROIs",
                    imaging_plane=cls.imaging_plane_name,
                )
            ],
        )

        # Fluorescence metadata
        cls.fluorescence_name = "Fluorescence"
        cls.roi_response_series_name = "RoiResponseSeries"
        cls.fluorescence_metadata = dict(
            name=cls.fluorescence_name,
            roi_response_series=dict(
                name=cls.roi_response_series_name,
                description="Fluorescence trace of segmented ROIs",
                unit="n.a.",
            ),
        )

        # Combined ophys metadata for validation
        cls.ophys_metadata = dict(
            Device=[cls.device_metadata],
            ImagingPlane=[cls.imaging_plane_metadata],
            ImageSegmentation=cls.image_segmentation_metadata,
            Fluorescence=cls.fluorescence_metadata,
        )

    def check_extracted_metadata(self, metadata: dict):
        """Check that metadata is correctly extracted from Inscopix segmentation files."""

        # Check overall ophys structure
        assert "Ophys" in metadata, "Ophys not found in extracted metadata"

        # Check required components exist
        for category in ["Device", "ImagingPlane", "ImageSegmentation"]:
            assert category in metadata["Ophys"], f"{category} not found in Ophys metadata"

        # Validate Device
        device = metadata["Ophys"]["Device"][0]
        assert (
            device["name"] == self.device_metadata["name"]
        ), f"Device name mismatch: expected '{self.device_metadata['name']}', got '{device['name']}'"

        # Validate ImagingPlane
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
        assert (
            imaging_plane["name"] == self.imaging_plane_metadata["name"]
        ), f"ImagingPlane name mismatch: expected '{self.imaging_plane_metadata['name']}', got '{imaging_plane['name']}'"
        assert (
            imaging_plane["device"] == self.device_name
        ), f"ImagingPlane device mismatch: expected '{self.device_name}', got '{imaging_plane['device']}'"

        # Validate ImageSegmentation
        image_segmentation = metadata["Ophys"]["ImageSegmentation"]
        assert (
            image_segmentation["name"] == self.image_segmentation_name
        ), f"ImageSegmentation name mismatch: expected '{self.image_segmentation_name}', got '{image_segmentation['name']}'"

        # Check if Fluorescence exists in metadata
        if "Fluorescence" in metadata["Ophys"]:
            fluorescence = metadata["Ophys"]["Fluorescence"]
            assert (
                fluorescence["name"] == self.fluorescence_name
            ), f"Fluorescence name mismatch: expected '{self.fluorescence_name}', got '{fluorescence['name']}'"

    def check_read_nwb(self, nwbfile_path: str):
        """Check that the data and metadata are correctly written to the NWB file."""
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            # Check device exists
            assert self.device_name in nwbfile.devices, f"Device '{self.device_name}' not found in NWB file devices."

            # Check imaging plane exists and is properly linked to device
            assert (
                self.imaging_plane_name in nwbfile.imaging_planes
            ), f"ImagingPlane '{self.imaging_plane_name}' not found in NWB file."
            imaging_plane = nwbfile.imaging_planes[self.imaging_plane_name]
            assert (
                imaging_plane.device.name == self.device_name
            ), f"ImagingPlane device mismatch: expected '{self.device_name}', got '{imaging_plane.device.name}'"

            # Check optical channel
            assert len(imaging_plane.optical_channel) == len(
                self.imaging_plane_metadata["optical_channel"]
            ), f"Optical channel count mismatch: expected {len(self.imaging_plane_metadata['optical_channel'])}, got {len(imaging_plane.optical_channel)}"

            # Check image segmentation module exists
            assert (
                self.image_segmentation_name in nwbfile.processing
            ), f"Processing module '{self.image_segmentation_name}' not found in NWB file."
            image_segmentation = nwbfile.processing[self.image_segmentation_name]

            # Check plane segmentation exists
            assert (
                self.plane_segmentation_name in image_segmentation.plane_segmentations
            ), f"PlaneSegmentation '{self.plane_segmentation_name}' not found in ImageSegmentation."
            plane_segmentation = image_segmentation.plane_segmentations[self.plane_segmentation_name]

            # Check plane segmentation is linked to the correct imaging plane
            assert (
                plane_segmentation.imaging_plane.name == self.imaging_plane_name
            ), f"PlaneSegmentation imaging_plane mismatch: expected '{self.imaging_plane_name}', got '{plane_segmentation.imaging_plane.name}'"

            # Check that ROIs exist with image masks (based on mask_type='image' default)
            assert plane_segmentation.id.data.shape[0] > 0, "No ROIs found in PlaneSegmentation"
            assert "image_mask" in plane_segmentation, "No image masks found in PlaneSegmentation"

            # Check fluorescence data
            assert (
                self.fluorescence_name in nwbfile.processing
            ), f"Processing module '{self.fluorescence_name}' not found in NWB file."
            fluorescence = nwbfile.processing[self.fluorescence_name]

            # Check roi response series exists
            assert (
                self.roi_response_series_name in fluorescence.roi_response_series
            ), f"RoiResponseSeries '{self.roi_response_series_name}' not found in Fluorescence."
            roi_response_series = fluorescence.roi_response_series[self.roi_response_series_name]

            # Check data dimensions and connections
            num_rois = plane_segmentation.id.data.shape[0]
            assert (
                roi_response_series.data.shape[1] == num_rois
            ), f"ROI count mismatch between PlaneSegmentation ({num_rois}) and RoiResponseSeries ({roi_response_series.data.shape[1]})"

            # Validate trace data
            assert roi_response_series.data.shape[0] > 0, "No timepoints found in RoiResponseSeries"
            assert (
                roi_response_series.data.dtype == np.float32 or roi_response_series.data.dtype == np.float64
            ), f"Data type is not float: {roi_response_series.data.dtype}"

            # Check ROI table references
            assert (
                roi_response_series.rois.table is plane_segmentation
            ), "RoiResponseSeries is not linked to the correct PlaneSegmentation"

            # Check ID handling - confirm the _create_integer_id_wrapper functionality
            assert all(
                isinstance(roi_id, (int, np.integer)) for roi_id in plane_segmentation.id.data
            ), "ROI IDs are not integers"

        # Call parent check_read_nwb to verify extractor compatibility
        super().check_read_nwb(nwbfile_path=nwbfile_path)


@skip_on_darwin_arm64
class TestInscopixSegmentationInterfaceCellSet(SegmentationExtractorInterfaceTestMixin):
    """Test InscopixSegmentationInterface with cellset.isxd"""

    data_interface_cls = InscopixSegmentationInterface
    save_directory = OUTPUT_PATH
    interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "inscopix" / "cellset.isxd"))


@skip_on_darwin_arm64
class TestInscopixSegmentationInterfaceCellSetEmpty(SegmentationExtractorInterfaceTestMixin):
    """Test InscopixSegmentationInterface with empty_cellset.isxd"""

    data_interface_cls = InscopixSegmentationInterface
    save_directory = OUTPUT_PATH
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "inscopix" / "empty_cellset.isxd")
    )
