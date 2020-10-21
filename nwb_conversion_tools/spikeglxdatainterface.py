"""Authors: Cody Baker and Ben Dichter."""
from .baserecordingextractorinterface import BaseRecordingExtractorInterface
from spikeextractors import SpikeGLXRecordingExtractor


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    RX = SpikeGLXRecordingExtractor
