from roiextractors import (
    CnmfeSegmentationExtractor,
    ExtractSegmentationExtractor,
    CaimanSegmentationExtractor,
    Suite2pSegmentationExtractor,
    SimaSegmentationExtractor,
)

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class SimaSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for SimaSegmentationExtractor"""

    SegX = SimaSegmentationExtractor
