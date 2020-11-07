"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class IntanRecordingInterface(BaseRecordingExtractorInterface):
    RX = se.IntanRecordingExtractor
