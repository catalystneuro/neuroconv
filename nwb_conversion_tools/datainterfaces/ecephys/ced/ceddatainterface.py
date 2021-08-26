"""Authors: Luiz Tauffer"""
import spikeextractors as se

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils.json_schema import get_schema_from_method_signature, FilePathType


class CEDRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a CEDRecordingExtractor."""

    RX = se.CEDRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the RecordingExtractor."""
        source_schema = get_schema_from_method_signature(class_method=cls.__init__, exclude=["smrx_channel_ids"])
        source_schema.update(additionalProperties=True)
        source_schema["properties"]["file_path"].update(description="Path to CED data file.")
        return source_schema

    def __init__(self, file_path: FilePathType):
        super().__init__(file_path=file_path)

    @classmethod
    def get_all_channels_info(cls, file_path: FilePathType):
        return cls.RX.get_all_channels_info(file_path)
