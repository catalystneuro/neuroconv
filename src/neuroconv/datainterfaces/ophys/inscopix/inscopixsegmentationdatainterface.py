from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class InscopixSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for Inscopix segmentation extractor."""

    display_name = "Inscopix Segmentation"
    associated_suffixes = (".mat",)
    info = "Interface for Inscopix segmentation data from Inscopix proprietary format."

    def __init__(self, file_path: FilePath, verbose: bool = False):
        super().__init__(file_path=file_path)
        self.verbose = verbose