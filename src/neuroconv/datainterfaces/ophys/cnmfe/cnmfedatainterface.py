from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class CnmfeSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for constrained non-negative matrix factorization (CNMFE) segmentation extractor."""

    display_name = "CNMFE Segmentation"
    associated_suffixes = (".mat",)
    info = "Interface for constrained non-negative matrix factorization (CNMFE) segmentation."

    def __init__(self, file_path: FilePath, verbose: bool = False, metadata_key: str = "default"):
        """

        Parameters
        ----------
        file_path : FilePath
            Path to .mat file containing CNMF-E segmentation data.
        verbose : bool, optional
            Whether to print progress. Default is False.
        metadata_key : str, optional
            The key to use for organizing metadata in the new dictionary structure.
            This single key will be used for ImageSegmentation.
            Default is "default".
        """
        super().__init__(file_path=file_path, metadata_key=metadata_key)
        self.verbose = verbose
