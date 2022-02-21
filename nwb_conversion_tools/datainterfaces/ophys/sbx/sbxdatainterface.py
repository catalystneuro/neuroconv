from roiextractors import SbxImagingExtractor

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils.json_schema import FilePathType, FloatType


class SbxImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for SbxImagingExtractor."""

    IX = SbxImagingExtractor

    def __init__(self, file_path: FilePathType, sampling_frequency: FloatType = None):
        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency)

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata["Ophys"]["Device"][0]["description"] = "Scanbox imaging"
        return metadata
