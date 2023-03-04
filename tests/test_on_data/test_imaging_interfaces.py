import unittest

from neuroconv.datainterfaces import TiffImagingInterface
from neuroconv.tools.testing.data_interface import ImagingExtractorInterfaceTestMixin

try:
    from .setup_paths import OPHYS_DATA_PATH as DATA_PATH
    from .setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH as DATA_PATH
    from setup_paths import OUTPUT_PATH


class TestTiffImagingInterface(ImagingExtractorInterfaceTestMixin, unittest.TestCase):
    data_interface_cls = TiffImagingInterface
    cases = dict(
        file_path=str(DATA_PATH / "imaging_datasets" / "Tif" / "demoMovie.tif"),
        sampling_frequency=15.0,  # typically provided by user
    )
    save_directory = OUTPUT_PATH
