"""Authors: Cody Baker and Ben Dichter."""
from abc import abstractmethod
from .utils import get_input_schema, get_metadata_schema


class BaseDataInterface:

    @classmethod
    def get_input_schema(cls):
        input_schema = get_input_schema()
        return input_schema

    def __init__(self, **input_args):
        self.input_args = input_args

    def get_metadata_schema():
        metadata_schema = get_metadata_schema()
        return metadata_schema

    @abstractmethod
    def get_metadata(self):
        pass

    @abstractmethod
    def convert_data(self, nwbfile_path, metadata_dict):
        pass
