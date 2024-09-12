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


class TestMockSegmentationInterface(SegmentationExtractorInterfaceTestMixin):

    data_interface_cls = MockSegmentationInterface
