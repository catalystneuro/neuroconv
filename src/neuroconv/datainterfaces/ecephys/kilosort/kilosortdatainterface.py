from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import FolderPathType


class KiloSortSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a KiloSortingExtractor from spikeinterface."""

    display_name = "KiloSort Sorting"
    associated_suffixes = (".npy",)
    info = "Interface for KiloSort sorting data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to the output Phy folder (containing the params.py)"
        return source_schema

    def __init__(
        self,
        folder_path: FolderPathType,
        keep_good_only: bool = False,
        verbose: bool = True,
    ):
        """
        Load and prepare sorting data for kilosort

        Parameters
        ----------
        folder_path: str or Path
            Path to the output Phy folder (containing the params.py)
        keep_good_only: bool, default: False
            If True, only Kilosort-labeled 'good' units are returned
        verbose: bool, default: True
        """
        super().__init__(folder_path=folder_path, keep_good_only=keep_good_only, verbose=verbose)
