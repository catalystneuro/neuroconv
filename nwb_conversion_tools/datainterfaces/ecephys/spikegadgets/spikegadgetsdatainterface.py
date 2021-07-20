"""Authors: Cody Baker."""
from typing import Union
from pathlib import Path

from spikeextractors import SpikeGadgetsRecordingExtractor

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils.json_schema import get_schema_from_method_signature

PathType = Union[str, Path]


class SpikeGadgetsRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting the SpikeGadgets format."""

    RX = SpikeGadgetsRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(cls.__init__)
        source_schema["properties"]["filename"].update(format="file", description="Path to SpikeGadgets (.rec) file.")
        return source_schema

    def __init__(self, filename: PathType):
        super().__init__(filename=filename)
