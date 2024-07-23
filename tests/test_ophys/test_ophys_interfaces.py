import tempfile
import unittest
from pathlib import Path

from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.testing.mock_interfaces import MockImagingInterface


class TestMockImagingInterface(unittest.TestCase):
    def setUp(self):
        self.mock_imaging_interface = MockImagingInterface()

    def test_run_conversion(self):

        with tempfile.TemporaryDirectory() as tmpdir:
            nwbfile_path = Path(tmpdir) / "test.nwb"
            self.mock_imaging_interface.run_conversion(nwbfile_path=nwbfile_path)

    def test_add_to_nwbfile(self):
        nwbfile = mock_NWBFile()
        self.mock_imaging_interface.add_to_nwbfile(nwbfile)
