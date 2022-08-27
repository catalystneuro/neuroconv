from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FilePathType, FloatType


class ExtractSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for ExtractSegmentationExtractor."""

    def __init__(self, file_path: FilePathType, sampling_frequency: FloatType, verbose: bool = True):
        self.verbose = verbose
        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency)
