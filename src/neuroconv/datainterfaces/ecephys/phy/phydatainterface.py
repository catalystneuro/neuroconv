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
        """
        super().__init__(folder_path=folder_path, exclude_cluster_groups=exclude_cluster_groups, verbose=verbose)
