from unittest import TestCase

from neuroconv.datainterfaces import CaimanSegmentationInterface, CnmfeSegmentationInterface, \
    ExtractSegmentationInterface, Suite2pSegmentationInterface
from neuroconv.tools.testing.data_interface_mixins import (
    SegmentationExtractorInterfaceTestMixin,
)

try:
    from .setup_paths import OPHYS_DATA_PATH
    from .setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH
    from setup_paths import OUTPUT_PATH


class TestCaimanSegmentationInterface(SegmentationExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = CaimanSegmentationInterface
    interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "caiman" /
                                          "caiman_analysis.hdf5"))
    save_directory = OUTPUT_PATH


class TestCnmfeSegmentationInterface(SegmentationExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = CnmfeSegmentationInterface
    interface_kwargs = dict(
        file_path=str(
            OPHYS_DATA_PATH
            / "segmentation_datasets"
            / "cnmfe"
            / "2014_04_01_p203_m19_check01_cnmfeAnalysis.mat"
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
        )
    ]
    save_directory = OUTPUT_PATH


class TestSuite2pSegmentationInterface(SegmentationExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = Suite2pSegmentationInterface
    interface_kwargs = dict(folder_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"))
    save_directory = OUTPUT_PATH

