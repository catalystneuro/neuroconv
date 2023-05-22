from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FolderPathType


class Suite2pSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for Suite2pSegmentationExtractor."""

    def __init__(self, folder_path: FolderPathType, combined: bool = False, plane_no: int = 0, verbose: bool = True):
        """

        Parameters
        ----------
        folder_path : FolderPathType
        combined : bool, default: False
        plane_no : int, default: 0
        verbose : bool, default: True
        """
        super().__init__(folder_path=folder_path, combined=combined, plane_no=plane_no)
        self.verbose = verbose
