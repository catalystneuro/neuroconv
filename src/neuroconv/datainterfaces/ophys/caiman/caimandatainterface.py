from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import FilePathType


class CaimanSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for CaimanSegmentationExtractor."""

    display_name = "CaImAn Segmentation"
    associated_suffixes = (".hdf5",)
    info = "Interface for Caiman segmentation data."

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """

        Parameters
        ----------
        file_path : FilePathType
            Path to .hdf5 file.
        verbose : bool, default True
            Whether to print progress
        """
        super().__init__(file_path=file_path)
        self.verbose = verbose
