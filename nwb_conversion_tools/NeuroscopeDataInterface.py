
from BaseDataInterface import BaseRecordingExtractorInterface
import spikeextractors as se

# then defining an recording interface any SpikeInterface is one line:
class NeuroscopeRecordingInterface(BaseRecordingExtractorInterface):
    RX = se.NeuroscopeRecordingExtractor
    
    