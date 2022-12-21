"""Authors: Heberto Mayorquin, Cody Baker."""
from typing import Optional, List

from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import FolderPathType


class PhySortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting Phy data. Uses
    :py:class:`~spikeinterface.extractors.PhySortingExtractor`."""

    def __init__(
        self,
        folder_path: FolderPathType,
        exclude_cluster_groups: Optional[List[str]] = None,
        verbose: bool = True,
        spikeextractors_backend: bool = False,
    ):
        """
        Initialize a PhySortingInterface.

        Parameters
        ----------
        folder_path : str or Path
            Path to the output Phy folder (containing the params.py).
        exclude_cluster_groups : str or list of str, optional
            Cluster groups to exclude (e.g. "noise" or ["noise", "mua"]).
        verbose : bool, default: True
        spikeextractors_backend : bool, default: False
        """
        if spikeextractors_backend:
            from spikeextractors import PhySortingExtractor

            self.Extractor = PhySortingExtractor
        super().__init__(folder_path=folder_path, exclude_cluster_groups=exclude_cluster_groups, verbose=verbose)
