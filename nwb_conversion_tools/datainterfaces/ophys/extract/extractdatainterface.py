from roiextractors import (
    CnmfeSegmentationExtractor,
    ExtractSegmentationExtractor,
    CaimanSegmentationExtractor,
    Suite2pSegmentationExtractor,
    SimaSegmentationExtractor,
)

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class ExtractSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for ExtractSegmentationExtractor"""

    SegX = ExtractSegmentationExtractor
