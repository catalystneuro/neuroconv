from pathlib import Path
from typing import Optional

import numpy as np

from .neuroscope_utils import (
    get_channel_groups,
    get_neural_channels,
    get_session_start_time,
    get_xml_file_path,
)
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....tools import get_package
from ....utils import FilePathType, FolderPathType


def filter_non_neural_channels(recording_extractor, xml_file_path: str):
    """
    Subsets the recording extractor to only use channels corresponding to neural data.

    Parameters
    ----------
    recording_extractor : BaseExtractor from spikeinterface
        The original recording extractor object.
    xml_file_path : str
        Path to the XML file containing the Neuroscope metadata.

    Returns
    -------
    BaseExtractor from spikeinterface
        The subset recording extractor object.

    Notes
    -----
    This function subsets the given recording extractor to include only channels that
    correspond to neural data, filtering out auxiliary channels.

    To identify the neural channels, it relies on the `get_neural_channels` function
    in the `neuroscope_utils.py` module. Please refer to that function for more details and warnings.

    If no neural channels are found o during the process, the original
    recording extractor is returned unchanged. If all the channels in the original recording extractor are
    neural channels, then the original recording extractor is returned unchanged as well.
    """

    neural_channels_as_groups = get_neural_channels(xml_file_path=xml_file_path)

    if neural_channels_as_groups is None:
        return recording_extractor
    else:
        # Flat neural channels as groups which is a list of lists and converter to str which is the representation
        # In spikeinterface of the channel ids
        neural_channel_ids = [str(channel_id) for group in neural_channels_as_groups for channel_id in group]
        channel_ids_in_recorder = recording_extractor.get_channel_ids()

        # Get only the channel_ids_in_recorder that are in the neural_channel_ids
        neural_channel_ids = [channel_id for channel_id in channel_ids_in_recorder if channel_id in neural_channel_ids]

        # If all the channel_ids_in_recorder are in the neural_channel_ids, return the original recording_extractor
        if len(neural_channel_ids) == len(channel_ids_in_recorder):
            return recording_extractor

        sub_recording = recording_extractor.channel_slice(channel_ids=neural_channel_ids)
        return sub_recording


def add_recording_extractor_properties(recording_extractor, gain: Optional[float] = None):
    """Automatically add properties to RecordingExtractor object."""

    if gain:
        recording_extractor.set_channel_gains(gain)

    channel_ids = recording_extractor.get_channel_ids()
    channel_names = recording_extractor.get_property(key="channel_name")
    channel_groups = [int(name.split("grp")[1]) for name in channel_names]

    channel_group_names = [f"Group{group_index + 1}" for group_index in channel_groups]
    recording_extractor.set_property(key="group", ids=channel_ids, values=channel_groups)
    recording_extractor.set_property(key="group_name", ids=channel_ids, values=channel_group_names)

    unique_groups = set(channel_groups)
    channel_id_to_shank_electrode_number = dict()

    # For each group, get the corresponding channels and enumerate them to have the shank electrode number
    for group_index in unique_groups:
        group_channels = [channel_id for channel_id, group in zip(channel_ids, channel_groups) if group == group_index]
        group_mapping = {channel_id: electrode_number for electrode_number, channel_id in enumerate(group_channels)}
        channel_id_to_shank_electrode_number.update(group_mapping)

    group_electrode_numbers = [channel_id_to_shank_electrode_number[channel_id] for channel_id in channel_ids]
    recording_extractor.set_property(key="shank_electrode_number", ids=channel_ids, values=group_electrode_numbers)


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

        add_recording_extractor_properties(recording_extractor=self.recording_extractor, gain=gain)

        self.recording_extractor = filter_non_neural_channels(
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
        gain : float, optional
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

        add_recording_extractor_properties(recording_extractor=self.recording_extractor, gain=gain)

        self.recording_extractor = filter_non_neural_channels(
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
