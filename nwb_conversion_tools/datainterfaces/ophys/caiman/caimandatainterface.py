from roiextractors import (
    CnmfeSegmentationExtractor,
    ExtractSegmentationExtractor,
    CaimanSegmentationExtractor,
    Suite2pSegmentationExtractor,
    SimaSegmentationExtractor,
)

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class CaimanSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for CaimanSegmentationExtractor"""

    SegX = CaimanSegmentationExtractor
