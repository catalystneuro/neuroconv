from unittest import TestCase

from parameterized import parameterized_class

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
    from .setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH


@parameterized_class(
    [
        {"conversion_options": {"mask_type": "image", "include_background": True}},
        {"conversion_options": {"mask_type": "pixel", "include_background": True}},
        {"conversion_options": {"mask_type": "voxel", "include_background": True}},
        {"conversion_options": {"mask_type": None, "include_background": True}},
        {"conversion_options": {"include_roi_centroids": False, "include_background": True}},
        {"conversion_options": {"include_roi_acceptance": False, "include_background": True}},
        {"conversion_options": {"include_background": False}},
    ]
)
class TestCaimanSegmentationInterface(SegmentationExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = CaimanSegmentationInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "caiman" / "caiman_analysis.hdf5")
    )
    save_directory = OUTPUT_PATH


class TestCaimanSegmentationInterface_invalid(SegmentationExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = CaimanSegmentationInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "caiman" / "caiman_analysis.hdf5")
    )
    save_directory = OUTPUT_PATH

    def test_invalid_mask_type(self):
        self.check_invalid_mask_type()


class TestCnmfeSegmentationInterface(SegmentationExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = CnmfeSegmentationInterface
    interface_kwargs = dict(
        file_path=str(
            OPHYS_DATA_PATH / "segmentation_datasets" / "cnmfe" / "2014_04_01_p203_m19_check01_cnmfeAnalysis.mat"
        )
    )
    save_directory = OUTPUT_PATH


class TestExtractSegmentationInterface(SegmentationExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = ExtractSegmentationInterface
    interface_kwargs = [
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
    ]
    save_directory = OUTPUT_PATH

    def test_extract_segmentation_interface_non_default_output_struct_name(self):
        """Test that the value for 'output_struct_name' is propagated to the extractor level
        where an error is raised."""
        file_path = OPHYS_DATA_PATH / "segmentation_datasets" / "extract" / "extract_public_output.mat"
        with self.assertRaisesRegex(AssertionError, "Output struct name 'not_output' not found in file."):
            ExtractSegmentationInterface(
                file_path=str(file_path),
                sampling_frequency=15.0,
                output_struct_name="not_output",
            )


class TestSuite2pSegmentationInterface(SegmentationExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = Suite2pSegmentationInterface
    interface_kwargs = [
        dict(
            folder_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"),
            channel_name="chan1",
            plane_name="plane0",
        ),
        dict(
            folder_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"),
            channel_name="chan2",
            plane_name="plane0",
        ),
    ]
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls) -> None:
        plane_suffices = ["Chan1Plane0", "Chan2Plane0"]
        cls.imaging_plane_names = ["ImagingPlane" + plane_suffix for plane_suffix in plane_suffices]
        cls.plane_segmentation_names = ["PlaneSegmentation" + plane_suffix for plane_suffix in plane_suffices]
        cls.mean_image_names = ["MeanImage" + plane_suffix for plane_suffix in plane_suffices]
        cls.correlation_image_names = ["CorrelationImage" + plane_suffix for plane_suffix in plane_suffices]
        cls.raw_traces_names = ["RoiResponseSeries" + plane_suffix for plane_suffix in plane_suffices]
        cls.neuropil_traces_names = ["Neuropil" + plane_suffix for plane_suffix in plane_suffices]
        cls.deconvolved_trace_name = "Deconvolved" + plane_suffices[0]

    def check_extracted_metadata(self, metadata: dict):
        """Check extracted metadata is adjusted correctly for each plane and channel combination."""
        self.assertEqual(metadata["Ophys"]["ImagingPlane"][0]["name"], self.imaging_plane_names[self.case])
        plane_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]
        plane_segmentation_name = self.plane_segmentation_names[self.case]
        self.assertEqual(plane_segmentation_metadata["name"], plane_segmentation_name)
        summary_images_metadata = metadata["Ophys"]["SegmentationImages"][plane_segmentation_name]
        self.assertEqual(summary_images_metadata["correlation"]["name"], self.correlation_image_names[self.case])
        self.assertEqual(summary_images_metadata["mean"]["name"], self.mean_image_names[self.case])

        raw_traces_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["raw"]
        self.assertEqual(raw_traces_metadata["name"], self.raw_traces_names[self.case])
        neuropil_traces_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["neuropil"]
        self.assertEqual(neuropil_traces_metadata["name"], self.neuropil_traces_names[self.case])
        if self.case == 0:
            deconvolved_trace_metadata = metadata["Ophys"]["Fluorescence"][plane_segmentation_name]["deconvolved"]
            self.assertEqual(deconvolved_trace_metadata["name"], self.deconvolved_trace_name)


class TestSuite2pSegmentationInterfaceWithStubTest(SegmentationExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = Suite2pSegmentationInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"),
        channel_name="chan1",
        plane_name="plane0",
    )
    save_directory = OUTPUT_PATH
    conversion_options = dict(stub_test=True)
