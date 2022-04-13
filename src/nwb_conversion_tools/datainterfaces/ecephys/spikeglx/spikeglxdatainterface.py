"""Authors: Cody Baker, Heberto Mayorquin and Ben Dichter."""
from datetime import datetime
from pathlib import Path
from typing import Optional

import spikeextractors as se
from spikeinterface import BaseRecording
from spikeinterface.extractors import SpikeGLXRecordingExtractor
from spikeinterface.core.old_api_utils import OldToNewRecording

from spikeextractors import SubRecordingExtractor, RecordingExtractor
from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ....utils import get_schema_from_method_signature, get_schema_from_hdmf_class, FilePathType, dict_deep_update


def fetch_spikeglx_metadata(recording: BaseRecording, metadata: dict):
    """
    Fetches the session_start_time from the meta readings and adds it to the metadata.
    """

    # Support for old spikeextractors objects
    recording = recording._kwargs.get("oldapi_recording_extractor", recording)
    if isinstance(recording, RecordingExtractor):
        if isinstance(recording, SubRecordingExtractor):
            meta = recording._parent_recording._meta
        else:
            meta = recording._meta
        # imDatPrb_type 0 and 21 correspond to single shank channels
        # see https://billkarsh.github.io/SpikeGLX/help/imroTables/
        imDatPrb_type = meta["imDatPrb_type"]
        if imDatPrb_type not in ["0", "21"]:
            raise NotImplementedError(
                "More than a single shank is not supported in spikeextractors, use the new spikeinterface."
            )
    else:
        stream_id = recording._kwargs["stream_id"]
        meta = recording.neo_reader.signals_info_dict[(0, stream_id)]["meta"]

    extracted_start_time = meta.get("fileCreateTime", None)
    if extracted_start_time:
        metadata = dict_deep_update(metadata, dict(NWBFile=dict(session_start_time=extracted_start_time)))

    # Electrodes columns descriptions
    metadata["Ecephys"]["Electrodes"] = [
        dict(name="shank_electrode_number", description="0-indexed channel within a shank."),
        dict(name="shank_group_name", description="The name of the ElectrodeGroup this electrode is a part of."),
    ]

    return metadata


def add_recording_extractor_properties(recording_extractor: BaseRecording):
    """Automatically add properties to RecordingExtractor object."""
    channel_ids = recording_extractor.get_channel_ids()
    values = recording_extractor.ids_to_indices(channel_ids)
    recording_extractor.set_property(key="shank_electrode_number", ids=channel_ids, values=values)
    values = ["Shank1"] * len(channel_ids)
    recording_extractor.set_property(key="shank_group_name", ids=channel_ids, values=values)


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting the high-pass (ap) SpikeGLX format."""

    RX = SpikeGLXRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(class_method=cls.__init__, exclude=["x_pitch", "y_pitch"])
        source_schema["properties"]["file_path"]["description"] = "Path to SpikeGLX file."
        return source_schema

    def __init__(
        self,
        file_path: FilePathType,
        stub_test: Optional[bool] = False,
        spikeextractors_backend: Optional[bool] = False,
    ):

        if spikeextractors_backend:
            self.RX = se.SpikeGLXRecordingExtractor
            super().__init__(file_path=str(file_path))
            self.recording_extractor = OldToNewRecording(oldapi_recording_extractor=self.recording_extractor)
        else:
            file_path = Path(file_path)
            folder_path = file_path.parent
            stream_id = "".join(file_path.suffixes[:-1])[1:]
            super().__init__(folder_path=folder_path, stream_id=stream_id)
            self.source_data["file_path"] = str(file_path)

        if stub_test:
            self.subset_channels = [0, 1]

        # Set electrodes properties
        add_recording_extractor_properties(self.recording_extractor)

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_raw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata = fetch_spikeglx_metadata(recording=self.recording_extractor, metadata=metadata)
        metadata["Ecephys"]["ElectricalSeries_raw"] = dict(
            name="ElectricalSeries_raw", description="Raw acquisition traces for the high-pass (ap) SpikeGLX data."
        )
        return metadata

    def get_conversion_options(self):
        conversion_options = dict(write_as="raw", es_key="ElectricalSeries_raw", stub_test=False)
        return conversion_options


class SpikeGLXLFPInterface(BaseLFPExtractorInterface):
    """Primary data interface class for converting the low-pass (lf) SpikeGLX format."""

    RX = SpikeGLXRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the RecordingExtractor."""
        source_schema = get_schema_from_method_signature(class_method=cls.__init__, exclude=["x_pitch", "y_pitch"])
        source_schema["properties"]["file_path"]["description"] = "Path to SpikeGLX file."
        return source_schema

    def __init__(
        self,
        file_path: FilePathType,
        stub_test: Optional[bool] = False,
        spikeextractors_backend: Optional[bool] = False,
    ):
        if spikeextractors_backend:
            self.RX = se.SpikeGLXRecordingExtractor
            super().__init__(file_path=str(file_path))
            self.recording_extractor = OldToNewRecording(oldapi_recording_extractor=self.recording_extractor)
        else:
            file_path = Path(file_path)
            folder_path = file_path.parent
            stream_id = "".join(file_path.suffixes[:-1])[1:]
            super().__init__(folder_path=folder_path, stream_id=stream_id)
            self.source_data["file_path"] = str(file_path)

        if stub_test:
            self.subset_channels = [0, 1]

        # Set electrodes properties
        add_recording_extractor_properties(self.recording_extractor)

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_lfp=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata = fetch_spikeglx_metadata(recording=self.recording_extractor, metadata=metadata)
        metadata["Ecephys"]["ElectricalSeries_lfp"].update(
            description="LFP traces for the processed (lf) SpikeGLX data."
        )
        return metadata

    def get_conversion_options(self):
        conversion_options = dict(stub_test=False)
        return conversion_options
