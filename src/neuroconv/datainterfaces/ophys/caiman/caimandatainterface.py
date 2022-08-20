from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FilePathType


class CaimanSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for CaimanSegmentationExtractor."""

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        super().__init__(file_path=file_path)
        self.verbose = verbose
