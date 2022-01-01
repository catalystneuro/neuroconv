"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

import spikeextractors as se
from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils.json_schema import get_schema_from_hdmf_class, FilePathType

try:
    from pyintan.intan import read_rhd, read_rhs

    HAVE_PYINTAN = True
except ImportError:
    HAVE_PYINTAN = False
INSTALL_MESSAGE = "Please install pyintan to use this extractor!"


class IntanRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a IntanRecordingExtractor."""

    RX = se.IntanRecordingExtractor

    def __init__(self, file_path: FilePathType):
        assert HAVE_PYINTAN, INSTALL_MESSAGE
        super().__init__(file_path=file_path)
        if ".rhd" in Path(self.source_data["file_path"]).suffixes:
            intan_file_metadata = read_rhd(self.source_data["file_path"])[1]
        else:
            intan_file_metadata = read_rhs(self.source_data["file_path"])[1]
        exclude_chan_types = ["AUX", "ADC", "VDD"]
        valid_channels = [
            x for x in intan_file_metadata if not any([y in x["native_channel_name"] for y in exclude_chan_types])
        ]

        group_names = [channel["native_channel_name"].split("-")[0] for channel in valid_channels]
        unique_group_names = set(group_names)
        group_electrode_numbers = [channel["native_order"] for channel in valid_channels]

        channel_ids = self.recording_extractor.get_channel_ids()
        for channel_id, channel_group in zip(channel_ids, group_names):
            self.recording_extractor.set_channel_property(
                channel_id=channel_id, property_name="group_name", value=f"Group{channel_group}"
            )

        if len(unique_group_names) > 1:
            for channel_id, group_electrode_number in zip(channel_ids, group_electrode_numbers):
                self.recording_extractor.set_channel_property(
                    channel_id=channel_id, property_name="group_electrode_number", value=group_electrode_number
                )

        custom_names = [channel["custom_channel_name"] for channel in valid_channels]
        if any(custom_names):
            for channel_id, custom_name in zip(channel_ids, custom_names):
                self.recording_extractor.set_channel_property(
                    channel_id=channel_id, property_name="custom_channel_name", value=custom_name
                )

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_raw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        channel_ids = self.recording_extractor.get_channel_ids()
        property_names = self.recording_extractor.get_shared_channel_property_names()
        ecephys_metadata = dict(
            Ecephys=dict(
                Device=[
                    dict(
                        name="Intan",
                        description="Intan recording",
                        manufacturer="Intan",
                    ),
                ],
                ElectrodeGroup=[
                    dict(
                        name=group_name,
                        description=f"Group {group_name} electrodes.",
                        device="Intan",
                        location="",
                    )
                    for group_name in set(
                        [
                            self.recording_extractor.get_channel_property(
                                channel_id=channel_id, property_name="group_name"
                            )
                            for channel_id in channel_ids
                        ]
                    )
                ],
                Electrodes=[
                    dict(name="group_name", description="The name of the ElectrodeGroup this electrode is a part of.")
                ],
                ElectricalSeries_raw=dict(name="ElectricalSeries_raw", description="Raw acquisition traces."),
            )
        )
        if "group_electrode_number" in property_names:
            ecephys_metadata["Ecephys"]["Electrodes"].append(
                dict(name="group_electrode_number", description="0-indexed channel within a group.")
            )
        if "custom_channel_name" in property_names:
            ecephys_metadata["Ecephys"]["Electrodes"].append(
                dict(name="custom_channel_name", description="Custom channel name assigned in Intan.")
            )
        return ecephys_metadata
