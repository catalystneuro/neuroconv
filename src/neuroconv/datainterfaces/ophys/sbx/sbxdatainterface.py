from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FilePathType, FloatType


class SbxImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for SbxImagingExtractor."""

    def __init__(self, file_path: FilePathType, sampling_frequency: FloatType = None, verbose: bool = True):
        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency, verbose=verbose)

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata["Ophys"]["Device"][0]["description"] = "Scanbox imaging"
        return metadata
