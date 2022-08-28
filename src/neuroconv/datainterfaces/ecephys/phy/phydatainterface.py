"""Authors: Heberto Mayorquin, Cody Baker."""
from typing import Optional

from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import FolderPathType


class PhySortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a PhySortingExtractor."""

    def __init__(
        self,
        folder_path: FolderPathType,
        exclude_cluster_groups: Optional[list] = None,
        verbose: bool = True,
        spikeextractors_backend: bool = False,
    ):
        if spikeextractors_backend:
            from spikeextractors import PhySortingExtractor

            self.Extractor = PhySortingExtractor
        super().__init__(folder_path=folder_path, exclude_cluster_groups=exclude_cluster_groups, verbose=verbose)
