from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import FolderPathType, get_schema_from_method_signature


class OpenEphysSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting OpenEphys spiking data."""

    @classmethod
    def get_source_schema(cls) -> dict:
        """Compile input schema for the SortingExtractor."""
        metadata_schema = get_schema_from_method_signature(
            method=cls.__init__, exclude=["recording_id", "experiment_id"]
        )
        metadata_schema["properties"]["folder_path"].update(description="Path to directory containing OpenEphys files.")
        metadata_schema["additionalProperties"] = False
        return metadata_schema

    def __init__(self, folder_path: FolderPathType, experiment_id: int = 0, recording_id: int = 0):
        from spikeextractors import OpenEphysSortingExtractor

        self.Extractor = OpenEphysSortingExtractor
        super().__init__(folder_path=str(folder_path), experiment_id=experiment_id, recording_id=recording_id)
