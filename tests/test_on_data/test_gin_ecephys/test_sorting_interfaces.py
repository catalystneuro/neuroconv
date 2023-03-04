import unittest

from neuroconv.datainterfaces import PhySortingInterface
from neuroconv.tools.testing.data_interface_mixins import (
    SortingExtractorInterfaceTestMixin,
)

try:
    from ..setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from ..setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from setup_paths import OUTPUT_PATH


class TestAxonRecordingInterface(SortingExtractorInterfaceTestMixin, unittest.TestCase):
    data_interface_cls = PhySortingInterface
    cases = (dict(folder_path=str(DATA_PATH / "phy" / "phy_example_0")),)
    save_directory = OUTPUT_PATH
