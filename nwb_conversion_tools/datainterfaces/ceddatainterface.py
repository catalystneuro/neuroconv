"""Authors: Luiz Tauffer and Cody Baker."""
from pathlib import Path

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
        """Compile input schema for the RecordingExtractor."""
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

    @classmethod
    def get_all_channels_info(cls, file_path):
        """Access channel info from SpikeExtractor class."""
        return cls.RX.get_all_channels_info(file_path)

    def get_metadata(self):
        """Auto-populate as much metadata as possible from the high-pass (ap) SpikeGLX format."""
        file_path = Path(self.source_data['file_path'])
        session_id = file_path.stem

        prb = read_probe_file(file_path)
        n_group = len(prb['channel_groups'])
        if n_group > 1:
            raise NotImplementedError("CED metadata for more than a single group is not yet supported.")

        prb_channels = list(prb['channel_groups'].values())[0]['channels']
        prb_xy = list(prb['channel_groups'].values())[0]['geometry']
        self.recording_extractor.set_channel_locations(locations=prb_xy, channel_ids=prb_channels)
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
                        name='probe_electrode_number',
                        description="Probe file channel index.",
                        data=prb_channels
                    ),
                    dict(
                        name='group_name',
                        description="The name of the ElectrodeGroup this electrode is a part of.",
                        data=group_name
                    )
                ],
                ElectricalSeries=dict(
                    name='ElectricalSeries',
                    description="Raw acquisition traces for the high-pass (ap) SpikeGLX data."
                )
            )
        )
        return metadata
