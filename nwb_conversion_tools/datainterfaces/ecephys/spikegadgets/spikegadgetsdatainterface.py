"""Authors: Cody Baker."""
from typing import Union, Optional
from pathlib import Path

from spikeextractors import SpikeGadgetsRecordingExtractor, load_probe_file

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils.json_schema import get_schema_from_method_signature

PathType = Union[str, Path]
OptionalPathType = Optional[PathType]


class SpikeGadgetsRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting the SpikeGadgets format."""

    RX = SpikeGadgetsRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(cls.__init__)
        source_schema["properties"]["filename"].update(format="file", description="Path to SpikeGadgets (.rec) file.")
        source_schema["properties"]["probe_file_path"].update(
            format="file", description="Optional path to a probe (.prb) file describing electrode features."
        )
        return source_schema

    def __init__(self, filename: PathType, probe_file_path: OptionalPathType = None):
        super().__init__(filename=filename)
        if probe_file_path is not None:
            self.recording_extractor = load_probe_file(recording=self.recording_extractor, probe_file=probe_file_path)
