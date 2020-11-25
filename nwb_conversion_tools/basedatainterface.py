"""Authors: Cody Baker and Ben Dichter."""
from abc import abstractmethod
import warnings

from .json_schema_utils import (
    get_base_schema, get_schema_from_method_signature, fill_defaults)


class BaseDataInterface:

    @staticmethod
    def get_ecephys_metadata():
        raise NotImplementedError("The get_ecephys_metadata method has not been configured for this class!")

    @classmethod
    def get_source_schema(cls):
        return get_base_schema()

    @classmethod
    def get_conversion_options_schema(cls):
        return get_schema_from_method_signature(cls.run_conversion, exclude=['nwbfile', 'metadata'])

    def __init__(self, **source_data):
        self.source_data = source_data

    def get_metadata_schema(self):
        metadata_schema = get_base_schema(
            id_='metadata.schema.json',
            root=True,
            title='Metadata',
            description='Schema for the metadata',
            version="0.1.0",
        )
        return metadata_schema

    def get_metadata(self):
        return dict()

    @abstractmethod
    def run_conversion(self, nwbfile_path: str, metadata: dict, **conversion_options):
        pass

    @abstractmethod
    def convert_data(self, nwbfile_path, metadata, **conversion_options):
        warnings.warn("The convert_data method should now be renamed to run_conversion "
                      "as of nwb-conversion-tools v0.6.0", DeprecationWarning)
        self.run_conversion(nwbfile_path, metadata, **conversion_options)
