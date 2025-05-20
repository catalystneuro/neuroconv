from pydantic import validate_call, FilePath

from neuroconv.datainterfaces.ophys.basesegmentationextractorinterface import (
    BaseSegmentationExtractorInterface,
)

class InscopixSegmentationInterface(BaseSegmentationExtractorInterface):
    """Conversion interface for Inscopix segmentation data."""

    display_name = "Inscopix Segmentation"
    associated_suffixes = (".isxd",)
    info = "Interface for handling Inscopix segmentation."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = True,
    ):
        """
        Initialize a new InscopixSegmentationInterface instance.
        Parameters
        ----------
        file_path : FilePathType
            Path to the Inscopix segmentation file (.isxd).
        verbose : bool, default: True
            Whether to print detailed information during processing.
        """
        super().__init__(file_path=file_path)
        self.verbose = verbose