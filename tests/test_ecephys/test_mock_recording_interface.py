import unittest

from neuroconv.tools.testing.data_interface_mixins import (
    RecordingExtractorInterfaceTestMixin,
)
from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface


class TestMockRecordingInterface(unittest.TestCase, RecordingExtractorInterfaceTestMixin):
    data_interface_cls = MockRecordingInterface
    interface_kwargs = [
        dict(durations=[0.100]),
    ]
