import unittest
from pathlib import Path

from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv.tools.testing.data_interface_mixins import (
    RecordingExtractorInterfaceTestMixin,
)
from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface


class TestMockRecordingInterface(unittest.TestCase, RecordingExtractorInterfaceTestMixin):
    data_interface_cls = MockRecordingInterface
    interface_kwargs = [
        dict(durations=[0.100]),
    ]
