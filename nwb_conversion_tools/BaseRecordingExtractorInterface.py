
from copy import deepcopy
from .utils import get_base_schema, get_schema_from_method_signature, \
                   get_schema_from_hdmf_class
from .BaseDataInterface import BaseDataInterface
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup, ElectricalSeries
import spikeextractors as se
    
class BaseRecordingExtractorInterface(BaseDataInterface):
    RX = None
    
    @classmethod
    def get_input_schema(cls):
        return get_schema_from_method_signature(cls.RX)
    
    def __init__(self, **input_args):
        super().__init__(**input_args)
        self.recording_extractor = self.RX(**input_args)
    
    def get_metadata_schema(self):
        metadata_schema = deepcopy(get_base_schema())
        
        # ideally most of this be automatically determined from pynwb docvals
        metadata_schema['properties']['Device'] = get_schema_from_hdmf_class(Device)
        metadata_schema['properties']['ElectrodeGroup'] = get_schema_from_hdmf_class(ElectrodeGroup)
        metadata_schema['properties']['ElectricalSeries'] = get_schema_from_hdmf_class(ElectricalSeries)
        required_fields = ['Device','ElectrodeGroup','ElectricalSeries']
        for field in required_fields:
            metadata_schema['required'].append(field)
        
        return metadata_schema # RecordingExtractor metadata json-schema here.
    
    def convert_data(self, nwbfile, metadata_dict, stub_test=False):
        if stub_test:
            num_test_channels = 10
            if self.recording_extractor.get_num_channels() <= num_test_channels:
                test_ids = self.recording_extractor.get_channel_ids()
            else:
                test_ids = self.recording_extractor.get_channel_ids()[0:num_test_channels]
            end_frame = min([1000, self.recording_extractor.get_num_frames()])
                
            test_recording_extractor = se.SubRecordingExtractor(self.recording_extractor,
                                                                channel_ids=test_ids,
                                                                start_frame=0,
                                                                end_frame=end_frame)
            
            se.NwbRecordingExtractor.write_recording(test_recording_extractor,
                                                     nwbfile=nwbfile,
                                                     metadata=metadata_dict)
        else:
            se.NwbRecordingExtractor.write_recording(self.recording_extractor,
                                                     nwbfile=nwbfile,
                                                     metadata=metadata_dict)
    
    
