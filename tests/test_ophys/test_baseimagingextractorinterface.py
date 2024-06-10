from hdmf.testing import TestCase

from neuroconv.tools.testing.mock_interfaces import MockImagingInterface


class TestBaseImagingExtractorInterface(TestCase):
    def setUp(self):
        self.mock_imaging_interface = MockImagingInterface()

    def test_photon_series_type_warning_triggered(self):
        with self.assertWarnsWith(
            warn_type=DeprecationWarning,
            exc_msg="The 'photon_series_type' argument is deprecated and will be removed in a future version. Please set 'photon_series_type' during the initialization of the BaseImagingExtractorInterface instance.",
        ):
            self.mock_imaging_interface.get_metadata(photon_series_type="TwoPhotonSeries")
