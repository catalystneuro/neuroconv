import unittest

from spikeinterface import BaseRecording
from spikeinterface.core import generate_recording
from hdmf.testing import TestCase

from neuroconv.datainterfaces import SpikeGLXNIDQInterface


class DummySpikeGLXNIDQInterface(SpikeGLXNIDQInterface):
    def __init__(self, recording: BaseRecording):
        self.recording_extractor = recording


class TestSpikeGLXNIDQTTLParsing(TestCase):
    # @classmethod
    # def setUpClass(cls):
    #     class DummySpikeGLXNIDQInterface

    #     cls.interface = generate_recording

    def test_single_pulse(self):
        interface = DummySpikeGLXNIDQInterface(recording=generate_recording())

        event_times = interface.get_events_times_from_ttl(channel_id=0)


if __name__ == "__main__":
    unittest.main()
