from roiextractors import TiffImagingExtractor

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class TiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for TIffImagingExtractor"""

    IX = TiffImagingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["format"] = "file"
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff file."
        return source_schema
