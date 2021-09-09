"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se

from pynwb.ecephys import ElectricalSeries

from ....utils.json_schema import get_schema_from_method_signature, get_schema_from_hdmf_class
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class RecordingTutorialInterface(BaseRecordingExtractorInterface):
    """High-pass recording data interface for demonstrating NWB Conversion Tools usage in tutorials."""

    RX = se.NumpyRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(se.example_datasets.toy_example)
        source_schema["additionalProperties"] = True
        return source_schema

    def __init__(self, **source_data):
        self.recording_extractor = se.example_datasets.toy_example(**source_data)[0]
        self.subset_channels = None

        # Set manual group names at the recording extractor level
        for channel_id in self.recording_extractor.get_channel_ids():
            self.recording_extractor.set_channel_property(
                channel_id=channel_id,
                property_name="group_name",
                value="ElectrodeGroup"
            )

        # Set any other type of value that is intended to be written as a column to the final electrodes table
        for channel_id in self.recording_extractor.get_channel_ids():
            self.recording_extractor.set_channel_property(
                channel_id=channel_id,
                property_name="custom_electrodes_column",
                value="A custom value"
            )

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_raw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        metadata = dict(
            Ecephys=dict(
                Device=[dict(name="TutorialDevice", description="Device for the NWB Conversion Tools tutorial.")],
                ElectrodeGroup=[
                    dict(
                        name="ElectrodeGroup",
                        description="Electrode group for the NWB Conversion Tools tutorial.",
                        location="Somewhere in the brain",  # "unknown" if you don't know for sure
                        device="TutorialDevice",
                    )
                ],
                # Set the description metadata for the extra columns added during initialization
                Electrodes=[
                    dict(
                        name="group_name",
                        description="Custom ElectrodeGroup name for these electrodes.",
                    ),
                    dict(
                        name="custom_electrodes_column",
                        description="Custom column in the electrodes table for the NWB Conversion Tools tutorial.",
                    ),
                ],
                ElectricalSeries_raw=dict(
                    name="ElectricalSeries_raw",
                    description="Raw acquisition traces for the NWB Conversion Tools tutorial."
                ),
            )
        )
        return metadata

    def get_conversion_options(self):
        conversion_options = dict(write_as="raw", es_key="ElectricalSeries_raw", stub_test=False)
        return conversion_options
