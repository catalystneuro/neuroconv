"""Author: Ben Dichter."""
import roiextractors as re
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ophys import Fluorescence, ImageSegmentation, ImagingPlane, TwoPhotonSeries
from .utils import get_schema_from_hdmf_class
from .basedatainterface import BaseDataInterface
from .json_schema_utils import get_schema_from_method_signature, fill_defaults, get_base_schema


class BaseImagingExtractorInterface(BaseDataInterface):
    IX = None

    @classmethod
    def get_source_schema(cls):
        return get_schema_from_method_signature(cls.IX.__init__)

    def __init__(self, **input_args):
        super().__init__(**input_args)
        self.imaging_extractor = self.IX(**input_args)

    def get_metadata_schema(self):
        """Compile metadata schema for the ImageExtractor."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema['required'] = ['Ophys']
        # Initiate Ophys metadata
        metadata_schema['properties']['Ophys'] = get_base_schema()
        metadata_schema['properties']['Ophys']['properties'] = dict(
            Device=get_schema_from_hdmf_class(Device),
            ImagingPlane=get_schema_from_hdmf_class(ImagingPlane),
            TwoPhotonSeries=get_schema_from_hdmf_class(TwoPhotonSeries)
        )
        metadata_schema['properties']['Ophys']['required'] = \
            ['Device', 'ImagingPlane', 'TwoPhotonSeries']
        fill_defaults(metadata_schema, self.get_metadata())
        return metadata_schema

    def get_metadata(self):
        """Auto-fill metadata with values found from the corresponding imageextractor.
        Must comply with metadata schema."""
        metadata = super().get_metadata()
        metadata.update(re.NwbImagingExtractor.get_nwb_metadata(self.imaging_extractor))
        _ = metadata.pop('NWBFile')
        return metadata

    def run_conversion(self, nwbfile: NWBFile, metadata_dict: dict, overwrite: bool = False):
        re.NwbImagingExtractor.write_imaging(
            self.imaging_extractor,
            nwbfile=nwbfile,
            metadata=metadata_dict,
            overwrite=overwrite
        )
