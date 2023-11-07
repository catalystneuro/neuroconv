import unittest

from neuroconv.tools.testing.mock_interfaces import MockImagingInterface


class TestMockImagingInterface(unittest.TestCase):
    def setUp(self):
        self.mock_imaging_interface = MockImagingInterface()

    def test_run_conversion(self):
        self.mock_imaging_interface.run_conversion()
