from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FilePathType


class TiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for TiffImagingExtractor."""

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
