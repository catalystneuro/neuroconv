"""Authors: Cody Baker and Ben Dichter."""
from abc import abstractmethod
import warnings

from .utils import get_base_source_schema, get_base_metadata_schema, get_schema_from_method_signature


class BaseDataInterface:

    @classmethod
    def get_source_schema(cls):
        return get_base_source_schema()

    def __init__(self, **source_data):
        self.source_data = source_data

    def get_metadata_schema(self):
        return get_base_metadata_schema()

    def get_metadata(self):
        return dict()

    @classmethod
    def get_conversion_options_schema(cls):
        return get_schema_from_method_signature(cls.convert_data, exclude=['nwbfile', 'metadata'])

    @abstractmethod
    def run_conversion(self, nwbfile_path, metadata):
        pass

    @abstractmethod
    def convert_data(self, nwbfile_path, metadata):
        warnings.warn("The convert_data method should now be renamed to run_conversion "
                      "as of nwb-conversion-tools v0.6.0", DeprecationWarning)
        self.run_conversion(nwbfile_path, metadata)
