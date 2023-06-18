from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FilePathType


class SbxImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for SbxImagingExtractor."""

    def __init__(self, file_path: FilePathType, sampling_frequency: float = None, verbose: bool = True):
        """
        Parameters
        ----------
        file_path : FilePathType
            Path to .sbx file.
        sampling_frequency : float, optional
        verbose : bool, default: True
        """

        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency, verbose=verbose)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        metadata["Ophys"]["Device"][0]["description"] = "Scanbox imaging"
        return metadata
