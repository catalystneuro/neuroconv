"""Authors: Cody Baker and Ben Dichter."""
from copy import deepcopy
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup, ElectricalSeries
import numpy as np
import segmentationextractors as segx

from .utils import get_base_schema, get_schema_from_method_signature, \
                   get_schema_from_hdmf_class
from .basedatainterface import BaseDataInterface


class BaseSegmentationExtractorInterface(BaseDataInterface):
    SegX = None

    @classmethod
    def get_input_schema(cls):
        return get_schema_from_method_signature(cls.SegX)

    def __init__(self, **input_args):
        super().__init__(**input_args)
        self.segmentation_extractor = self.SegX(**input_args)

    def get_metadata_schema(self):
        # metadata_schema = deepcopy(get_base_schema())
        #
        # # ideally most of this be automatically determined from pynwb docvals
        # metadata_schema['properties']['Device'] = get_schema_from_hdmf_class(Device)
        # metadata_schema['properties']['ElectrodeGroup'] = get_schema_from_hdmf_class(ElectrodeGroup)
        # metadata_schema['properties']['ElectricalSeries'] = get_schema_from_hdmf_class(ElectricalSeries)
        # required_fields = ['Device','ElectrodeGroup','ElectricalSeries']
        # for field in required_fields:
        #     metadata_schema['required'].append(field)
        #
        # return metadata_schema # SegmentationExtractor metadata json-schema here.
        raise NotImplementedError

    def convert_data(self, nwbfile_path, metadata_dict, stub_test=False):
        # if stub_test:
        #     # example recording extractor for fast testing
        #     num_channels = 4
        #     num_frames = 10000
        #     test_recording_extractor = segx.NumpySegmentationExtractor(
        #         timeseries=(np.random.normal(0, 1, (num_channels, num_frames)) * 100).astype(int),
        #         sampling_frequency=20000,
        #         geom=np.random.normal(0, 1, (num_channels, 2)))
        #     segx.NwbSegmentationExtractor.write_recording(test_recording_extractor, nwbfile_path, metadata_dict)
        # else:
        #     segx.NwbSegmentationExtractor.write_recording(self.recording_extractor, nwbfile_path, metadata_dict)
        raise NotImplementedError
