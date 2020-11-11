"""Authors: Cody Baker and Ben Dichter."""
from spikeextractors import SpikeGLXRecordingExtractor

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting the SpikeGLX format."""

    RX = SpikeGLXRecordingExtractor
