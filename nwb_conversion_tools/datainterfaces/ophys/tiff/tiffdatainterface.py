from roiextractors import TiffImagingExtractor

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils.json_schema import FilePathType, FloatType, ArrayType


class TiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for TIffImagingExtractor."""

    IX = TiffImagingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff file."
        return source_schema

    def __init__(self, file_path: FilePathType, sampling_frequency: FloatType, channel_names: ArrayType = None):
        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency, channel_names=channel_names)
