from abc import ABC

from roiextractors import CnmfeSegmentationExtractor, ExtractSegmentationExtractor, \
    CaimanSegmentationExtractor, Suite2pSegmentationExtractor, SimaSegmentationExtractor

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class CnmfeSegmentationInterface(BaseSegmentationExtractorInterface, ABC):
    """Data interface for CnmfeRecordingInterface"""

    SegX = CnmfeSegmentationExtractor


class ExtractSegmentationInterface(BaseSegmentationExtractorInterface, ABC):
    """Data interface for ExtractSegmentationExtractor"""

    SegX = ExtractSegmentationExtractor


class CaimanSegmentationInterface(BaseSegmentationExtractorInterface, ABC):
    """Data interface for CaimanSegmentationExtractor"""

    SegX = CaimanSegmentationExtractor


class Suite2pSegmentationInterface(BaseSegmentationExtractorInterface, ABC):
    """Data interface for Suite2pSegmentationExtractor"""

    SegX = Suite2pSegmentationExtractor


class SimaSegmentationInterface(BaseSegmentationExtractorInterface, ABC):
    """Data interface for SimaSegmentationExtractor"""

    SegX = SimaSegmentationExtractor
