from roiextractors import ExtractSegmentationExtractor

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FilePathType


class ExtractSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for ExtractSegmentationExtractor."""

    SegX = ExtractSegmentationExtractor

    def __init__(self, file_path: FilePathType):
        super().__init__(file_path=file_path)
