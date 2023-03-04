import unittest

from neuroconv.datainterfaces import CaimanSegmentationInterface
from neuroconv.tools.testing.data_interface_mixins import (
    SegmentationExtractorInterfaceTestMixin,
)

try:
    from .setup_paths import OPHYS_DATA_PATH as DATA_PATH
    from .setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH as DATA_PATH
    from setup_paths import OUTPUT_PATH


class TestCaimanSegmentationInterface(SegmentationExtractorInterfaceTestMixin, unittest.TestCase):
    data_interface_cls = CaimanSegmentationInterface
    cases = dict(file_path=str(DATA_PATH / "segmentation_datasets" / "caiman" / "caiman_analysis.hdf5"))
    save_directory = OUTPUT_PATH
