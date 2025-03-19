import numpy as np

from neuroconv.tools.testing.data_interface_mixins import (
    ImagingExtractorInterfaceTestMixin,
    SegmentationExtractorInterfaceTestMixin,
)
from neuroconv.tools.testing.mock_interfaces import (
    MockImagingInterface,
    MockSegmentationInterface,
)


class TestMockImagingInterface(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = MockImagingInterface
    interface_kwargs = dict()

    def test_always_write_timestamps(self, setup_interface):
        # By default the MockImagingInterface has a uniform sampling rate

        nwbfile = self.interface.create_nwbfile(always_write_timestamps=True)
        two_photon_series = nwbfile.acquisition["TwoPhotonSeries"]
        imaging = self.interface.imaging_extractor
        expected_timestamps = imaging.frame_to_time(np.arange(imaging.get_num_frames()))

        np.testing.assert_array_equal(two_photon_series.timestamps[:], expected_timestamps)

    # Remove this after roiextractors 0.5.10 is released
    def test_all_conversion_checks(self):
        pass


class TestMockSegmentationInterface(SegmentationExtractorInterfaceTestMixin):

    data_interface_cls = MockSegmentationInterface
    interface_kwargs = dict()
