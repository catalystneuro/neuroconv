from roiextractors import CnmfeSegmentationExtractor

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FilePathType


class CnmfeSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for CnmfeRecordingInterface."""

    SegX = CnmfeSegmentationExtractor

    def __init__(self, file_path: FilePathType, verbose: bool = True):

        super().__init__(file_path=file_path)
        self.verbose = verbose
