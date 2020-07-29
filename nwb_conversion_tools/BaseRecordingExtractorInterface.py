
from copy import deepcopy
from .utils import get_base_schema, get_schema_from_method_signature, \
                   get_schema_from_hdmf_class
from .BaseDataInterface import BaseDataInterface
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup,ElectricalSeries
from pynwb.epoch import TimeIntervals
    
class BaseRecordingExtractorInterface(BaseDataInterface):
    RX = None
    
    @classmethod
    def get_input_schema(cls):
        return get_schema_from_method_signature(cls.RX)
    
    def __init__(self, **input_args):
        super().__init__(**input_args)
        self.recording_extactor = self.RX(**input_args)
    
    def get_metadata_schema(self):
        metadata_schema = deepcopy(get_base_schema())
        
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
    
    