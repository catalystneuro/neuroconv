from roiextractors import ExtractSegmentationExtractor
from roiextractors.extraction_tools import FloatType

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FilePathType


class ExtractSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for ExtractSegmentationExtractor."""

    SegX = ExtractSegmentationExtractor

    def __init__(self, file_path: FilePathType, sampling_frequency: FloatType, verbose: bool = True):
        self.verbose = verbose
        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency)
