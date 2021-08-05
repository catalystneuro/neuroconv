from roiextractors import (
    CnmfeSegmentationExtractor,
    ExtractSegmentationExtractor,
    CaimanSegmentationExtractor,
    Suite2pSegmentationExtractor,
    SimaSegmentationExtractor,
)

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class Suite2pSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for Suite2pSegmentationExtractor"""

    SegX = Suite2pSegmentationExtractor
