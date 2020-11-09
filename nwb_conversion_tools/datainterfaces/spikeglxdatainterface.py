"""Authors: Cody Baker and Ben Dichter."""
from spikeextractors import SpikeGLXRecordingExtractor

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a NeuroscopeRecordingExtractor."""

    RX = SpikeGLXRecordingExtractor

    def get_metadata():
        """Retrieve Ecephys metadata specific to the SpikeGLX format."""
        # TODO
        raise NotImplementedError
