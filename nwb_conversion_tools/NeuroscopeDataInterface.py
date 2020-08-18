from .BaseRecordingExtractorInterface import BaseRecordingExtractorInterface
from .BaseSortingExtractorInterface import BaseSortingExtractorInterface
import spikeextractors as se


class NeuroscopeRecordingInterface(BaseRecordingExtractorInterface):
    RX = se.NeuroscopeRecordingExtractor


class NeuroscopeSortingInterface(BaseSortingExtractorInterface):
    SX = se.NeuroscopeMultiSortingExtractor
    
    