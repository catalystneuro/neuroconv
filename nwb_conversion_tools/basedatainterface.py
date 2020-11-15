"""Authors: Cody Baker and Ben Dichter."""
from abc import abstractmethod

from .utils import get_input_schema, get_metadata_schema, get_schema_from_method_signature


class BaseDataInterface:

    @classmethod
    def get_input_schema(cls):
        return get_input_schema()

    def __init__(self, **input_args):
        self.input_args = input_args

    def get_metadata_schema(self):
        return get_metadata_schema()

    def get_metadata(self):
        return dict()

    @classmethod
    def get_conversion_options_schema(cls):
        return get_schema_from_method_signature(cls.convert_data,
                                                exclude=['nwbfile', 'metadata_dict'])

    @abstractmethod
    def convert_data(self, nwbfile_path, metadata_dict):
        pass
