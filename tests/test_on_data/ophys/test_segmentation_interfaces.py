import pytest

from neuroconv.datainterfaces import (
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    ExtractSegmentationInterface,
    Suite2pSegmentationInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    SegmentationExtractorInterfaceTestMixin,
)

try:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH


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
