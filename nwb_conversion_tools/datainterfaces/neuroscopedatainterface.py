"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se
from lxml import etree as et
from pathlib import Path
from itertools import compress
import numpy as np

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ..utils import dict_deep_update


class NeuroscopeRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeRecordingExtractor."""

    RX = se.NeuroscopeRecordingExtractor

    def get_metadata(self, metadata):
        """Retrieve Ecephys metadata specific to the Neuroscope format."""
        session_path = Path(self.input_args['file_path'])
        session_id = session_path.stem
        xml_filepath = session_path / f"{session_id}.xml"
        root = et.parse(xml_filepath).getroot()
        shank_channels = [[int(channel.text)
                          for channel in group.find('channels')]
                          for group in root.find('spikeDetection').find('channelGroups').findall('group')]
        all_shank_channels = np.concatenate(shank_channels)
        all_shank_channels.sort()
        shank_electrode_number = [x for channels in shank_channels for x, _ in enumerate(channels)]
        shank_group_name = ["shank{}".format(n+1) for n, channels in enumerate(shank_channels) for _ in channels]

        re_metadata = dict(
            Ecephys=dict(
                subset_channels=all_shank_channels,
                Device=[
                    dict(
                        description=session_id + '.xml'
                    )
                ],
                ElectrodeGroup=[
                    dict(
                        name=f'shank{n+1}',
                        description=f"shank{n+1} electrodes"
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
                        name='group',
                        description="A reference to the ElectrodeGroup this electrode is a part of.",
                        data=shank_group_name
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
        dict_deep_update(metadata, re_metadata)


class NeuroscopeSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeSortingExtractor."""

    SX = se.NeuroscopeMultiSortingExtractor
