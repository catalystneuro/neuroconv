from roiextractors import (
    CnmfeSegmentationExtractor,
    ExtractSegmentationExtractor,
    CaimanSegmentationExtractor,
    Suite2pSegmentationExtractor,
    SimaSegmentationExtractor,
)

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class CnmfeSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for CnmfeRecordingInterface"""

    SegX = CnmfeSegmentationExtractor
