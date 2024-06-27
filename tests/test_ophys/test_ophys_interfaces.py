import unittest

from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.testing.mock_interfaces import MockImagingInterface


class TestMockImagingInterface(unittest.TestCase):
    def setUp(self):
        self.mock_imaging_interface = MockImagingInterface()

    def test_run_conversion(self):
        self.mock_imaging_interface.run_conversion()

    def test_add_to_nwbfile(self):
        nwbfile = mock_NWBFile()
        self.mock_imaging_interface.add_to_nwbfile(nwbfile)
