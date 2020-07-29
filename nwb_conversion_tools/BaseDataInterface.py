
from abc import abstractmethod

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
    
    