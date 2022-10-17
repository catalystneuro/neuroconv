"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

import scipy
import numpy as np

from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....tools import get_package
from ....utils import FilePathType


class CellExplorerSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting Cell Explorer spiking data."""

    ExtractorModuleName = "spikeextractors"

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        hdf5storage = get_package(package_name="hdf5storage")

        super().__init__(spikes_matfile_path=file_path, verbose=verbose)
        self.source_data = dict(file_path=file_path)
        spikes_matfile_path = Path(file_path)

        session_path = Path(file_path).parent
        session_id = session_path.stem

        assert (
            spikes_matfile_path.is_file()
        ), f"The file_path should point to an existing .spikes.cellinfo.mat file ({spikes_matfile_path})"

        try:
            spikes_mat = scipy.io.loadmat(file_name=str(spikes_matfile_path))
            self.read_spikes_info_with_scipy = True
        except NotImplementedError:
            spikes_mat = hdf5storage.loadmat(file_name=str(spikes_matfile_path))
            self.read_spikes_info_with_scipy = False
        cell_info = spikes_mat.get("spikes", np.empty(0))
        self.cell_info_fields = cell_info.dtype.names

        if self.read_spikes_info_with_scipy:
            unit_ids = self.sorting_extractor.get_unit_ids()
            if "cluID" in self.cell_info_fields:
                for unit_id, value in zip(unit_ids, [int(x) for x in cell_info["cluID"][0][0][0]]):
                    self.sorting_extractor.set_unit_property(unit_id=unit_id, property_name="clu_id", value=value)
            if "shankID" in self.cell_info_fields:
                for unit_id, value in zip(unit_ids, [f"Group{x}" for x in cell_info["shankID"][0][0][0]]):
                    self.sorting_extractor.set_unit_property(unit_id=unit_id, property_name="group_id", value=value)
            if "region" in self.cell_info_fields:
                for unit_id, value in zip(unit_ids, [str(x[0]) for x in cell_info["region"][0][0][0]]):
                    self.sorting_extractor.set_unit_property(unit_id=unit_id, property_name="location", value=value)
        else:  # Logic for hdf5storage
            unit_ids = self.sorting_extractor.get_unit_ids()
            if "cluID" in self.cell_info_fields:
                for unit_id, value in zip(unit_ids, [int(x) for x in cell_info["cluID"][0][0]]):
                    self.sorting_extractor.set_unit_property(unit_id=unit_id, property_name="clu_id", value=value)
            if "shankID" in self.cell_info_fields:
                for unit_id, value in zip(unit_ids, [f"Group{x}" for x in cell_info["shankID"][0][0]]):
                    self.sorting_extractor.set_unit_property(unit_id=unit_id, property_name="group_id", value=value)
            if "region" in self.cell_info_fields:
                for unit_id, value in zip(unit_ids, [str(x[0]) for x in cell_info["region"][0]][0]):
                    self.sorting_extractor.set_unit_property(unit_id=unit_id, property_name="location", value=value)
        celltype_mapping = {"pE": "excitatory", "pI": "inhibitory", "[]": "unclassified"}
        celltype_file_path = session_path / f"{session_id}.CellClass.cellinfo.mat"
        if celltype_file_path.is_file():
            celltype_info = scipy.io.loadmat(celltype_file_path).get("CellClass", np.empty(0))
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
            cell_info_fields = self.cell_info_fields
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
            celltype_info = scipy.io.loadmat(celltype_filepath).get("CellClass", np.empty(0))
            if "label" in celltype_info.dtype.names:
                unit_properties.append(
                    dict(
                        name="cell_type",
                        description="Type of cell this has been classified as.",
                    )
                )
        metadata.update(Ecephys=dict(UnitProperties=unit_properties))
        return metadata
