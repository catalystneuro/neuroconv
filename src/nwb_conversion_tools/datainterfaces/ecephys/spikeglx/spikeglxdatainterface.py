"""Authors: Cody Baker, Heberto Mayorquin and Ben Dichter."""
from pathlib import Path
from typing import Optional

import spikeextractors as se
import probeinterface as pi

from spikeinterface import BaseRecording
from spikeinterface.extractors import SpikeGLXRecordingExtractor
from spikeinterface.core.old_api_utils import OldToNewRecording

from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ....utils import get_schema_from_method_signature, get_schema_from_hdmf_class, FilePathType, dict_deep_update
from .spikeglx_utils import (
    get_session_start_time,
    _fetch_metadata_dic_for_spikextractors_spikelgx_object,
    _assert_single_shank_for_spike_extractors,
    fetch_stream_id_for_spikelgx_file,
)


def add_recording_extractor_properties(recording_extractor: BaseRecording):
    """Automatically add properties shank and electrode number for spikeglx."""

    probe = recording_extractor.get_probe()
    channel_ids = recording_extractor.get_channel_ids()
    
    if probe.get_shank_count() > 1:
        shank_electrode_number = [contact_id.split(":")[1] for contact_id in probe.contact_ids]
        shank_group_name = [contact_id.split(":")[0] for contact_id in probe.contact_ids]
    else:
        shank_electrode_number = recording_extractor.ids_to_indices(channel_ids)
        shank_group_name = ["s0"] * len(channel_ids)

    recording_extractor.set_property(key="shank_electrode_number", ids=channel_ids, values=shank_electrode_number)
    recording_extractor.set_property(key="shank_group_name", ids=channel_ids, values=shank_group_name)


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
        self.stub_test = stub_test
        self.stream_id = fetch_stream_id_for_spikelgx_file(file_path)

        if spikeextractors_backend:
            self.RX = se.SpikeGLXRecordingExtractor
            super().__init__(file_path=str(file_path))
            _assert_single_shank_for_spike_extractors(self.recording_extractor)
            self.meta = _fetch_metadata_dic_for_spikextractors_spikelgx_object(self.recording_extractor)
            self.recording_extractor = OldToNewRecording(oldapi_recording_extractor=self.recording_extractor)
        else:
            file_path = Path(file_path)
            folder_path = file_path.parent
            super().__init__(folder_path=folder_path, stream_id=self.stream_id)
            self.source_data["file_path"] = str(file_path)
            self.meta = self.recording_extractor.neo_reader.signals_info_dict[(0, self.stream_id)]["meta"]

        # Mount the probe
        meta_filename = str(file_path).replace(".bin", ".meta").replace(".lf", ".ap")
        probe = pi.read_spikeglx(meta_filename)
        self.recording_extractor.set_probe(probe, in_place=True)
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
        session_start_time = get_session_start_time(self.meta)
        if session_start_time:
            metadata = dict_deep_update(metadata, dict(NWBFile=dict(session_start_time=str(session_start_time))))

        # Electrodes columns descriptions
        metadata["Ecephys"]["Electrodes"] = [
            dict(name="shank_electrode_number", description="0-indexed channel within a shank."),
            dict(name="shank_group_name", description="The name of the ElectrodeGroup this electrode is a part of."),
        ]

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

        self.stub_test = stub_test
        self.stream_id = fetch_stream_id_for_spikelgx_file(file_path)

        if spikeextractors_backend:
            self.RX = se.SpikeGLXRecordingExtractor
            super().__init__(file_path=str(file_path))
            _assert_single_shank_for_spike_extractors(self.recording_extractor)
            self.meta = _fetch_metadata_dic_for_spikextractors_spikelgx_object(self.recording_extractor)
            self.recording_extractor = OldToNewRecording(oldapi_recording_extractor=self.recording_extractor)
        else:
            file_path = Path(file_path)
            folder_path = file_path.parent
            super().__init__(folder_path=folder_path, stream_id=self.stream_id)
            self.source_data["file_path"] = str(file_path)
            self.meta = self.recording_extractor.neo_reader.signals_info_dict[(0, self.stream_id)]["meta"]

        # Mount the probe
        meta_filename = str(file_path).replace(".bin", ".meta").replace(".lf", ".ap")
        probe = pi.read_spikeglx(meta_filename)
        self.recording_extractor.set_probe(probe, in_place=True)


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
        session_start_time = get_session_start_time(self.meta)
        if session_start_time:
            metadata = dict_deep_update(metadata, dict(NWBFile=dict(session_start_time=str(session_start_time))))

        # Electrodes columns descriptions
        metadata["Ecephys"]["Electrodes"] = [
            dict(name="shank_electrode_number", description="0-indexed channel within a shank."),
            dict(name="shank_group_name", description="The name of the ElectrodeGroup this electrode is a part of."),
        ]
        metadata["Ecephys"]["ElectricalSeries_lfp"].update(
            description="LFP traces for the processed (lf) SpikeGLX data."
        )
        return metadata

    def get_conversion_options(self):
        conversion_options = dict(stub_test=False)
        return conversion_options
