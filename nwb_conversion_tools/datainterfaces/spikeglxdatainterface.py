"""Authors: Cody Baker and Ben Dichter."""
from datetime import datetime
from pathlib import Path
from typing import Union, Optional
from spikeextractors import SpikeGLXRecordingExtractor, SubRecordingExtractor
from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ..utils.json_schema import get_schema_from_method_signature, get_schema_from_hdmf_class

PathType = Union[str, Path, None]


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting the high-pass (ap) SpikeGLX format."""

    RX = SpikeGLXRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the RecordingExtractor."""
        source_schema = get_schema_from_method_signature(
            class_method=cls.RX.__init__,
            exclude=['x_pitch', 'y_pitch']
        )
        source_schema['properties']['file_path']['format'] = 'file'
        source_schema['properties']['file_path']['description'] = 'Path to SpikeGLX file.'
        return source_schema

    def __init__(self, file_path: PathType, stub_test: Optional[bool] = False):
        super().__init__(file_path=str(file_path))
        if stub_test:
            self.subset_channels = [0, 1]

    def get_metadata_schema(self):
        """Compile metadata schema for the RecordingExtractor."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema['properties']['Ecephys']['properties'].update(
            ElectricalSeries_raw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self):
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        metadata = super().get_metadata()

        file_path = Path(self.source_data['file_path'])
        session_id = file_path.parent.stem

        if isinstance(self.recording_extractor, SubRecordingExtractor):
            n_shanks = int(self.recording_extractor._parent_recording._meta['snsShankMap'][1])
            session_start_time = datetime.fromisoformat(
                self.recording_extractor._parent_recording._meta['fileCreateTime']
            ).astimezone()
        else:
            n_shanks = int(self.recording_extractor._meta['snsShankMap'][1])
            session_start_time = datetime.fromisoformat(self.recording_extractor._meta['fileCreateTime']).astimezone()
        if n_shanks > 1:
            raise NotImplementedError("SpikeGLX metadata for more than a single shank is not yet supported.")

        channels = self.recording_extractor.get_channel_ids()
        shank_electrode_number = channels
        shank_group_name = ["Shank1" for x in channels]

        metadata['NWBFile'] = dict(
            session_start_time=session_start_time.strftime('%Y-%m-%dT%H:%M:%S'),
        )

        metadata['Ecephys'] = dict(
            Device=[
                dict(
                    name='Device_ecephys',
                    description=f"More details for the high-pass (ap) data found in {session_id}.ap.meta!"
                )
            ],
            ElectrodeGroup=[
                dict(
                    name='Shank1',
                    description="Shank1 electrodes.",
                    location='no description', 
                    device='Device_ecephys'
                )
            ],
            Electrodes=[
                dict(
                    name='shank_electrode_number',
                    description="0-indexed channel within a shank.",
                    data=shank_electrode_number
                ),
                dict(
                    name='group_name',
                    description="The name of the ElectrodeGroup this electrode is a part of.",
                    data=shank_group_name
                )
            ],
            ElectricalSeries_raw=dict(
                name='ElectricalSeries',
                description="Raw acquisition traces for the high-pass (ap) SpikeGLX data."
            )
        )

        return metadata


class SpikeGLXLFPInterface(BaseLFPExtractorInterface):
    """Primary data interface class for converting the low-pass (ap) SpikeGLX format."""

    RX = SpikeGLXRecordingExtractor
