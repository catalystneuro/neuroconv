from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FilePathType


class CnmfeSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for constrained non-negative matrix factorization (CNMFE) segmentation extractor."""

    help = "Interface for constrained non-negative matrix factorization (CNMFE) segmentation."
    display_name = "CNMFE Segmentation"

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        super().__init__(file_path=file_path)
        self.verbose = verbose
