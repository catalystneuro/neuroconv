"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

import numpy as np
import spikeextractors as se
from lxml import etree as et
from scipy.io import loadmat

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface


def get_xml_file_path(data_file_path: str):
    """
    Infer the xml_file_path from the data_file_path (.dat or .eeg).

    Assumes the two are in the same folder and follow the session_id naming convention.
    """
    session_path = Path(data_file_path).parent
    session_id = session_path.stem
    return session_path / f"{session_id}.xml"


def get_xml(xml_file_path: str):
    """Auxiliary function for retrieving root of xml."""
    root = et.parse(str(xml_file_path.absolute())).getroot()

    return root


def get_sorted_shank_channels(xml_file_path: str):
    """."""
    root = get_xml(xml_file_path)
    shank_channels = [[int(channel.text)
                       for channel in group.find('channels')]
                      for group in root.find('spikeDetection').find('channelGroups').findall('group')]
    all_shank_channels = np.concatenate(shank_channels)

    return sorted(all_shank_channels)


class NeuroscopeRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeRecordingExtractor."""

    RX = se.NeuroscopeRecordingExtractor

    @staticmethod
    def get_ecephys_metadata(xml_file_path: str):
        """Auto-populates ecephys metadata from the xml_file_path inferred."""
        session_path = Path(xml_file_path).parent
        session_id = session_path.stem
        root = et.parse(str(xml_file_path.absolute())).getroot()
        shank_channels = [[int(channel.text)
                           for channel in group.find('channels')]
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')]
        sorted_shank_channels = get_sorted_shank_channels(xml_file_path=xml_file_path)
        shank_electrode_number = [x for channels in shank_channels for x, _ in enumerate(channels)]
        shank_group_name = [f"shank{n + 1}" for n, channels in enumerate(shank_channels) for _ in channels]

        ecephys_metadata = dict(
            Ecephys=dict(
                subset_channels=sorted_shank_channels,
                Device=[
                    dict(
                        description=session_id + '.xml'
                    )
                ],
                ElectrodeGroup=[
                    dict(
                        name=f'shank{n + 1}',
                        description=f"shank{n + 1} electrodes"
                    )
                    for n, _ in enumerate(shank_channels)
                ],
                Electrodes=[
                    dict(
                        name='shank_electrode_number',
                        description="0-indexed channel within a shank.",
                        data=shank_electrode_number
                    ),
                    dict(
                        name='group_name',
                        description="The name of the ElectrodeGroup this electrode is a part of.",
                        data=shank_group_name
                    )
                ],
                ElectricalSeries=dict(
                    name='ElectricalSeries',
                    description="Raw acquisition traces."
                )
            )
        )

        return ecephys_metadata

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subset_channels = get_sorted_shank_channels(self.source_data['file_path'])

    def get_metadata(self):
        """Retrieve Ecephys metadata specific to the Neuroscope format."""
        return NeuroscopeRecordingInterface.get_ecephys_metadata(
            data_file_path=self.source_data['file_path']
        )


class NeuroscopeLFPInterface(BaseLFPExtractorInterface):
    """Primary data interface class for converting Neuroscope LFP data."""

    RX = se.NeuroscopeRecordingExtractor

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subset_channels = get_sorted_shank_channels(self.source_data['file_path'])


class NeuroscopeSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeSortingExtractor."""

    SX = se.NeuroscopeMultiSortingExtractor

    def get_metadata(self):
        """Auto-populates spiking unit metadata."""
        session_path = Path(self.source_data['folder_path'])
        session_id = session_path.stem
        xml_file_path = session_path / f"{session_id}.xml"
        metadata = NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path)

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
                        data=["shank" + str(x) for x in cell_info['shankID'][0][0][0]]
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
