"""Authors: Cody Baker and Ben Dichter."""
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
import spikeextractors as se


class NeuroscopeRecordingInterface(BaseRecordingExtractorInterface):
    RX = se.NeuroscopeRecordingExtractor


class NeuroscopeSortingInterface(BaseSortingExtractorInterface):
    SX = se.NeuroscopeMultiSortingExtractor
