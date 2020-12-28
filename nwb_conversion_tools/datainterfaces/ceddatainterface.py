"""Authors: Luiz Tauffer and Cody Baker."""
from pathlib import Path
import numpy as np

import spikeextractors as se

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..json_schema_utils import get_schema_from_method_signature


def read_probe_file(file_path):
    pass


class CEDRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a CEDRecordingExtractor."""

    RX = se.CEDRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(
            class_method=cls.RX.__init__,
            exclude=['smrx_channel_ids']
        )
        source_schema.update(additionalProperties=True)
        source_schema['properties'].update(
            file_path=dict(
                type=source_schema['properties']['file_path']['type'],
                format="file",
                description="path to data file"
            )
        )
        return source_schema

    def get_metadata(self):
        file_path = Path(self.source_data['file_path'])
        session_id = file_path.stem

        prb_channels = [
            42, 36, 32, 38, 39, 47, 45, 37, 44, 46, 48, 35, 34, 40, 41, 43, 62, 60, 58, 56, 54, 52, 50, 33, 49, 51, 53,
            55, 57, 59, 61, 63, 1, 3, 5, 7, 9, 11, 13, 30, 14, 12, 10, 8, 6, 4, 2, 0, 21, 27, 31, 25, 24, 16, 18, 26,
            19, 17, 15, 28, 29, 23, 22, 20
        ]
        prb_locations = [[0, x * 20] for x in range(len(prb_channels))]
        self.recording_extractor.set_channel_locations(locations=np.array(prb_locations)[prb_channels, :])
        group_name = ["Group1"] * len(prb_channels)

        metadata = dict(
            NWBFile=dict(session_id=session_id),
            Ecephys=dict(
                Device=[
                    dict(
                        description="Ecephys probe used for recording."
                    )
                ],
                ElectrodeGroup=[
                    dict(
                        name='Group1',
                        description="Group1 electrodes."
                    )
                ],
                Electrodes=[
                    dict(
                        name='group_name',
                        description="The name of the ElectrodeGroup this electrode is a part of.",
                        data=group_name
                    ),
                    dict(
                        name='probe_electrode_number',
                        description="Probe file channel index.",
                        data=prb_channels
                    )
                ],
                ElectricalSeries=dict(
                    name='ElectricalSeries',
                    description="Raw acquisition traces for CED data from rhd channels."
                )
            )
        )
        return metadata
