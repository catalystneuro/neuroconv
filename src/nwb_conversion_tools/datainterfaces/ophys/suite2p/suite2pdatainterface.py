from roiextractors import Suite2pSegmentationExtractor


from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FilePathType, IntType


class Suite2pSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for Suite2pSegmentationExtractor."""

    SegX = Suite2pSegmentationExtractor

    def __init__(self, file_path: FilePathType, combined: bool = False, plane_no: IntType = 0):
        super().__init__(file_path=file_path, combined=combined, plane_no=plane_no)
