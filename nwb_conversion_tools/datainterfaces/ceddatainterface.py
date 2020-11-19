"""Authors: Luiz Tauffer"""
import spikeextractors as se

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class CEDRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a CEDRecordingExtractor."""

    RX = se.CEDRecordingExtractor
