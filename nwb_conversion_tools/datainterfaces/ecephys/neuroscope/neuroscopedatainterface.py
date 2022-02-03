"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
from typing import Optional, Union

import spikeextractors as se
import spikeinterface as si
from spikeinterface.core.old_api_utils import OldToNewRecording

from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils.json_schema import FilePathType, FolderPathType, OptionalFilePathType, get_schema_from_hdmf_class

try:
    import lxml
    from .neuroscope_utils import get_xml_file_path, get_channel_groups, get_shank_channels

    HAVE_LXML = True
except ImportError:
    HAVE_LXML = False
INSTALL_MESSAGE = "Please install lxml to use this interface!"


def subset_shank_channels(
    recording_extractor: Union[se.RecordingExtractor, si.BaseRecording], xml_file_path: str
) -> si.BaseRecording:
    """Attempt to create a SubRecordingExtractor containing only channels related to neural data."""
    if isinstance(recording_extractor, se.RecordingExtractor):
        recording = OldToNewRecording(oldapi_recording_extractor=recording_extractor)
    else:
        recording = recording_extractor
    shank_channels = get_shank_channels(xml_file_path=xml_file_path)

    if shank_channels is not None:
        channel_ids = [channel_id for group in shank_channels for channel_id in group]
        sub_recording = recording.channel_slice(channel_ids)
    else:
        sub_recording = recording
    return sub_recording


def add_recording_extractor_properties(recording_extractor: se.RecordingExtractor, xml_file_path: str):
    """Automatically add properties to RecordingExtractor object."""
    channel_groups = get_channel_groups(xml_file_path=xml_file_path)
    channel_map = {
        channel_id: idx
        for idx, channel_id in enumerate([channel_id for group in channel_groups for channel_id in group])
    }
    group_electrode_numbers = [x for channels in channel_groups for x, _ in enumerate(channels)]
    group_nums = [n + 1 for n, channels in enumerate(channel_groups) for _ in channels]
    group_names = [f"Group{n}" for n in group_nums]

    for channel_id in channel_map.keys():
        recording_extractor.set_channel_groups(channel_ids=[channel_id], groups=group_nums[channel_map[channel_id]])
        recording_extractor.set_channel_property(
            channel_id=channel_id, property_name="group_name", value=group_names[channel_map[channel_id]]
        )
        recording_extractor.set_channel_property(
            channel_id=channel_id,
            property_name="shank_electrode_number",
            value=group_electrode_numbers[channel_map[channel_id]],
        )


class NeuroscopeRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeRecordingExtractor."""

    RX = se.NeuroscopeRecordingExtractor

    @staticmethod
    def get_ecephys_metadata(xml_file_path: str):
        """Auto-populates ecephys metadata from the xml_file_path."""
        channel_groups = get_channel_groups(xml_file_path=xml_file_path)
        ecephys_metadata = dict(
            ElectrodeGroup=[
                dict(
                    name=f"Group{n + 1}", description=f"Group{n + 1} electrodes.", location="", device="Device_ecephys"
                )
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
        xml_file_path: OptionalFilePathType = None,
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
        xml_file_path : OptionalFilePathType, optional
            Path to .xml file containing device and electrode configuration.
            If unspecified, it will be automatically set as the only .xml file in the same folder as the .dat file.
            The default is None.
        """
        assert HAVE_LXML, INSTALL_MESSAGE

        if xml_file_path is None:
            xml_file_path = get_xml_file_path(data_file_path=file_path)
        super().__init__(file_path=file_path, gain=gain, xml_file_path=xml_file_path)

        # Add the properties
        add_recording_extractor_properties(recording_extractor=self.recording_extractor, xml_file_path=xml_file_path)
        self.recording_extractor = subset_shank_channels(
            recording_extractor=self.recording_extractor, xml_file_path=xml_file_path
        )

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_raw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        session_path = Path(self.source_data["file_path"]).parent
        session_id = session_path.stem
        xml_file_path = self.source_data.get("xml_file_path", str(session_path / f"{session_id}.xml"))
        metadata = super().get_metadata()
        metadata["Ecephys"].update(NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path))
        metadata["Ecephys"].update(
            ElectricalSeries_raw=dict(name="ElectricalSeries_raw", description="Raw acquisition traces.")
        )
        return metadata


class NeuroscopeMultiRecordingTimeInterface(NeuroscopeRecordingInterface):
    """Primary data interface class for converting a NeuroscopeMultiRecordingTimeExtractor."""

    RX = se.NeuroscopeMultiRecordingTimeExtractor

    def __init__(
        self,
        folder_path: FolderPathType,
        gain: Optional[float] = None,
        xml_file_path: OptionalFilePathType = None,
    ):
        """
        Load and prepare raw acquisition data and corresponding metadata from the Neuroscope format (.dat files).

        For all the .dat files in the folder_path, this concatenates them in time assuming no gaps in between.
        If there are gaps, timestamps inside the RecordingExtractor should be overridden.

        Parameters
        ----------
        folder_path : FolderPathType
            Path to folder of multiple .dat files.
        gain : Optional[float], optional
            Conversion factors from int16 to Volts are not contained in xml_file_path; set them explicitly here.
            Most common value is 0.195 for an intan recording system.
            The default is None.
        xml_file_path : OptionalFilePathType, optional
            Path to .xml file containing device and electrode configuration.
            If unspecified, it will be automatically set as the only .xml file in the same folder as the .dat file.
            The default is None.
        """
        assert HAVE_LXML, INSTALL_MESSAGE

        if xml_file_path is None:
            xml_file_path = get_xml_file_path(data_file_path=folder_path)
        super(NeuroscopeRecordingInterface, self).__init__(
            folder_path=folder_path, gain=gain, xml_file_path=xml_file_path
        )
        self.recording_extractor = subset_shank_channels(
            recording_extractor=self.recording_extractor, xml_file_path=xml_file_path
        )
        add_recording_extractor_properties(recording_extractor=self.recording_extractor, xml_file_path=xml_file_path)


