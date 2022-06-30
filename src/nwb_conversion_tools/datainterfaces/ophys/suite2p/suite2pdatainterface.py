from roiextractors import Suite2pSegmentationExtractor


from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FolderPathType, IntType


class Suite2pSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for Suite2pSegmentationExtractor."""

    SegX = Suite2pSegmentationExtractor

    def __init__(self, folder_path: FolderPathType, combined: bool = False, plane_no: IntType = 0):
        super().__init__(folder_path=folder_path, combined=combined, plane_no=plane_no)
