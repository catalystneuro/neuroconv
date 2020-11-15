"""Authors: Cody Baker and Ben Dichter."""
# import segmentationextractors as segx

from .basedatainterface import BaseDataInterface
from .utils import get_schema_from_method_signature


class BaseSegmentationExtractorInterface(BaseDataInterface):
    SegX = None

    @classmethod
    def get_input_schema(cls):
        return get_schema_from_method_signature(cls.SegX)

    def __init__(self, **input_args):
        super().__init__(**input_args)
        self.segmentation_extractor = self.SegX(**input_args)

    def get_metadata_schema(self):
        raise NotImplementedError

    def convert_data(self, nwbfile_path, metadata_dict, stub_test=False):
        raise NotImplementedError
