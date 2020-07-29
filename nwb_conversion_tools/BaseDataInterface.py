
from abc import abstractmethod
from copy import deepcopy
import spikeextractors as se
from utils import get_schema_from_method_signature, get_schema_from_hdmf_class
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup,ElectricalSeries
from pynwb.epoch import TimeIntervals

base_schema = dict(
    required=[],
    properties={},
    type='object',
    additionalProperties='false')

root_schema = deepcopy(base_schema)
root_schema.update({
    "$schema": "http://json-schema.org/draft-07/schema#",
})

class BaseDataInterface:
    
    @classmethod
    @abstractmethod
    def get_input_schema(cls):
        pass
        
    def __init__(self, **input_args):
        self.input_args = input_args

    @abstractmethod
    def get_metadata_schema():
        pass

    @abstractmethod
    def convert_data(self, nwbfile_path, metadata_dict):
        pass
    
class BaseRecordingExtractorInterface(BaseDataInterface):
    RX = None
    
    @classmethod
    def get_input_schema(cls):
        return get_schema_from_method_signature(cls.RX)
    
    def __init__(self, **input_args):
        super().__init__(**input_args)
        self.recording_extactor = self.RX(**input_args)
    
    def get_metadata_schema(self):
        metadata_schema = deepcopy(base_schema)
        
        # ideally most of this be automatically determined from pynwb docvals
        metadata_schema['properties']['Device'] = get_schema_from_hdmf_class(Device)
        metadata_schema['properties']['ElectrodeGroup'] = get_schema_from_hdmf_class(ElectrodeGroup)
        metadata_schema['properties']['ElectricalSeries'] = get_schema_from_hdmf_class(ElectricalSeries)
        metadata_schema['properties']['Epochs'] = get_schema_from_hdmf_class(TimeIntervals)
        required_fields = ['Device','ElectrodeGroup','ElectricalSeries']
        for field in required_fields:
            metadata_schema['required'].append(field)
        
        return metadata_schema # RecordingExtractor metadata json-schema here.
    
    def convert_data(self, nwbfile_path, metadata_dict, stub_test=False):
        if stub_test:
            # placeholder
            a = 1
        else:
            # placeholder
            a = 2

    
# then defining an recording interface any SpikeInterface is one line:
class NeuroscopeRecordingInterface(BaseRecordingExtractorInterface):
    RX = se.NeuroscopeRecordingExtractor
    
    