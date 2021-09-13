from roiextractors import CaimanSegmentationExtractor

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils.json_schema import FilePathType


class CaimanSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for CaimanSegmentationExtractor."""

    SegX = CaimanSegmentationExtractor

    def __init__(self, file_path: FilePathType):
        super().__init__(file_path=file_path)
