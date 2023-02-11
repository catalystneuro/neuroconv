import datetime
from unittest import TestCase
from shutil import rmtree
from tempfile import mkdtemp
from pathlib import Path

from neuroconv.datainterfaces import SpikeGLXConverter

from ..setup_paths import ECEPHY_DATA_PATH

SPIKEGLX_PATH = ECEPHY_DATA_PATH / "spikeglx"


class TestSpikeGLXConverter(TestCase):
    def setUp(self):
        self.tmpdir = Path(mkdtemp())

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_spikeglx_converter(self):
        # TODO, make temporary symlinks to emulate multi-probe

        converter = SpikeGLXConverter(folder_path=SPIKEGLX_PATH / "Noise4sam_g0")
        print(converter.data_interface_objects)

        metadata = converter.get_metadata()
        # Check some essential metadata structure and values

        converter.run_conversion(metadata=metadata, nwbfile_path=self.tmpdir / "test_spikeglx_converter.nwb")
        # Check if everything was written as intended
        assert False
