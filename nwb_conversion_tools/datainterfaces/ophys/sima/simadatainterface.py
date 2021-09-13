from roiextractors import SimaSegmentationExtractor

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils.json_schema import FilePathType


class SimaSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for SimaSegmentationExtractor."""

    SegX = SimaSegmentationExtractor

    def __init__(self, file_path: FilePathType, sima_segmentation_label: str = "auto_ROIs"):
        super().__init__(file_path=file_path, sima_segmentation_label=sima_segmentation_label)
