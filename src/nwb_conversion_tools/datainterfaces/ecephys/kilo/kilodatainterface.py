"""Authors: Cody Baker."""
from typing import Optional

from spikeinterface.extractors import KiloSortSortingExtractor

from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import FolderPathType


class KiloSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a KiloSortingExtractor from spikeinterface."""

    SX = KiloSortSortingExtractor

    def __init__(self, folder_path: FolderPathType, keep_good_only: bool = False):
        """
        Load and prepare sorting data for kilosort

        Parameters
        ----------
        folder_path: str or Path
            Path to the output Phy folder (containing the params.py)
        keep_good_only: bool
            If True, only Kilosort-labeled 'good' units are returned
        """
        super().__init__(folder_path=folder_path, keep_good_only=keep_good_only)
