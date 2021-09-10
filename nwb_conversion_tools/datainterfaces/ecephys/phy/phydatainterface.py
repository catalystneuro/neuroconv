"""Authors: Cody Baker."""
from typing import Optional

import spikeextractors as se

from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils.json_schema import FolderPathType


class PhySortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a PhySortingExtractor."""

    SX = se.PhySortingExtractor

    def __init__(self, folder_path: FolderPathType, exclude_cluster_groups: Optional[list] = None):
        super().__init__(folder_path=folder_path, exclude_cluster_groups=exclude_cluster_groups)
