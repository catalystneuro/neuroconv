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

    # TODO: fix this by setting a seed on the dummy imaging extractor
    def test_all_conversion_checks(self):
        pass


class TestMockSegmentationInterface(SegmentationExtractorInterfaceTestMixin):

    data_interface_cls = MockSegmentationInterface
    interface_kwargs = dict()
