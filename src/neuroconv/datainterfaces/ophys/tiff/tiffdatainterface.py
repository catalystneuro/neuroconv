from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FilePathType, FloatType


class TiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for TiffImagingExtractor."""

    @classmethod
    def get_source_schema(cls):
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff file."
        return source_schema

    def __init__(self, file_path: FilePathType, sampling_frequency: FloatType, verbose: bool = True):
        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency, verbose=verbose)
