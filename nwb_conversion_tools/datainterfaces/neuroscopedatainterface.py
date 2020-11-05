"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface


class NeuroscopeRecordingInterface(BaseRecordingExtractorInterface):
    RX = se.NeuroscopeRecordingExtractor


class NeuroscopeSortingInterface(BaseSortingExtractorInterface):
    SX = se.NeuroscopeMultiSortingExtractor
