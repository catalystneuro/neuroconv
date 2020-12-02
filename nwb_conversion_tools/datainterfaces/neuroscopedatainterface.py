"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

import numpy as np
import spikeextractors as se
from lxml import etree as et

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
    return str((session_path / f"{session_id}.xml").absolute())


def get_xml(xml_file_path: str):
    """Auxiliary function for retrieving root of xml."""
    root = et.parse(xml_file_path).getroot()

    return root


def get_shank_channels(xml_file_path: str, sort: bool = False):
    """Auxiliary function for retrieving the list of structured shank-only channels."""
    root = get_xml(xml_file_path)
    shank_channels = [
        [int(channel.text) for channel in group.find('channels')]
        for group in root.find('spikeDetection').find('channelGroups').findall('group')
    ]

    if sort:
        shank_channels = sorted(np.concatenate(shank_channels))

    return shank_channels


class NeuroscopeRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeRecordingExtractor."""

    RX = se.NeuroscopeRecordingExtractor

    @staticmethod
    def get_ecephys_metadata(xml_file_path: str):
        """Auto-populates ecephys metadata from the xml_file_path inferred."""
        session_path = Path(xml_file_path).parent
        session_id = session_path.stem
        shank_channels = get_shank_channels(xml_file_path)

        ecephys_metadata = dict(
            Ecephys=dict(
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
                        data=[x for channels in shank_channels for x, _ in enumerate(channels)]
                    ),
                    dict(
                        name='group_name',
                        description="The name of the ElectrodeGroup this electrode is a part of.",
                        data=[f"shank{n + 1}" for n, channels in enumerate(shank_channels) for _ in channels]
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
        self.subset_channels = get_shank_channels(
            xml_file_path=get_xml_file_path(data_file_path=self.source_data['file_path']),
            sort=True
        )

    def get_metadata(self):
        """Retrieve Ecephys metadata specific to the Neuroscope format."""
        return NeuroscopeRecordingInterface.get_ecephys_metadata(
            xml_file_path=get_xml_file_path(data_file_path=self.source_data['file_path'])
        )


class NeuroscopeLFPInterface(BaseLFPExtractorInterface):
    """Primary data interface class for converting Neuroscope LFP data."""

    RX = se.NeuroscopeRecordingExtractor

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subset_channels = get_shank_channels(
            xml_file_path=get_xml_file_path(data_file_path=self.source_data['file_path']),
            sort=True
        )

    def get_metadata(self):
        """Retrieve Ecephys metadata specific to the Neuroscope format."""
        metadata = NeuroscopeRecordingInterface.get_ecephys_metadata(
            xml_file_path=get_xml_file_path(data_file_path=self.source_data['file_path'])
        )
        metadata['Ecephys'].update(
            LFPElectricalSeries=dict(
                name="LFP",
                description="Local field potential signal."
            )
        )
        return metadata


class NeuroscopeSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeSortingExtractor."""

    SX = se.NeuroscopeMultiSortingExtractor

    def get_metadata(self):
        """Auto-populates spiking unit metadata."""
        raise NotImplementedError("get_metadata() for NeuroscopeSortingInterface is not yet implemented!")
