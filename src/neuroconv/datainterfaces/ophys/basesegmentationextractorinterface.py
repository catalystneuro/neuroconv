"""Authors: Heberto Mayorquin, Cody Baker and Ben Dichter."""

from typing import Optional

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ophys import Fluorescence, ImageSegmentation, ImagingPlane, TwoPhotonSeries

from ...baseextractorinterface import BaseExtractorInterface
from ...utils import fill_defaults, get_base_schema, get_schema_from_hdmf_class


class BaseSegmentationExtractorInterface(BaseExtractorInterface):
    """Parent class for all SegmentationExtractorInterfaces."""

    keywords = ("segmentation", "roi", "cells")

    ExtractorModuleName = "roiextractors"

    def __init__(self, verbose: bool = False, **source_data):
        super().__init__(**source_data)
        self.verbose = verbose
        self.segmentation_extractor = self.get_extractor()(**source_data)

    def get_metadata_schema(self) -> dict:
        """
        Generate the metadata schema for Ophys data, updating required fields and properties.

        This method builds upon the base schema and customizes it for Ophys-specific metadata, including required
        components such as devices, fluorescence data, imaging planes, and two-photon series. It also applies
        temporary schema adjustments to handle certain use cases until a centralized metadata schema definition
        is available.

        Returns
        -------
        dict
            A dictionary representing the updated Ophys metadata schema.

        Notes
        -----
        - Ensures that `Device` and `ImageSegmentation` are marked as required.
        - Updates various properties, including ensuring arrays for `ImagingPlane` and `TwoPhotonSeries`.
        - Adjusts the schema for `Fluorescence`, including required fields and pattern properties.
        - Adds schema definitions for `DfOverF`, segmentation images, and summary images.
        - Applies temporary fixes, such as setting additional properties for `ImageSegmentation` to True.
        """
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

        metadata_schema["properties"]["Ophys"]["properties"]["Fluorescence"].update(required=["name"])
        metadata_schema["properties"]["Ophys"]["properties"]["Fluorescence"].pop("additionalProperties")

        roi_response_series_schema = metadata_schema["properties"]["Ophys"]["properties"]["Fluorescence"][
            "properties"
        ].pop("roi_response_series")

        roi_response_series_schema.pop("maxItems")
        roi_response_series_schema["items"].update(required=list())

        roi_response_series_per_plane_schema = dict(
            type="object", patternProperties={"^[a-zA-Z0-9]+$": roi_response_series_schema["items"]}
        )

        metadata_schema["properties"]["Ophys"]["properties"]["Fluorescence"].update(
            patternProperties={"^(?!name$)[a-zA-Z0-9]+$": roi_response_series_per_plane_schema}
        )

        metadata_schema["properties"]["Ophys"]["properties"]["ImageSegmentation"]["additionalProperties"] = True

        metadata_schema["properties"]["Ophys"]["properties"]["DfOverF"] = metadata_schema["properties"]["Ophys"][
            "properties"
        ]["Fluorescence"]

        # NOTE: Would prefer to remove in favor of simply using the up-to-date metadata_schema.json
        images_inner_schema = dict(
            type="object",
            properties=dict(name=dict(type="string"), description=dict(type="string")),
        )

        summary_images_per_plane_schema = dict(type="object", patternProperties={"^[a-zA-Z0-9]+$": images_inner_schema})

        metadata_schema["properties"]["Ophys"]["properties"]["SegmentationImages"] = dict(
            type="object",
            required=["name"],
            properties=dict(
                name=dict(type="string", default="SegmentationImages"),
                description=dict(type="string"),
            ),
            patternProperties={
                "^(?!(name|description)$)[a-zA-Z0-9]+$": summary_images_per_plane_schema,
            },
        )

        fill_defaults(metadata_schema, self.get_metadata())
        return metadata_schema

    def get_metadata(self) -> dict:
        from ...tools.roiextractors import get_nwb_segmentation_metadata

        metadata = super().get_metadata()
        metadata.update(get_nwb_segmentation_metadata(self.segmentation_extractor))
        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        reinitialized_extractor = self.get_extractor()(**self.source_data)
        return reinitialized_extractor.frame_to_time(frames=np.arange(stop=reinitialized_extractor.get_num_frames()))

    def get_timestamps(self) -> np.ndarray:
        return self.segmentation_extractor.frame_to_time(
            frames=np.arange(stop=self.segmentation_extractor.get_num_frames())
        )

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        self.segmentation_extractor.set_times(times=aligned_timestamps)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        stub_frames: int = 100,
        include_background_segmentation: bool = False,
        include_roi_centroids: bool = True,
        include_roi_acceptance: bool = True,
        mask_type: Optional[str] = "image",  # Literal["image", "pixel", "voxel"]
        plane_segmentation_name: Optional[str] = None,
        iterator_options: Optional[dict] = None,
    ):
        """

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile to add the plane segmentation to.
        metadata : dict, optional
            The metadata for the interface
        stub_test : bool, default: False
        stub_frames : int, default: 100
        include_background_segmentation : bool, default: False
            Whether to include the background plane segmentation and fluorescence traces in the NWB file. If False,
            neuropil traces are included in the main plane segmentation rather than the background plane segmentation.
        include_roi_centroids : bool, default: True
            Whether to include the ROI centroids on the PlaneSegmentation table.
            If there are a very large number of ROIs (such as in whole-brain recordings),
            you may wish to disable this for faster write speeds.
        include_roi_acceptance : bool, default: True
            Whether to include if the detected ROI was 'accepted' or 'rejected'.
            If there are a very large number of ROIs (such as in whole-brain recordings), you may wish to ddisable this for
            faster write speeds.
        mask_type : str, default: 'image'
            There are three types of ROI masks in NWB, 'image', 'pixel', and 'voxel'.

            * 'image' masks have the same shape as the reference images the segmentation was applied to, and weight each pixel
              by its contribution to the ROI (typically boolean, with 0 meaning 'not in the ROI').
            * 'pixel' masks are instead indexed by ROI, with the data at each index being the shape of the image by the number
              of pixels in each ROI.
            * 'voxel' masks are instead indexed by ROI, with the data at each index being the shape of the volume by the number
              of voxels in each ROI.

            Specify your choice between these two as mask_type='image', 'pixel', 'voxel', or None.
            If None, the mask information is not written to the NWB file.
        plane_segmentation_name : str, optional
            The name of the plane segmentation to be added.
        iterator_options : dict, optional
            The options to use when iterating over the image masks of the segmentation extractor.

        Returns
        -------

        """
        from ...tools.roiextractors import add_segmentation_to_nwbfile

        if stub_test:
            stub_frames = min([stub_frames, self.segmentation_extractor.get_num_frames()])
            segmentation_extractor = self.segmentation_extractor.frame_slice(start_frame=0, end_frame=stub_frames)
        else:
            segmentation_extractor = self.segmentation_extractor

        metadata = metadata or self.get_metadata()

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            include_background_segmentation=include_background_segmentation,
            include_roi_centroids=include_roi_centroids,
            include_roi_acceptance=include_roi_acceptance,
            mask_type=mask_type,
            plane_segmentation_name=plane_segmentation_name,
            iterator_options=iterator_options,
        )
