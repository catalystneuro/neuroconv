"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

import spikeextractors as se
from scipy.io import loadmat
import numpy as np

from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils.json_schema import FilePathType


class CellExplorerSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting Cell Explorer spiking data."""

    SX = se.CellExplorerSortingExtractor

    def __init__(self, spikes_matfile_path: FilePathType):
        super().__init__(spikes_matfile_path=spikes_matfile_path)

    def get_metadata(self):
        session_path = Path(self.source_data["spikes_matfile_path"]).parent
        session_id = session_path.stem
        # TODO: add condition for retrieving ecephys metadata if no recoring or lfp are included in conversion
        metadata = dict(NWBFile=dict(session_id=session_id))

        unit_properties = []
        cell_filepath = session_path / f"{session_id}.spikes.cellinfo.mat"
        if cell_filepath.is_file():
            cell_info = loadmat(cell_filepath).get("spikes", np.empty(0))
            cell_info_fields = cell_info.dtype.names
            if "cluID" in cell_info_fields:
                unit_properties.append(
                    dict(
                        name="shank_id",
                        description="0-indexed id of cluster identified from the shank.",
                        # - 2 b/c the 0 and 1 IDs from each shank have been removed
                        data=[int(x - 2) for x in cell_info["cluID"][0][0][0]],
                    )
                )
            if "shankID" in cell_info_fields:
                unit_properties.append(
                    dict(
                        name="electrode_group",
                        description="The electrode group that each unit was identified by.",
                        data=[f"shank{x}" for x in cell_info["shankID"][0][0][0]],
                    )
                )
            if "region" in cell_info_fields:
                unit_properties.append(
                    dict(
                        name="location",
                        description="Brain region where each unit was detected.",
                        data=[str(x[0]) for x in cell_info["region"][0][0][0]],
                    )
                )

        celltype_mapping = {"pE": "excitatory", "pI": "inhibitory", "[]": "unclassified"}
        celltype_filepath = session_path / f"{session_id}.CellClass.cellinfo.mat"
        if celltype_filepath.is_file():
            celltype_info = loadmat(celltype_filepath).get("CellClass", np.empty(0))
            if "label" in celltype_info.dtype.names:
                unit_properties.append(
                    dict(
                        name="cell_type",
                        description="Type of cell this has been classified as.",
                        data=[str(celltype_mapping[str(x[0])]) for x in celltype_info["label"][0][0][0]],
                    )
                )
        metadata.update(UnitProperties=unit_properties)
        return metadata
