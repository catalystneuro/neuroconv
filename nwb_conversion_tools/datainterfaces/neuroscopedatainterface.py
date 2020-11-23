"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

import numpy as np
import spikeextractors as se
from lxml import etree as et

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface


class NeuroscopeRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeRecordingExtractor."""

    RX = se.NeuroscopeRecordingExtractor

    @staticmethod
    def get_ecephys_metadata(xml_file_path):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        root = self.get_xml()

        shank_channels = [[int(channel.text)
                           for channel in group.find('channels')]
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')]
        all_shank_channels = np.concatenate(shank_channels)

        self.subset_channels = sorted(all_shank_channels)

    def get_xml(self):
        file_path = Path(self.input_args['file_path'])
        session_path = file_path.parent
        session_id = session_path.stem
        xml_filepath = session_path / f"{session_id}.xml"
        root = et.parse(str(xml_filepath.absolute())).getroot()

        return root

    def get_metadata(self):
        """Retrieve Ecephys metadata specific to the Neuroscope format."""
        file_path = Path(self.input_args['file_path'])
        session_path = file_path.parent
        session_id = session_path.stem
        xml_file_path = session_path / f"{session_id}.xml"
        ecephys_metadata = NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path)
        return ecephys_metadata


class NeuroscopeSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeSortingExtractor."""

    SX = se.NeuroscopeMultiSortingExtractor

    def get_metadata(self):
        session_path = Path(self.input_args['folder_path'])
        session_id = session_path.stem
        xml_file_path = session_path / f"{session_id}.xml"
        metadata = NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path)
        return metadata
