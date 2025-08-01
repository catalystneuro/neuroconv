from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class CaimanSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for CaimanSegmentationExtractor."""

    display_name = "CaImAn Segmentation"
    associated_suffixes = (".hdf5",)
    info = "Interface for CaImAn segmentation data."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the CaImAn segmentation interface.

        Returns
        -------
        dict
            The schema dictionary containing input parameters and descriptions
            for initializing the CaImAn segmentation interface.
        """
        source_metadata = super().get_source_schema()
        source_metadata["properties"]["file_path"]["description"] = "Path to .hdf5 file."
        return source_metadata

    def __init__(self, file_path: FilePath, verbose: bool = False):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to .hdf5 file.
        verbose : bool, default False
            Whether to print progress
        """
        super().__init__(file_path=file_path)
        self.verbose = verbose
