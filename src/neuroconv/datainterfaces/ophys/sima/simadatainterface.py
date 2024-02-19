from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FilePathType


class SimaSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for SimaSegmentationExtractor."""

    display_name = "SIMA Segmentation"
    associated_suffixes = (".sima",)
    info = "Interface for SIMA segmentation."

    def __init__(self, file_path: FilePathType, sima_segmentation_label: str = "auto_ROIs"):
        """

        Parameters
        ----------
        file_path : FilePathType
        sima_segmentation_label : str, default: "auto_ROIs"
        """
        super().__init__(file_path=file_path, sima_segmentation_label=sima_segmentation_label)
