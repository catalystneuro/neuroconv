from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FolderPathType, IntType


class Suite2pSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for Suite2pSegmentationExtractor."""

    def __init__(
        self, folder_path: FolderPathType, combined: bool = False, plane_no: IntType = 0, verbose: bool = True
    ):
        super().__init__(folder_path=folder_path, combined=combined, plane_no=plane_no)
        self.verbose = verbose
