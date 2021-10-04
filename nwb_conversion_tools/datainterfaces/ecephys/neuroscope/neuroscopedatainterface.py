"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
from typing import Optional

import spikeextractors as se
from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils.json_schema import FilePathType, FolderPathType, OptionalFilePathType, get_schema_from_hdmf_class

try:
    import lxml
    from .neuroscope_utils import (
        get_xml_file_path, get_channel_groups, get_shank_channels, add_recording_extractor_properties
    )

    HAVE_LXML = True
except ImportError:
    HAVE_LXML = False
INSTALL_MESSAGE = "Please install lxml to use this extractor!"


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
        if get_shank_channels(xml_file_path=xml_file_path) is not None:
            ecephys_metadata["Electrodes"].append(
                dict(name="spike_detection", description="If the channel was used for spike detection.")
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

        super().__init__(file_path=file_path, gain=gain, xml_file_path=xml_file_path)
        if xml_file_path is None:
            xml_file_path = get_xml_file_path(data_file_path=self.source_data["file_path"])
        add_recording_extractor_properties(recording_extractor=self.recording_extractor, xml_file_path=xml_file_path)

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_raw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata["Ecephys"].update(
            NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=self.source_data["xml_file_path"])
        )
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

        super(NeuroscopeRecordingInterface, self).__init__(
            folder_path=folder_path, gain=gain, xml_file_path=xml_file_path
        )
        if xml_file_path is None:
            xml_file_path = get_xml_file_path(data_file_path=self.source_data["folder_path"])
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
        super().__init__(file_path=file_path, gain=gain, xml_file_path=xml_file_path)
        if xml_file_path is None:
            xml_file_path = get_xml_file_path(data_file_path=self.source_data["file_path"])
        add_recording_extractor_properties(recording_extractor=self.recording_extractor, xml_file_path=xml_file_path)

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata["Ecephys"].update(
            NeuroscopeRecordingInterface.get_ecephys_metadata(xml_file_path=self.source_data["xml_file_path"])
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
