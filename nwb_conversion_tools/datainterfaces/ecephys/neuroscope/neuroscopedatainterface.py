"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
from typing import Optional, List

import numpy as np
import spikeextractors as se
from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils.json_schema import FilePathType, FolderPathType, get_schema_from_hdmf_class, dict_deep_update

try:
    from lxml import etree as et

    HAVE_LXML = True
except ImportError:
    HAVE_LXML = False
INSTALL_MESSAGE = "Please install lxml to use this extractor!"


def get_xml_file_path(data_file_path: str):
    """
    Infer the xml_file_path from the data_file_path (.dat or .eeg).

    Assumes the two are in the same folder and follow the session_id naming convention.
    """
    session_path = Path(data_file_path).parent
    return str(session_path / f"{session_path.stem}.xml")


def get_xml(xml_file_path: str):
    """Auxiliary function for retrieving root of xml."""
    return et.parse(xml_file_path).getroot()


def get_shank_channels(xml_file_path: str, sort: bool = False):
    """
    Auxiliary function for retrieving the list of structured shank-only channels.

    Attempts to retrieve these first from the spikeDetection sub-field in the event that spike sorting was performed on
    the raw data. In the event that spike sorting was not performed, it then retrieves only the anatomicalDescription.
    """
    root = get_xml(xml_file_path)
    try:
        shank_channels = [
            [int(channel.text) for channel in group.find("channels")]
            for group in root.find("spikeDetection").find("channelGroups").findall("group")
        ]
    except (TypeError, AttributeError):
        shank_channels = [
            [int(channel.text) for channel in group.findall("channel")]
            for group in root.find("anatomicalDescription").find("channelGroups").findall("group")
        ]

    if sort:
        shank_channels = sorted(np.concatenate(shank_channels))

    return shank_channels


class NeuroscopeRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeRecordingExtractor."""

    RX = se.NeuroscopeRecordingExtractor

    @staticmethod
    def get_ecephys_metadata(xml_file_path: str):
        """Auto-populates ecephys metadata from the xml_file_path."""
        shank_channels = get_shank_channels(xml_file_path)
        ecephys_metadata = dict(
            ElectrodeGroup=[
                dict(name=f"shank{n + 1}", description=f"shank{n + 1} electrodes", location="", device="Device_ecephys")
                for n, _ in enumerate(shank_channels)
            ],
            Electrodes=[
                dict(name="shank_electrode_number", description="0-indexed channel within a shank."),
                dict(name="group_name", description="The name of the ElectrodeGroup this electrode is a part of."),
            ],
        )
        return ecephys_metadata

    def __init__(self, file_path: FilePathType):
        super().__init__(file_path=file_path)
        xml_file_path = get_xml_file_path(data_file_path=self.source_data["file_path"])
        self.subset_channels = get_shank_channels(xml_file_path=xml_file_path, sort=True)
        shank_channels = get_shank_channels(xml_file_path)
        group_electrode_numbers = [x for channels in shank_channels for x, _ in enumerate(channels)]
        group_names = [f"shank{n + 1}" for n, channels in enumerate(shank_channels) for _ in channels]
        for channel_id, group_electrode_number, group_name in zip(
            self.recording_extractor.get_channel_ids(), group_electrode_numbers, group_names
        ):
            self.recording_extractor.set_channel_property(
                channel_id=channel_id, property_name="shank_electrode_number", value=group_electrode_number
            )
            self.recording_extractor.set_channel_property(
                channel_id=channel_id, property_name="group_name", value=group_name
            )

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_raw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        """Retrieve Ecephys metadata specific to the Neuroscope format."""
        metadata = super().get_metadata()
        metadata["Ecephys"].update(
            NeuroscopeRecordingInterface.get_ecephys_metadata(
                xml_file_path=get_xml_file_path(data_file_path=self.source_data["file_path"])
            )
        )
        metadata["Ecephys"].update(
            ElectricalSeries_raw=dict(name="ElectricalSeries_raw", description="Raw acquisition traces.")
        )
        return metadata


class NeuroscopeMultiRecordingTimeInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeMultiRecordingTimeExtractor."""

    RX = se.NeuroscopeMultiRecordingTimeExtractor

    def __init__(self, folder_path: FolderPathType):
        super().__init__(folder_path=folder_path)
        xml_file_path = get_xml_file_path(data_file_path=self.source_data["folder_path"])
        self.subset_channels = get_shank_channels(xml_file_path=xml_file_path, sort=True)
        shank_channels = get_shank_channels(xml_file_path)
        group_electrode_numbers = [x for channels in shank_channels for x, _ in enumerate(channels)]
        group_names = [f"shank{n + 1}" for n, channels in enumerate(shank_channels) for _ in channels]
        for channel_id, group_electrode_number, group_name in zip(
            self.recording_extractor.get_channel_ids(), group_electrode_numbers, group_names
        ):
            self.recording_extractor.set_channel_property(
                channel_id=channel_id, property_name="group_electrode_number", value=group_electrode_number
            )
            self.recording_extractor.set_channel_property(
                channel_id=channel_id, property_name="group_name", value=group_name
            )

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_raw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        """Retrieve Ecephys metadata specific to the Neuroscope format."""
        metadata = super().get_metadata()
        metadata(
            metadata,
            NeuroscopeRecordingInterface.get_ecephys_metadata(
                xml_file_path=get_xml_file_path(data_file_path=self.source_data["folder_path"])
            ),
        )
        metadata["Ecephys"].update(
            ElectricalSeries_raw=dict(name="ElectricalSeries_raw", description="Raw acquisition traces.")
        )
        return metadata


class NeuroscopeLFPInterface(BaseLFPExtractorInterface):
    """Primary data interface class for converting Neuroscope LFP data."""

    RX = se.NeuroscopeRecordingExtractor

    def __init__(self, file_path: FilePathType):
        super().__init__(file_path=file_path)
        self.subset_channels = get_shank_channels(
            xml_file_path=get_xml_file_path(data_file_path=self.source_data["file_path"]), sort=True
        )

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_lfp=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        """Retrieve Ecephys metadata specific to the Neuroscope format."""
        metadata = super().get_metadata()
        dict_deep_update(
            metadata,
            NeuroscopeRecordingInterface.get_ecephys_metadata(
                xml_file_path=get_xml_file_path(data_file_path=self.source_data["file_path"])
            ),
        )
        metadata["Ecephys"].update(
            ElectricalSeries_lfp=dict(name="ElectricalSeries_lfp", description="Local field potential signal.")
        )
        return metadata


class NeuroscopeSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeSortingExtractor."""

    SX = se.NeuroscopeMultiSortingExtractor

    def __init__(
        self,
        folder_path: FolderPathType,
        keep_mua_units: bool = True,
        exlude_shanks: Optional[list] = None,
        load_waveforms: bool = False,
        gain: Optional[float] = None,
    ):
        super().__init__(
            folder_path=folder_path,
            keep_mua_units=keep_mua_units,
            exlude_shanks=exlude_shanks,
            load_waveforms=load_waveforms,
            gain=gain,
        )

    def get_metadata(self):
        session_path = Path(self.source_data["folder_path"])
        session_id = session_path.stem
        metadata = NeuroscopeRecordingInterface.get_ecephys_metadata(
            xml_file_path=str((session_path / f"{session_id}.xml").absolute())
        )
        metadata.update(UnitProperties=[])
        return metadata
