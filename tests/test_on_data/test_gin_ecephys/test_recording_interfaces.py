import unittest

from neuroconv.datainterfaces import AxonaRecordingInterface
from neuroconv.tools.testing.data_interface_mixins import RecordingExtractorInterfaceTestMixin

try:
    from ..setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from ..setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from setup_paths import OUTPUT_PATH


class TestAxonRecordingInterface(RecordingExtractorInterfaceTestMixin, unittest.TestCase):
    data_interface_cls = AxonaRecordingInterface
    cases = dict(file_path=str(DATA_PATH / "axona" / "axona_raw.bin"))
    save_directory = OUTPUT_PATH
