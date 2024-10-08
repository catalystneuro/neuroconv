from roiextractors.extraction_tools import PathType
from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class MinianSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for MinianSegmentationExtractor."""

    display_name = "Minian Segmentation"
    associated_suffixes = (".zarr",)
    info = "Interface for Minian segmentation data."

    
    @classmethod
    def get_source_schema(cls) -> dict:
        source_metadata = super().get_source_schema()
        source_metadata["properties"]["folder_path"]["description"] = "Path to .zarr output."
        return source_metadata

    def __init__(self, folder_path: PathType, verbose: bool = True):
        """

        Parameters
        ----------
        folder_path : PathType
            Path to .zarr path.
        verbose : bool, default True
            Whether to print progress
        """
        super().__init__(folder_path=folder_path)
        self.verbose = verbose
