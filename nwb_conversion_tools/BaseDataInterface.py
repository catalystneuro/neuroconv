
from abc import abstractmethod
from copy import deepcopy

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
    
    