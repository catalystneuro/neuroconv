"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se

from ....utils.json_schema import get_schema_from_method_signature
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class RecordingTutorialInterface(BaseRecordingExtractorInterface):
    """High-pass recording data interface for demonstrating NWB Conversion Tools usage in tutorials."""

    RX = se.NumpyRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(se.example_datasets.toy_example)
        source_schema['additionalProperties'] = True
        return source_schema

    def __init__(self, **source_data):
        self.recording_extractor = se.example_datasets.toy_example(**source_data)[0]
        self.subset_channels = None
        self.source_data = source_data

    def get_metadata(self):
        metadata = dict(
            Ecephys=dict(
                Device=[
                    dict(
                        description="Device for the NWB Conversion Tools tutorial."
                    )
                ],
                ElectrodeGroup=[
                    dict(
                        name="ElectrodeGroup",
                        description="Electrode group for the NWB Conversion Tools tutorial."
                    )
                ],
                Electrodes=[
                    dict(
                        name="group_name",
                        description="Custom ElectrodeGroup name for these electrodes.",
                        data=["ElectrodeGroup" for x in range(self.recording_extractor.get_num_channels())]
                    ),
                    dict(
                        name="custom_electrodes_column",
                        description="Custom column in the electrodes table for the NWB Conversion Tools tutorial.",
                        data=[x for x in range(self.recording_extractor.get_num_channels())]
                    )
                ],
                ElectricalSeries=dict(
                    name="ElectricalSeries",
                    description="Raw acquisition traces for the NWB Conversion Tools tutorial."
                )
            )
        )
        return metadata
