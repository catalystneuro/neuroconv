from roiextractors import SbxImagingExtractor, Hdf5ImagingExtractor, TiffImagingExtractor

from ....utils.json_schema import get_schema_from_method_signature
from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class TiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for TIffImagingExtractor"""

    IX = TiffImagingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(
            cls.IX.__init__,
            exclude=["channel_names"]
        )
        source_schema["properties"]["file_path"]["format"] = "file"
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff file."
        return source_schema