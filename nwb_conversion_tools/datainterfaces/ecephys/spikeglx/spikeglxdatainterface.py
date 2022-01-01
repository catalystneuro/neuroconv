"""Authors: Cody Baker and Ben Dichter."""
from datetime import datetime
from pathlib import Path
from typing import Optional

from spikeextractors import SpikeGLXRecordingExtractor, SubRecordingExtractor, RecordingExtractor
from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ....utils.json_schema import get_schema_from_method_signature, get_schema_from_hdmf_class, FilePathType


def fetch_spikeglx_metadata(file_path: FilePathType, recording: RecordingExtractor, metadata: dict):
    file_path = Path(file_path)
    session_id = file_path.parent.stem

    if isinstance(recording, SubRecordingExtractor):
        n_shanks = int(recording._parent_recording._meta.get("snsShankMap", [1, 1])[1])
        session_start_time = datetime.fromisoformat(recording._parent_recording._meta["fileCreateTime"]).astimezone()
    else:
        n_shanks = int(recording._meta.get("snsShankMap", [1, 1])[1])
        session_start_time = datetime.fromisoformat(recording._meta["fileCreateTime"]).astimezone()
    if n_shanks > 1:
        raise NotImplementedError("SpikeGLX metadata for more than a single shank is not yet supported.")

    metadata["NWBFile"] = dict(session_start_time=session_start_time.strftime("%Y-%m-%dT%H:%M:%S"))

    # Electrodes columns descriptions
    metadata["Ecephys"]["Electrodes"] = [
        dict(name="shank_electrode_number", description="0-indexed channel within a shank."),
        dict(name="shank_group_name", description="The name of the ElectrodeGroup this electrode is a part of."),
    ]


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting the high-pass (ap) SpikeGLX format."""

    RX = SpikeGLXRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(class_method=cls.__init__, exclude=["x_pitch", "y_pitch"])
        source_schema["properties"]["file_path"]["description"] = "Path to SpikeGLX file."
        return source_schema

    def __init__(self, file_path: FilePathType, stub_test: Optional[bool] = False):
        super().__init__(file_path=str(file_path))
        if stub_test:
            self.subset_channels = [0, 1]

        # Set electrodes properties
        for ch in self.recording_extractor.get_channel_ids():
            self.recording_extractor.set_channel_property(
                channel_id=ch, property_name="shank_electrode_number", value=ch
            )
            self.recording_extractor.set_channel_property(
                channel_id=ch, property_name="shank_group_name", value="Shank1"
            )

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_raw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        fetch_spikeglx_metadata(
            file_path=self.source_data["file_path"], recording=self.recording_extractor, metadata=metadata
        )
        metadata["Ecephys"]["ElectricalSeries_raw"] = dict(
            name="ElectricalSeries_raw", description="Raw acquisition traces for the high-pass (ap) SpikeGLX data."
        )
        return metadata

    def get_conversion_options(self):
        conversion_options = dict(write_as="raw", es_key="ElectricalSeries_raw", stub_test=False)
        return conversion_options


class SpikeGLXLFPInterface(BaseLFPExtractorInterface):
    """Primary data interface class for converting the low-pass (ap) SpikeGLX format."""

    RX = SpikeGLXRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the RecordingExtractor."""
        source_schema = get_schema_from_method_signature(class_method=cls.__init__, exclude=["x_pitch", "y_pitch"])
        source_schema["properties"]["file_path"]["description"] = "Path to SpikeGLX file."
        return source_schema

    def __init__(self, file_path: FilePathType, stub_test: Optional[bool] = False):
        super().__init__(file_path=str(file_path))
        if stub_test:
            self.subset_channels = [0, 1]

        # Set electrodes properties
        for ch in self.recording_extractor.get_channel_ids():
            self.recording_extractor.set_channel_property(
                channel_id=ch, property_name="shank_electrode_number", value=ch
            )
            self.recording_extractor.set_channel_property(
                channel_id=ch, property_name="shank_group_name", value="Shank1"
            )

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_lfp=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        fetch_spikeglx_metadata(
            file_path=self.source_data["file_path"], recording=self.recording_extractor, metadata=metadata
        )
        metadata["Ecephys"]["ElectricalSeries_lfp"].update(
            description="LFP traces for the processed (lf) SpikeGLX data."
        )
        return metadata

    def get_conversion_options(self):
        conversion_options = dict(stub_test=False)
        return conversion_options
