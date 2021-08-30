from roiextractors import CnmfeSegmentationExtractor

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class CnmfeSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for CnmfeRecordingInterface"""

    SegX = CnmfeSegmentationExtractor
