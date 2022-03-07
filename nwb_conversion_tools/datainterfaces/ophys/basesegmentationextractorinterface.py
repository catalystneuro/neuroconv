"""Authors: Cody Baker and Ben Dichter."""
from abc import ABC

from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ophys import Fluorescence, ImageSegmentation, ImagingPlane, TwoPhotonSeries

from ...basedatainterface import BaseDataInterface
from ...tools.roiextractors import write_segmentation, get_nwb_segmentation_metadata
from ...utils import (
    get_schema_from_hdmf_class,
    fill_defaults,
    get_base_schema,
)


class BaseSegmentationExtractorInterface(BaseDataInterface, ABC):
    SegX = None

    def __init__(self, **source_data):
        super().__init__(**source_data)
        self.segmentation_extractor = self.SegX(**source_data)

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["required"] = ["Ophys"]
        metadata_schema["properties"]["Ophys"] = get_base_schema()
        metadata_schema["properties"]["Ophys"]["properties"] = dict(
            Device=dict(type="array", minItems=1, items=get_schema_from_hdmf_class(Device)),
        )
        metadata_schema["properties"]["Ophys"]["properties"].update(
            Fluorescence=get_schema_from_hdmf_class(Fluorescence),
            ImageSegmentation=get_schema_from_hdmf_class(ImageSegmentation),
            ImagingPlane=get_schema_from_hdmf_class(ImagingPlane),
            TwoPhotonSeries=get_schema_from_hdmf_class(TwoPhotonSeries),
        )
        metadata_schema["properties"]["Ophys"]["required"] = ["Device", "Fluorescence", "ImageSegmentation"]

        # Temporary fixes until centralized definition of metadata schemas
        metadata_schema["properties"]["Ophys"]["properties"]["ImagingPlane"].update(type="array")
        metadata_schema["properties"]["Ophys"]["properties"]["Fluorescence"]["properties"]["roi_response_series"][
            "items"
        ]["required"] = list()
        metadata_schema["properties"]["Ophys"]["properties"]["ImageSegmentation"]["additionalProperties"] = True
        metadata_schema["properties"]["Ophys"]["properties"]["Fluorescence"]["properties"]["roi_response_series"].pop(
            "maxItems"
        )
        fill_defaults(metadata_schema, self.get_metadata())
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata.update(get_nwb_segmentation_metadata(self.segmentation_extractor))
        _ = metadata.pop("NWBFile")
        return metadata

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, overwrite: bool = False):
        write_segmentation(self.segmentation_extractor, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite)
