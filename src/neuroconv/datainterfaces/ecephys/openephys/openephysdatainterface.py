"""Authors: Heberto Mayorquin, Luiz Tauffer."""
from typing import Optional

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import get_schema_from_method_signature, FolderPathType


class OpenEphysRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface for converting OpenEphys data. Uses
    :py:class:`~spikeinterface.extractors.OpenEphysBinaryRecordingExtractor`."""

    ExtractorName = "OpenEphysBinaryRecordingExtractor"

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
        stub_test: bool = False,
        verbose: bool = True,
        spikeextractors_backend: bool = False,
    ):
        self.spikeextractors_backend = spikeextractors_backend
        if spikeextractors_backend:
            from spikeextractors import OpenEphysRecordingExtractor
            from spikeinterface.core.old_api_utils import OldToNewRecording

            self.Extractor = OpenEphysRecordingExtractor
            super().__init__(
                folder_path=folder_path, experiment_id=experiment_id, recording_id=recording_id, verbose=verbose
            )
            self.recording_extractor = OldToNewRecording(oldapi_recording_extractor=self.recording_extractor)
            # Remove when spikeinterface 0.95 is released, this has an int sampling rate that causes problems
            self.recording_extractor._sampling_frequency = float(self.recording_extractor.get_sampling_frequency())
        else:
            from spikeinterface.extractors import OpenEphysBinaryRecordingExtractor

            self.RX = OpenEphysBinaryRecordingExtractor
            super().__init__(folder_path=folder_path, verbose=verbose)

        if stub_test:
            self.subset_channels = [0, 1]

    def get_metadata(self):
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        import pyopenephys

        metadata = super().get_metadata()

        folder_path = self.source_data["folder_path"]
        fileobj = pyopenephys.File(foldername=folder_path)
        session_start_time = fileobj.experiments[0].datetime

        metadata["NWBFile"].update(session_start_time=session_start_time)
        return metadata


class OpenEphysSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting OpenEphys spiking data."""

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
        from spikeextractors import OpenEphysSortingExtractor

        self.Extractor = OpenEphysSortingExtractor
        super().__init__(folder_path=str(folder_path), experiment_id=experiment_id, recording_id=recording_id)