class NeuroscopeLFPInterface(BaseLFPExtractorInterface):
    """Primary data interface class for converting Neuroscope LFP data."""

    RX = se.NeuroscopeRecordingExtractor

    def __init__(
        self,
        file_path: FilePathType,
        gain: Optional[float] = None,
        xml_file_path: OptionalFilePathType = None,
    ):
        """
        Load and prepare lfp data and corresponding metadata from the Neuroscope format (.eeg or .lfp files).

        Parameters
        ----------
        file_path : FilePathType
            Path to .dat file.
        gain : Optional[float], optional
            Conversion factors from int16 to Volts are not contained in xml_file_path; set them explicitly here.
            Most common value is 0.195 for an intan recording system.
            The default is None.
        xml_file_path : OptionalFilePathType, optional
            Path to .xml file containing device and electrode configuration.
            If unspecified, it will be automatically set as the only .xml file in the same folder as the .dat file.
            The default is None.
        """
        assert HAVE_LXML, INSTALL_MESSAGE

        if xml_file_path is None:
            xml_file_path = get_xml_file_path(data_file_path=file_path)
        super().__init__(file_path=file_path, gain=gain, xml_file_path=xml_file_path)

        add_recording_extractor_properties(recording_extractor=self.recording_extractor, xml_file_path=xml_file_path)
        self.recording_extractor = subset_shank_channels(
            recording_extractor=self.recording_extractor, xml_file_path=xml_file_path
        )

    def get_metadata(self):
        session_path = Path(self.source_data["file_path"]).parent
        session_id = session_path.stem
        xml_file_path = self.source_data.get("xml_file_path", str(session_path / f"{session_id}.xml"))
        metadata = super().get_metadata()
        metadata["Ecephys"].update(NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path))
        return metadata


class NeuroscopeSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeSortingExtractor."""

    SX = se.NeuroscopeMultiSortingExtractor

    def __init__(
        self,
        folder_path: FolderPathType,
        keep_mua_units: bool = True,
        exclude_shanks: Optional[list] = None,
        xml_file_path: OptionalFilePathType = None,
        # TODO: we can enable this once
        #     a) waveforms on unit columns support conversion factor in NWB
        #     b) write_sorting utils support writing said waveforms properly to a units table
        # load_waveforms: bool = False,
        # gain: Optional[float] = None,
    ):
        """
        Load and prepare spike sorted data and corresponding metadata from the Neuroscope format (.res/.clu files).

        Parameters
        ----------
        folder_path : FolderPathType
            Path to folder containing .clu and .res files.
            The default is None.
        keep_mua_units : bool
            Optional. Whether or not to return sorted spikes from multi-unit activity.
            The default is True.
        exclude_shanks : list
            Optional. List of indices to ignore. The set of all possible indices is chosen by default, extracted as the
            final integer of all the .res.%i and .clu.%i pairs.
        xml_file_path : OptionalFilePathType, optional
            Path to .xml file containing device and electrode configuration.
            If unspecified, it will be automatically set as the only .xml file in the same folder as the .dat file.
            The default is None.
        load_waveforms : bool, optional
            If True, extracts waveform data from .spk.%i files in the path corresponding to
            the .res.%i and .clue.%i files and sets these as unit spike features.
            The default is False.
            Not currently in use pending updates to NWB waveforms.
        gain : float, optional
            If loading waveforms, this value converts the data type of the waveforms to units of microvolts.
            Conversion factors from int16 to Volts are not contained in xml_file_path; set them explicitly here.
            Most common value is 0.195 for an intan recording system.
            The default is None.
            Not currently in use pending updates to NWB waveforms.
        """
        assert HAVE_LXML, INSTALL_MESSAGE

        super().__init__(
            folder_path=folder_path,
            keep_mua_units=keep_mua_units,
            exclude_shanks=exclude_shanks,
            xml_file_path=xml_file_path,
            # TODO: we can enable this once
            #     a) waveforms on unit columns support conversion factor in NWB
            #     b) write_sorting utils support writing said waveforms properly to a units table
            # load_waveforms=load_waveforms,
            # gain=gain,
        )

    def get_metadata(self):
        session_path = Path(self.source_data["folder_path"])
        session_id = session_path.stem
        xml_file_path = self.source_data.get("xml_file_path", str(session_path / f"{session_id}.xml"))
        metadata = dict(Ecephys=NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=xml_file_path))
        return metadata
