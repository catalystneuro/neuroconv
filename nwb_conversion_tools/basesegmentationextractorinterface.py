"""Authors: Cody Baker and Ben Dichter."""
from .basedatainterface import BaseDataInterface
from .json_schema_utils import get_schema_from_method_signature


class BaseSegmentationExtractorInterface(BaseDataInterface):
    SegX = None

    @classmethod
    def get_source_schema(cls):
        return get_schema_from_method_signature(cls.SegX.__init__)

    def __init__(self, **source_data):
        super().__init__(**source_data)
        self.segmentation_extractor = self.SegX(**source_data)

    def run_conversion(self, nwbfile_path, metadata, stub_test=False):
        raise NotImplementedError
