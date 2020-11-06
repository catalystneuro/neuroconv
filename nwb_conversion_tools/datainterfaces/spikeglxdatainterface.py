"""Authors: Cody Baker and Ben Dichter."""
from spikeextractors import SpikeGLXRecordingExtractor, SubRecordingExtractor

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    RX = SpikeGLXRecordingExtractor

    @classmethod
    def get_input_schema(cls):
        input_schema = super().get_input_schema()
        input_schema['properties'].update(sync_with_ttl=dict(type='boolean', default=True))
        return input_schema

    def __init__(self, **input_args):
        if 'sync_with_ttl' in input_args:
            sync_with_ttl = input_args['sync_with_ttl']
            input_args.pop('sync_with_ttl')
        else:
            sync_with_ttl = False
        super().__init__(**input_args)
        if sync_with_ttl:
            recording_ap = self.recording_extractor
            ttl, states = recording_ap.get_ttl_events()
            rising_times = ttl[states == 1]
            self.recording_extractor = SubRecordingExtractor(self.recording_extractor, start_frame=rising_times[0])
