"""Author: Ben Dichter."""
import roiextractors as re

from .basedatainterface import BaseDataInterface
from .json_schema_utils import get_schema_from_method_signature, fill_defaults


class BaseImagingExtractorInterface(BaseDataInterface):
    IX = None

    @classmethod
    def get_input_schema(cls):
        return get_schema_from_method_signature(cls.IX.__init__)

    def __init__(self, **input_args):
        super().__init__(**input_args)
        self.imaging_extractor = self.IX(**input_args)

    def convert_data(self, nwbfile, metadata_dict):
        re.NwbImagingExtractor.write_imaging(
            self.imaging_extractor,
            nwbfile=nwbfile,
            metadata=metadata_dict
        )
