"""Authors: Cody Baker and Ben Dichter."""
from spikeextractors import SpikeGLXRecordingExtractor

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeRecordingExtractor."""

    RX = SpikeGLXRecordingExtractor

    def get_metadata(self):
        """Auto-populate as much of the metadata as possible from the SpikeGLX format."""
        re_metadata = dict(
            Ecephys=dict(
            )
        )
        return re_metadata
