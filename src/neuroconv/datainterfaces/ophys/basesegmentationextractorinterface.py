"""Authors: Heberto Mayorquin, Cody Baker and Ben Dichter."""
from typing import Optional

from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ophys import Fluorescence, ImageSegmentation, ImagingPlane, TwoPhotonSeries

from ...baseextractorinterface import BaseExtractorInterface
from ...utils import get_schema_from_hdmf_class, fill_defaults, OptionalFilePathType, get_base_schema


class BaseSegmentationExtractorInterface(BaseExtractorInterface):
    """Parent class for all SegmentationExtractorInterfaces."""

    ExtractorModuleName: Optional[str] = "roiextractors"

    def __init__(self, **source_data):
        super().__init__(**source_data)
        self.segmentation_extractor = self.Extractor(**source_data)

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
        metadata_schema["properties"]["Ophys"]["required"] = ["Device", "ImageSegmentation"]

        # Temporary fixes until centralized definition of metadata schemas
        metadata_schema["properties"]["Ophys"]["properties"]["ImagingPlane"].update(type="array")
        metadata_schema["properties"]["Ophys"]["properties"]["TwoPhotonSeries"].update(type="array")

        metadata_schema["properties"]["Ophys"]["properties"]["Fluorescence"]["properties"]["roi_response_series"][
            "items"
        ]["required"] = list()
        metadata_schema["properties"]["Ophys"]["properties"]["ImageSegmentation"]["additionalProperties"] = True
        metadata_schema["properties"]["Ophys"]["properties"]["Fluorescence"]["properties"]["roi_response_series"].pop(
            "maxItems"
        )
        metadata_schema["properties"]["Ophys"]["properties"]["DfOverF"] = metadata_schema["properties"]["Ophys"][
            "properties"
        ]["Fluorescence"]

        fill_defaults(metadata_schema, self.get_metadata())
        return metadata_schema

    def get_metadata(self):
        from ...tools.roiextractors import get_nwb_segmentation_metadata

        metadata = super().get_metadata()
        metadata.update(get_nwb_segmentation_metadata(self.segmentation_extractor))
        return metadata

    def run_conversion(
        self,
        nwbfile_path: OptionalFilePathType = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        stub_test: bool = False,
        stub_frames: int = 100,
        include_roi_centroids: bool = True,
        mask_type: Optional[str] = "image",  # Optional[Literal["image", "pixel"]]
        iterator_options: Optional[dict] = None,
        compression_options: Optional[dict] = None,
    ):
        from ...tools.roiextractors import write_segmentation

        if stub_test:
            stub_frames = min([stub_frames, self.segmentation_extractor.get_num_frames()])
            segmentation_extractor = self.segmentation_extractor.frame_slice(start_frame=0, end_frame=stub_frames)
        else:
            segmentation_extractor = self.segmentation_extractor

        write_segmentation(
            segmentation_extractor=segmentation_extractor,
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
            include_roi_centroids=include_roi_centroids,
            mask_type=mask_type,
            iterator_options=iterator_options,
            compression_options=compression_options,
        )
