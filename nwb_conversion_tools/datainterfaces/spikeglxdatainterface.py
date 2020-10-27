"""Authors: Cody Baker and Ben Dichter."""
from spikeextractors import SpikeGLXRecordingExtractor

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    RX = SpikeGLXRecordingExtractor
