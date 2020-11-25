"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

import numpy as np
import spikeextractors as se
from lxml import etree as et
from scipy.io import loadmat

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface


def get_xml(dat_file_path):
    """Auxiliary function for retrieving root of xml."""
    file_path = Path(dat_file_path)
    session_path = file_path.parent
    session_id = session_path.stem
    xml_filepath = session_path / f"{session_id}.xml"
    root = et.parse(str(xml_filepath.absolute())).getroot()

    return root


class NeuroscopeRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeRecordingExtractor."""

    RX = se.NeuroscopeRecordingExtractor

    @staticmethod
    def get_ecephys_metadata(xml_file_path):
        """Auto-populates ecephys metadata from the xml_file_path."""
        session_path = Path(xml_file_path).parent
        session_id = session_path.stem
        root = et.parse(str(xml_file_path.absolute())).getroot()
        shank_channels = [[int(channel.text)
                           for channel in group.find('channels')]
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')]
        all_shank_channels = np.concatenate(shank_channels)
        all_shank_channels.sort()
        shank_electrode_number = [x for channels in shank_channels for x, _ in enumerate(channels)]
        shank_group_name = [f"shank{n + 1}" for n, channels in enumerate(shank_channels) for _ in channels]

        ecephys_metadata = dict(
            Ecephys=dict(
                subset_channels=all_shank_channels,
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
                    description="raw acquisition traces"
                )
            )
        )

        return ecephys_metadata

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        root = get_xml(self.source_data['file_path'])
        shank_channels = [[int(channel.text)
                           for channel in group.find('channels')]
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')]
        all_shank_channels = np.concatenate(shank_channels)

        self.subset_channels = sorted(all_shank_channels)

    def get_metadata(self):
        """Retrieve Ecephys metadata specific to the Neuroscope format."""
        file_path = Path(self.source_data['file_path'])
        session_path = file_path.parent
        session_id = session_path.stem
        xml_file_path = session_path / f"{session_id}.xml"
        ecephys_metadata = NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path)

        return ecephys_metadata


class NeuroscopeLFPInterface(BaseLFPExtractorInterface):
    """Primary data interface class for converting Neuroscope LFP data."""

    RX = se.NeuroscopeRecordingExtractor

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        root = get_xml(self.source_data['file_path'])
        shank_channels = [[int(channel.text)
                           for channel in group.find('channels')]
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')]
        all_shank_channels = np.concatenate(shank_channels)

        self.subset_channels = sorted(all_shank_channels)


class NeuroscopeSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeSortingExtractor."""

    SX = se.NeuroscopeMultiSortingExtractor

    def get_metadata(self):
        """Auto-populates spiking unit metadata."""
        session_path = Path(self.source_data['folder_path'])
        session_id = session_path.stem
        xml_file_path = session_path / f"{session_id}.xml"
        metadata = NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path)

        cell_filepath = session_path / f"{session_id}.spikes.cellinfo.mat"
        if cell_filepath.is_file():
            cell_info = loadmat(cell_filepath)['spikes']

        celltype_mapping = {'pE': "excitatory", 'pI': "inhibitory"}
        celltype_filepath = session_path / f"{session_id}.CellClass.cellinfo.mat"
        if celltype_filepath.is_file():
            celltype_info = [str(celltype_mapping[x[0]])
                             for x in loadmat(celltype_filepath)['CellClass']['label'][0][0][0]]

        # TODO: generalize for the non-existence of these fields
        metadata.update(
            UnitProperties=[
                dict(
                    name="cell_type",
                    description="Type of cell this has been classified as.",
                    data=celltype_info
                ),
                dict(
                    name="global_id",
                    description="Global id for this cell for the entire experiment.",
                    data=[int(x) for x in cell_info['UID'][0][0][0]]
                ),
                dict(
                    name="shank_id",
                    description="0-indexed id of cluster identified from the shank.",
                    # - 2 b/c the 0 and 1 IDs from each shank have been removed
                    data=[int(x - 2) for x in cell_info['cluID'][0][0][0]]
                ),
                dict(
                    name="electrode_group",
                    description="The electrode group that each unit was identified by.",
                    data=["shank" + str(x) for x in cell_info['shankID'][0][0][0]]
                ),
                dict(
                    name="region",
                    description="Brain region where each unit was detected.",
                    data=[str(x[0]) for x in cell_info['region'][0][0][0]]
                )
            ]
        )
        return metadata
