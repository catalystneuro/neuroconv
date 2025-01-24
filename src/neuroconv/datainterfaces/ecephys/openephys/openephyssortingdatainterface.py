from pydantic import DirectoryPath, validate_call

from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import get_json_schema_from_method_signature


class OpenEphysSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting OpenEphys spiking data."""

    display_name = "OpenEphys Sorting"
    associated_suffixes = (".spikes",)
    info = "Interface for converting legacy OpenEphys sorting data."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Compile input schema for the SortingExtractor.

        Returns
        -------
        dict
            The schema dictionary containing input parameters and descriptions
            for initializing the SortingExtractor.
        """
        metadata_schema = get_json_schema_from_method_signature(
            method=cls.__init__, exclude=["recording_id", "experiment_id"]
        )
        metadata_schema["properties"]["folder_path"].update(
            description="Path to directory containing OpenEphys .spikes files."
        )
        metadata_schema["additionalProperties"] = False
        return metadata_schema

    @validate_call
    def __init__(self, folder_path: DirectoryPath, experiment_id: int = 0, recording_id: int = 0):
        from spikeextractors import OpenEphysSortingExtractor

        self.Extractor = OpenEphysSortingExtractor
        super().__init__(folder_path=str(folder_path), experiment_id=experiment_id, recording_id=recording_id)
