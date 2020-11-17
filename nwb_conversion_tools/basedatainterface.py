"""Authors: Cody Baker and Ben Dichter."""
from abc import abstractmethod

from .utils import get_base_input_schema, get_metadata_schema, get_schema_from_method_signature


class BaseDataInterface:

    @classmethod
    def get_source_schema(cls):
        return get_base_input_schema()

    def __init__(self, **source_data):
        self.source_data = source_data

    def get_metadata_schema(self):
        return get_metadata_schema()

    def get_metadata(self):
        return dict()

    @classmethod
    def get_conversion_options_schema(cls):
        return get_schema_from_method_signature(cls.convert_data, exclude=['nwbfile', 'metadata'])

    @abstractmethod
    def run_conversion(self, nwbfile_path, metadata):
        pass
