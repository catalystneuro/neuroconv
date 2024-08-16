from pathlib import Path
from typing import Literal, Optional

import numpy as np
from pynwb.file import NWBFile

from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import DeepDict, FolderPathType


class PhySortingInterface(BaseSortingExtractorInterface):
    """
    Primary data interface class for converting Phy data. Uses
    :py:class:`~spikeinterface.extractors.PhySortingExtractor`.
    """

    display_name = "Phy Sorting"
    associated_suffixes = (".npy",)
    info = "Interface for Phy sorting data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["exclude_cluster_groups"]["items"] = dict(type="string")
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to the output Phy folder (containing the params.py)."
        return source_schema

    def get_max_channel(self):
        folder_path = Path(self.source_data["folder_path"])

        templates = np.load(str(folder_path / "templates.npy"))
        channel_map = np.load(str(folder_path / "channel_map.npy")).T
        whitening_mat_inv = np.load(str(folder_path / "whitening_mat_inv.npy"))
        templates_unwh = templates @ whitening_mat_inv

        cluster_ids = self.sorting_extractor.get_property("original_cluster_id")
        templates = templates_unwh[cluster_ids]

        max_over_time = np.max(templates, axis=1)
        idx_max_channel = np.argmax(max_over_time, axis=1)
        max_channel = channel_map[idx_max_channel].ravel()

        return max_channel

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

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[DeepDict] = None,
        stub_test: bool = False,
        write_ecephys_metadata: bool = False,
        write_as: Literal["units", "processing"] = "units",
        units_name: str = "units",
        units_description: str = "Imported from Phy",
        include_max_channel: bool = True,
    ):
        if include_max_channel and "max_channel" not in self.sorting_extractor.get_property_keys():
            max_channels = self.get_max_channel()
            self.sorting_extractor.set_property("max_channel", max_channels)

        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            write_ecephys_metadata=write_ecephys_metadata,
            write_as=write_as,
            units_name=units_name,
            units_description=units_description,
        )

        return nwbfile
