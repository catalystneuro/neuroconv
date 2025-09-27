from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class CnmfeSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for constrained non-negative matrix factorization (CNMFE) segmentation extractor."""

    display_name = "CNMFE Segmentation"
    associated_suffixes = (".mat",)
    info = "Interface for constrained non-negative matrix factorization (CNMFE) segmentation."

    def __init__(self, file_path: FilePath, verbose: bool = False):
        super().__init__(file_path=file_path)
        self.verbose = verbose

    def _initialize_extractor(self, interface_kwargs: dict):
        from roiextractors import CnmfeSegmentationExtractor

        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)  # Remove interface params

        return CnmfeSegmentationExtractor(**self.extractor_kwargs)
