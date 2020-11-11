"""Authors: Cody Baker and Ben Dichter."""
from spikeextractors import SpikeGLXRecordingExtractor, SubRecordingExtractor

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeRecordingExtractor."""

    RX = SpikeGLXRecordingExtractor

    def convert_data(self, nwbfile, metadata_dict: None, stub_test: bool = False, sync_with_ttl: bool = True):
        """Primary function for converting recording extractor data to nwb."""
        if sync_with_ttl:
            ttl, states = self.recording_extractor.get_ttl_events()
            rising_times = ttl[states == 1]
            self.recording_extractor = SubRecordingExtractor(self.recording_extractor, start_frame=rising_times[0])
        super().convert_data(nwbfile=nwbfile, metadata_dict=metadata_dict, stub_test=stub_test)
