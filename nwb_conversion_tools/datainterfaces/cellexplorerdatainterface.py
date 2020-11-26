"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

import spikeextractors as se
from scipy.io import loadmat

from ..basesortingextractorinterface import BaseSortingExtractorInterface


class CellExplorerSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting Cell Explorer spiking data."""

    # TODO: technically, there is separately stored spiking information specific to the cell explorer format
    # but we would need to make a sorting extractor for that. Defaulting to using the Neuroscope for now.
    SX = se.NeuroscopeMultiSortingExtractor

    def get_metadata(self):
        """Auto-populates spiking unit metadata."""
        session_path = Path(self.source_data['folder_path'])
        session_id = session_path.stem
        # TODO: add condition for retrieving ecephys metadata if no recoring or lfp are included in conversion

        unit_properties = []
        cell_filepath = session_path / f"{session_id}.spikes.cellinfo.mat"
        if cell_filepath.is_file():
            cell_info = loadmat(cell_filepath).get('spikes', dict())
            if 'UID' in cell_info:
                unit_properties.append(
                    dict(
                        name="global_id",
                        description="Global id for this cell for the entire experiment.",
                        data=[int(x) for x in cell_info['UID'][0][0][0]]
                    )
                )
            if 'cluID' in cell_info:
                unit_properties.append(
                    dict(
                        name="shank_id",
                        description="0-indexed id of cluster identified from the shank.",
                        # - 2 b/c the 0 and 1 IDs from each shank have been removed
                        data=[int(x - 2) for x in cell_info['cluID'][0][0][0]]
                    )
                )
            if 'shankID' in cell_info:
                unit_properties.append(
                    dict(
                        name="electrode_group",
                        description="The electrode group that each unit was identified by.",
                        data=[f"shank{x}" for x in cell_info['shankID'][0][0][0]]
                    )
                )
            if 'region' in cell_info:
                unit_properties.append(
                    dict(
                        name="region",
                        description="Brain region where each unit was detected.",
                        data=[str(x[0]) for x in cell_info['region'][0][0][0]]
                    )
                )

        celltype_mapping = {'pE': "excitatory", 'pI': "inhibitory"}
        celltype_filepath = session_path / f"{session_id}.CellClass.cellinfo.mat"
        if celltype_filepath.is_file():
            celltype_info = loadmat(celltype_filepath).get('CellClass', dict())
            if 'label' in celltype_info:
                unit_properties.append(
                    dict(
                        name="cell_type",
                        description="Type of cell this has been classified as.",
                        data=[str(celltype_mapping[x[0]]) for x in celltype_info['label'][0][0][0]]
                    )
                )

        return dict(UnitProperties=unit_properties)
