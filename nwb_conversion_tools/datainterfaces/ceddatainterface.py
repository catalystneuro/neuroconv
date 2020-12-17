"""Authors: Luiz Tauffer"""
import spikeextractors as se

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..json_schema_utils import get_schema_from_method_signature


class CEDRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a CEDRecordingExtractor."""

    RX = se.CEDRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the RecordingExtractor."""
        source_schema = get_schema_from_method_signature(
            class_method=cls.RX.__init__,
            exclude=['smrx_channel_ids']
        )
        source_schema.update(additionalProperties=True)
        source_schema['properties'].update(
            file_path=dict(
                type=source_schema['properties']['file_path']['type'],
                format="file",
                description="path to data file"
            )
        )
        return source_schema
