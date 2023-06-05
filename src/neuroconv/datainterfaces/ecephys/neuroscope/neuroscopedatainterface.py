from pathlib import Path
from typing import Optional

import numpy as np

from .neuroscope_utils import (
    get_channel_groups,
    get_session_start_time,
    get_shank_channels,
    get_xml_file_path,
)
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....tools import get_package
from ....utils import FilePathType, FolderPathType


def subset_shank_channels(recording_extractor, xml_file_path: str):
    """Attempt to create a SubRecordingExtractor containing only channels related to neural data."""
    shank_channels = get_shank_channels(xml_file_path=xml_file_path)

    if shank_channels is not None:
        channel_ids = [channel_id for group in shank_channels for channel_id in group]
        new_ids = recording_extractor.get_channel_ids()[channel_ids]
        sub_recording = recording_extractor.channel_slice(new_ids)
    else:
        sub_recording = recording_extractor

    return sub_recording


def add_recording_extractor_properties(recording_extractor, xml_file_path: str, gain: Optional[float] = None):
    """Automatically add properties to RecordingExtractor object."""

    if gain:
        recording_extractor.set_channel_gains(gain)

    channel_groups = get_channel_groups(xml_file_path=xml_file_path)

    channel_map = {
        channel_id: idx
        for idx, channel_id in enumerate([channel_id for group in channel_groups for channel_id in group])
    }
    group_electrode_numbers = [x for channels in channel_groups for x, _ in enumerate(channels)]
    group_nums = [n + 1 for n, channels in enumerate(channel_groups) for _ in channels]
    group_names = [f"Group{n}" for n in group_nums]

    channel_groups_mapped = [group_nums[channel_map[channel_id]] for channel_id in channel_map.keys()]
    group_names_mapped = [group_names[channel_map[channel_id]] for channel_id in channel_map.keys()]
    shank_electrode_number = [group_electrode_numbers[channel_map[channel_id]] for channel_id in channel_map.keys()]

    channel_ids_mapped = recording_extractor.get_channel_ids()
    recording_extractor.set_property(key="group", ids=channel_ids_mapped, values=channel_groups_mapped)
    recording_extractor.set_property(key="group_name", ids=channel_ids_mapped, values=group_names_mapped)
    recording_extractor.set_property(
        key="shank_electrode_number", ids=channel_ids_mapped, values=shank_electrode_number
    )


class NeuroScopeRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface for converting a NeuroScope data. Uses
    :py:class:`~spikeinterface.extractors.NeuroScopeRecordingExtractor`."""

    @staticmethod
    def get_ecephys_metadata(xml_file_path: str) -> dict:
        """Auto-populates ecephys metadata from the xml_file_path."""
        channel_groups = get_channel_groups(xml_file_path=xml_file_path)
        ecephys_metadata = dict(
            ElectrodeGroup=[
                dict(name=f"Group{n + 1}", description=f"Group{n + 1} electrodes.", location="", device="DeviceEcephys")
                for n, _ in enumerate(channel_groups)
            ],
            Electrodes=[
                dict(name="shank_electrode_number", description="0-indexed channel within a shank."),
                dict(name="group_name", description="The name of the ElectrodeGroup this electrode is a part of."),
            ],
        )
        return ecephys_metadata

    def __init__(
        self,
        file_path: FilePathType,
        gain: Optional[float] = None,
        xml_file_path: Optional[FilePathType] = None,
        verbose: bool = True,
        es_key: str = "ElectricalSeries",
    ):
        """
        Load and prepare raw acquisition data and corresponding metadata from the Neuroscope format (.dat files).

        Parameters
        ----------
        file_path : FilePathType
            Path to .dat file.
        gain : Optional[float], optional
            Conversion factors from int16 to Volts are not contained in xml_file_path; set them explicitly here.
            Most common value is 0.195 for an intan recording system.
            The default is None.
        xml_file_path : FilePathType, optional
            Path to .xml file containing device and electrode configuration.
            If unspecified, it will be automatically set as the only .xml file in the same folder as the .dat file.
            The default is None.
        es_key: str, default: "ElectricalSeries"
        """
        get_package(package_name="lxml")

        if xml_file_path is None:
            xml_file_path = get_xml_file_path(data_file_path=file_path)

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)
        self.source_data["xml_file_path"] = xml_file_path

        add_recording_extractor_properties(
            recording_extractor=self.recording_extractor, xml_file_path=xml_file_path, gain=gain
        )

        self.recording_extractor = subset_shank_channels(
            recording_extractor=self.recording_extractor, xml_file_path=xml_file_path
        )

    def get_metadata(self) -> dict:
        session_path = Path(self.source_data["file_path"]).parent
        session_id = session_path.stem
        xml_file_path = self.source_data.get("xml_file_path", str(session_path / f"{session_id}.xml"))
        metadata = super().get_metadata()
        metadata["Ecephys"].update(NeuroScopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path))
        session_start_time = get_session_start_time(str(xml_file_path))
        if session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        # TODO: add generic method for aliasing from NeuroConv signature to SI init
        new_recording = self.get_extractor()(file_path=self.source_data["file_path"])
        if self._number_of_segments == 1:
            return new_recording.get_times()
        else:
            return [
                new_recording.get_times(segment_index=segment_index)
                for segment_index in range(self._number_of_segments)
            ]


class NeuroScopeLFPInterface(BaseLFPExtractorInterface):
    """Primary data interface class for converting Neuroscope LFP data."""

    ExtractorName = "NeuroScopeRecordingExtractor"

    def __init__(
        self,
        file_path: FilePathType,
        gain: Optional[float] = None,
        xml_file_path: Optional[FilePathType] = None,
    ):
        """
        Load and prepare lfp data and corresponding metadata from the Neuroscope format (.eeg or .lfp files).

        Parameters
        ----------
        file_path : FilePathType
            Path to .dat file.
        gain : Optional[float], optiona
            Conversion factors from int16 to Volts are not contained in xml_file_path; set them explicitly here.
            Most common value is 0.195 for an intan recording system.
            The default is None.
        xml_file_path : OptionalFilePathType, optional
            Path to .xml file containing device and electrode configuration.
            If unspecified, it will be automatically set as the only .xml file in the same folder as the .dat file.
            The default is None.
        """
        get_package(package_name="lxml")

        if xml_file_path is None:
            xml_file_path = get_xml_file_path(data_file_path=file_path)

        super().__init__(file_path=file_path)
        self.source_data["xml_file_path"] = xml_file_path

        add_recording_extractor_properties(
            recording_extractor=self.recording_extractor, xml_file_path=xml_file_path, gain=gain
        )

        self.recording_extractor = subset_shank_channels(
            recording_extractor=self.recording_extractor, xml_file_path=xml_file_path
        )

    def get_metadata(self) -> dict:
        session_path = Path(self.source_data["file_path"]).parent
        session_id = session_path.stem
        xml_file_path = self.source_data.get("xml_file_path", str(session_path / f"{session_id}.xml"))
        metadata = super().get_metadata()
        metadata["Ecephys"].update(NeuroScopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path))
        return metadata


class NeuroScopeSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeSortingExtractor."""

    def __init__(
        self,
        folder_path: FolderPathType,
        keep_mua_units: bool = True,
        exclude_shanks: Optional[list] = None,
        xml_file_path: Optional[FilePathType] = None,
        verbose: bool = True,
    ):
        """
        Load and prepare spike sorted data and corresponding metadata from the Neuroscope format (.res/.clu files).

        Parameters
        ----------
        folder_path : FolderPathType
            Path to folder containing .clu and .res files.
        keep_mua_units : bool, default: True
            Optional. Whether to return sorted spikes from multi-unit activity.
            The default is True.
        exclude_shanks : list, optional
            List of indices to ignore. The set of all possible indices is chosen by default, extracted as the
            final integer of all the .res.%i and .clu.%i pairs.
        xml_file_path : FilePathType, optional
            Path to .xml file containing device and electrode configuration.
            If unspecified, it will be automatically set as the only .xml file in the same folder as the .dat file.
            The default is None.
        """
        get_package(package_name="lxml")

        super().__init__(
            folder_path=folder_path,
            keep_mua_units=keep_mua_units,
            exclude_shanks=exclude_shanks,
            xml_file_path=xml_file_path,
            verbose=verbose,
        )

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        session_path = Path(self.source_data["folder_path"])
        session_id = session_path.stem
        xml_file_path = self.source_data.get("xml_file_path", str(session_path / f"{session_id}.xml"))
        metadata["Ecephys"] = NeuroScopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path)
        session_start_time = get_session_start_time(str(xml_file_path))
        if session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        return metadata
