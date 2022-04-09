"""Authors: Luiz Tauffer."""
import pytz
import spikeextractors as se
from typing import Optional

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import get_schema_from_method_signature, FolderPathType


class OpenEphysRecordingExtractorInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a OpenEphysRecordingExtractor."""

    RX = se.OpenEphysRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the RecordingExtractor."""
        source_schema = get_schema_from_method_signature(
            class_method=cls.__init__, exclude=["recording_id", "experiment_id", "stub_test"]
        )
        source_schema["properties"]["folder_path"]["description"] = "Path to directory containing OpenEphys files."
        return source_schema

    def __init__(
        self,
        folder_path: FolderPathType,
        experiment_id: Optional[int] = 0,
        recording_id: Optional[int] = 0,
        stub_test: Optional[bool] = False,
    ):
        super().__init__(folder_path=folder_path, experiment_id=experiment_id, recording_id=recording_id)
        if stub_test:
            self.subset_channels = [0, 1]

    def get_metadata(self):
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        metadata = super().get_metadata()

        # Open file and extract info
        session_start_time = self.recording_extractor._fileobj.experiments[0].datetime
        session_start_time_tzaware = pytz.timezone("EST").localize(session_start_time)

        metadata["NWBFile"] = dict(
            session_start_time=session_start_time_tzaware.strftime("%Y-%m-%dT%H:%M:%S"),
        )

        return metadata


class OpenEphysSortingExtractorInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting OpenEphys spiking data."""

    SX = se.OpenEphysSortingExtractor

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the SortingExtractor."""
        metadata_schema = get_schema_from_method_signature(
            class_method=cls.__init__, exclude=["recording_id", "experiment_id"]
        )
        metadata_schema["properties"]["folder_path"].update(description="Path to directory containing OpenEphys files.")
        metadata_schema["additionalProperties"] = False
        return metadata_schema

    def __init__(self, folder_path: FolderPathType, experiment_id: int = 0, recording_id: int = 0):
        super().__init__(folder_path=str(folder_path), experiment_id=experiment_id, recording_id=recording_id)
