"""Authors: Heberto Mayorquin, Cody Baker."""
from typing import Optional

from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import FolderPathType


class PhySortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting Phy data. Uses
    :py:class:`~spikeinterface.extractors.PhySortingExtractor`."""

    def __init__(
        self,
        folder_path: FolderPathType,
        exclude_cluster_groups: Optional[list] = None,
        verbose: bool = True,
        spikeextractors_backend: bool = False,
    ):
        """
        Initialize a PhySortingInterface.

        Parameters
        ----------
        folder_path: str or Path
            Path to the output Phy folder (containing the params.py).
        exclude_cluster_groups: list of str | str, optional
            Cluster groups to exclude (e.g. "noise" or ["noise", "mua"]).
        verbose: bool
        spikeextractors_backend: bool
        """
        if spikeextractors_backend:
            from spikeextractors import PhySortingExtractor

            self.Extractor = PhySortingExtractor
        super().__init__(folder_path=folder_path, exclude_cluster_groups=exclude_cluster_groups, verbose=verbose)
