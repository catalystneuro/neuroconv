from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FilePathType, FolderPathType


class TiffImagingInterface(BaseImagingExtractorInterface):
    """Interface for multi-page TIFF files."""

    display_name = "TIFF Imaging"
    associated_suffixes = (".tif", ".tiff")
    info = "Interface for multi-page TIFF files."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff file."
        return source_schema

    def __init__(self, file_path: FilePathType, sampling_frequency: float, verbose: bool = True):
        """
        Initialize reading of TIFF file.

        Parameters
        ----------
        file_path : FilePathType
        sampling_frequency : float
        verbose : bool, default: True
        """
        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency, verbose=verbose)


class MultiPageMultiTiffImagingInterface(BaseImagingExtractorInterface):
    """Interface for multi-page multi-TIFF files."""

    display_name = "Multi-Page Multi-TIFF"
    associated_suffixes = (".tif", ".tiff")
    info = "Interface for multiple multi-page TIFF files that have been split."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff directory."
        return source_schema

    def __init__(self, folder_path: FolderPathType, pattern: str, sampling_frequency: float, verbose: bool = True):
        """
        Initialize reading of multi-page multi-TIFF file.

        Parameters
        ----------
        folder_path : FolderPathType
        pattern: str
            fstring-style pattern to match the TIFF files. Must use named variables.
        sampling_frequency : float
        verbose : bool, default: True
        """
        super().__init__(
            folder_path=folder_path, pattern=pattern, sampling_frequency=sampling_frequency, verbose=verbose
        )
