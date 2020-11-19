"""Authors: Cody Baker and Ben Dichter."""
import roiextractors as re

from .basedatainterface import BaseDataInterface
from .utils import get_schema_from_method_signature


class BaseSegmentationExtractorInterface(BaseDataInterface):
    SegX = None

    @classmethod
    def get_input_schema(cls):
        return get_schema_from_method_signature(cls.SegX.__init__)

    def __init__(self, **input_args):
        super().__init__(**input_args)
        self.segmentation_extractor = self.SegX(**input_args)

    def convert_data(self, nwbfile, metadata_dict):
        re.NwbSegmentationExtractor.write_segmentation(
            self.segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata_dict
        )
