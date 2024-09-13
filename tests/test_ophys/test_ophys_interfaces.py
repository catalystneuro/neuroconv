from neuroconv.tools.testing.data_interface_mixins import (
    ImagingExtractorInterfaceTestMixin,
)
from neuroconv.tools.testing.mock_interfaces import MockImagingInterface


class TestMockImagingInterface(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = MockImagingInterface
    interface_kwargs = dict()
