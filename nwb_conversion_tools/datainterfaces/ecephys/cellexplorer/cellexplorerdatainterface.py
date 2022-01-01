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

    def __init__(self, file_path: FilePathType):
        super().__init__(spikes_matfile_path=file_path)
        self.source_data = dict(file_path=file_path)

        session_path = Path(file_path).parent
        session_id = session_path.stem
        spikes_cellinfo_file_path = session_path / f"{session_id}.spikes.cellinfo.mat"
        if spikes_cellinfo_file_path.is_file():
            cell_info = loadmat(spikes_cellinfo_file_path).get("spikes", np.empty(0))
            cell_info_fields = cell_info.dtype.names
            unit_ids = self.sorting_extractor.get_unit_ids()
            if "cluID" in cell_info_fields:
                for unit_id, value in zip(unit_ids, [int(x) for x in cell_info["cluID"][0][0][0]]):
                    self.sorting_extractor.set_unit_property(unit_id=unit_id, property_name="clu_id", value=value)
            if "shankID" in cell_info_fields:
                for unit_id, value in zip(unit_ids, [f"Group{x}" for x in cell_info["shankID"][0][0][0]]):
                    self.sorting_extractor.set_unit_property(unit_id=unit_id, property_name="group_id", value=value)
            if "region" in cell_info_fields:
                for unit_id, value in zip(unit_ids, [str(x[0]) for x in cell_info["region"][0][0][0]]):
                    self.sorting_extractor.set_unit_property(unit_id=unit_id, property_name="location", value=value)

        celltype_mapping = {"pE": "excitatory", "pI": "inhibitory", "[]": "unclassified"}
        celltype_file_path = session_path / f"{session_id}.CellClass.cellinfo.mat"
        if celltype_file_path.is_file():
            celltype_info = loadmat(celltype_file_path).get("CellClass", np.empty(0))
            if "label" in celltype_info.dtype.names:
                for unit_id, value in zip(
                    unit_ids, [str(celltype_mapping[str(x[0])]) for x in celltype_info["label"][0][0][0]]
                ):
                    self.sorting_extractor.set_unit_property(unit_id=unit_id, property_name="cell_type", value=value)

    def get_metadata(self):
        session_path = Path(self.source_data["file_path"]).parent
        session_id = session_path.stem
        # TODO: add condition for retrieving ecephys metadata if no recording or lfp are included in conversion
        metadata = dict(NWBFile=dict(session_id=session_id))

        unit_properties = []
        cellinfo_file_path = session_path / f"{session_id}.spikes.cellinfo.mat"
        if cellinfo_file_path.is_file():
            cell_info = loadmat(cellinfo_file_path).get("spikes", np.empty(0))
            cell_info_fields = cell_info.dtype.names
            if "cluID" in cell_info_fields:
                unit_properties.append(
                    dict(
                        name="clu_id",
                        description="0-indexed id of cluster identified from the shank.",
                    )
                )
            if "shankID" in cell_info_fields:
                unit_properties.append(
                    dict(
                        name="group_id",
                        description="The electrode group ID that each unit was identified by.",
                    )
                )
            if "region" in cell_info_fields:
                unit_properties.append(
                    dict(
                        name="location",
                        description="Brain region where each unit was detected.",
                    )
                )

        celltype_filepath = session_path / f"{session_id}.CellClass.cellinfo.mat"
        if celltype_filepath.is_file():
            celltype_info = loadmat(celltype_filepath).get("CellClass", np.empty(0))
            if "label" in celltype_info.dtype.names:
                unit_properties.append(
                    dict(
                        name="cell_type",
                        description="Type of cell this has been classified as.",
                    )
                )
        metadata.update(Ecephys=dict(UnitProperties=unit_properties))
        return metadata
