import warnings
from typing import Literal

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ophys import Fluorescence, ImageSegmentation, ImagingPlane, PlaneSegmentation

from ...baseextractorinterface import BaseExtractorInterface
from ...utils import (
    DeepDict,
    dict_deep_update,
    fill_defaults,
    get_base_schema,
    get_schema_from_hdmf_class,
)


class BaseSegmentationExtractorInterface(BaseExtractorInterface):
    """Parent class for all SegmentationExtractorInterfaces."""

    keywords = ("segmentation", "roi", "cells")

    def _initialize_extractor(self, interface_kwargs: dict):
        """
        Initialize and return the extractor instance for segmentation interfaces.

        Extends the base implementation to also remove interface-specific parameters
        which are not needed by the extractor.

        Parameters
        ----------
        interface_kwargs : dict
            The source data parameters passed to the interface constructor.

        Returns
        -------
        extractor_instance
            An initialized segmentation extractor instance.
        """
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("metadata_key", None)

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    def __init__(
        self,
        *,  # Force keyword-only arguments
        verbose: bool = False,
        metadata_key: str = "default",
        **source_data,
    ):
        """
        Initialize the segmentation interface.

        Parameters
        ----------
        verbose : bool, default: False
            Whether to print verbose output.
        metadata_key : str, default: "default"
            The key to use for this segmentation data in the metadata dictionaries.
            This key is used to identify this interface's metadata in:
            - metadata["Devices"]
            - metadata["Ophys"]["ImagingPlanes"]
            - metadata["Ophys"]["PlaneSegmentations"]
            - metadata["Ophys"]["RoiResponses"]
        **source_data
            Source data parameters passed to the extractor.
        """
        super().__init__(**source_data)
        self.verbose = verbose
        self.metadata_key = metadata_key
        self.segmentation_extractor = self._extractor_instance

    def get_metadata_schema(self) -> dict:
        """
        Generate the metadata schema for Ophys segmentation data using the new dictionary-based structure.

        Returns
        -------
        dict
            A dictionary representing the updated Ophys metadata schema with dictionary-based
            structures for Devices, ImagingPlanes, PlaneSegmentations, and RoiResponses.
        """
        metadata_schema = super().get_metadata_schema()
        metadata_schema["required"] = ["Ophys"]

        # Top-level Devices schema
        device_schema = get_schema_from_hdmf_class(Device)
        metadata_schema["properties"]["Devices"] = {
            "type": "object",
            "patternProperties": {"^[a-zA-Z0-9_]+$": device_schema},
        }

        # Ophys schema
        metadata_schema["properties"]["Ophys"] = get_base_schema(tag="Ophys")
        metadata_schema["properties"]["Ophys"]["required"] = ["ImagingPlanes", "PlaneSegmentations"]

        # ImagingPlanes schema (dictionary-based)
        imaging_plane_schema = get_schema_from_hdmf_class(ImagingPlane)
        imaging_plane_schema["properties"]["optical_channel"].pop("maxItems", None)
        imaging_plane_schema["properties"]["device_metadata_key"] = {"type": "string"}
        imaging_plane_schema["additionalProperties"] = True  # Allow partial metadata
        imaging_plane_schema["required"] = []  # No required fields - defaults applied at conversion
        # Also make optical_channel items permissive
        if "items" in imaging_plane_schema["properties"]["optical_channel"]:
            imaging_plane_schema["properties"]["optical_channel"]["items"]["required"] = []
            imaging_plane_schema["properties"]["optical_channel"]["items"]["additionalProperties"] = True

        # PlaneSegmentations schema (dictionary-based)
        plane_segmentation_schema = get_schema_from_hdmf_class(PlaneSegmentation)
        plane_segmentation_schema["properties"]["imaging_plane_metadata_key"] = {"type": "string"}
        plane_segmentation_schema["additionalProperties"] = True  # Allow partial metadata
        plane_segmentation_schema["required"] = []  # No required fields - defaults applied at conversion

        # RoiResponses schema (dictionary-based)
        roi_response_trace_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "unit": {"type": "string"},
            },
        }
        roi_responses_per_plane_schema = {
            "type": "object",
            "patternProperties": {"^[a-zA-Z0-9_]+$": roi_response_trace_schema},
        }

        # SegmentationImages schema
        images_inner_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
            },
        }
        segmentation_images_per_plane_schema = {
            "type": "object",
            "patternProperties": {"^[a-zA-Z0-9_]+$": images_inner_schema},
        }

        metadata_schema["properties"]["Ophys"]["properties"] = {
            "ImagingPlanes": {
                "type": "object",
                "patternProperties": {"^[a-zA-Z0-9_]+$": imaging_plane_schema},
            },
            "PlaneSegmentations": {
                "type": "object",
                "patternProperties": {"^[a-zA-Z0-9_]+$": plane_segmentation_schema},
            },
            "RoiResponses": {
                "type": "object",
                "patternProperties": {"^[a-zA-Z0-9_]+$": roi_responses_per_plane_schema},
            },
            "SegmentationImages": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "default": "SegmentationImages"},
                    "description": {"type": "string"},
                },
                "patternProperties": {
                    "^(?!(name|description)$)[a-zA-Z0-9_]+$": segmentation_images_per_plane_schema,
                },
            },
        }

        # Definitions for reference
        metadata_schema["properties"]["Ophys"]["definitions"] = {
            "Device": device_schema,
            "ImagingPlane": imaging_plane_schema,
            "PlaneSegmentation": plane_segmentation_schema,
            "Fluorescence": get_schema_from_hdmf_class(Fluorescence),
            "ImageSegmentation": get_schema_from_hdmf_class(ImageSegmentation),
        }

        fill_defaults(metadata_schema, self.get_metadata())
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        """
        Retrieve the metadata for the segmentation data.

        Returns
        -------
        DeepDict
            Dictionary containing metadata including device information, imaging plane details,
            plane segmentation configuration, and ROI response metadata using the new
            dictionary-based structure.
        """
        from ...tools.roiextractors import get_nwb_segmentation_metadata

        metadata = super().get_metadata()
        default_metadata = get_nwb_segmentation_metadata(
            self.segmentation_extractor,
            metadata_key=self.metadata_key,
        )
        metadata = dict_deep_update(default_metadata, metadata)

        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        reinitialized_extractor = self._initialize_extractor(self.source_data)
        return reinitialized_extractor.get_timestamps()

    def get_timestamps(self) -> np.ndarray:
        return self.segmentation_extractor.get_timestamps()

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        self.segmentation_extractor.set_times(times=aligned_timestamps)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        stub_test: bool = False,
        stub_frames: int | None = None,
        include_background_segmentation: bool = False,
        include_roi_centroids: bool = True,
        include_roi_acceptance: bool = True,
        mask_type: Literal["image", "pixel", "voxel"] = "image",
        iterator_options: dict | None = None,
        stub_samples: int = 100,
    ):
        """
        Add segmentation data to the NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile to add the plane segmentation to.
        metadata : dict, optional
            The metadata for the interface
        stub_test : bool, default: False
        stub_frames : int, optional
            .. deprecated:: February 2026
                Use `stub_samples` instead.
        include_background_segmentation : bool, default: False
            Whether to include the background plane segmentation and fluorescence traces in the NWB file. If False,
            neuropil traces are included in the main plane segmentation rather than the background plane segmentation.
        include_roi_centroids : bool, default: True
            Whether to include the ROI centroids on the PlaneSegmentation table.
            If there are a very large number of ROIs (such as in whole-brain recordings),
            you may wish to disable this for faster write speeds.
        include_roi_acceptance : bool, default: True
            Whether to include if the detected ROI was 'accepted' or 'rejected'.
            If there are a very large number of ROIs (such as in whole-brain recordings), you may wish to disable this for
            faster write speeds.
        mask_type : str, default: 'image'
            There are three types of ROI masks in NWB, 'image', 'pixel', and 'voxel'.

            * 'image' masks have the same shape as the reference images the segmentation was applied to, and weight each pixel
              by its contribution to the ROI (typically boolean, with 0 meaning 'not in the ROI').
            * 'pixel' masks are instead indexed by ROI, with the data at each index being the shape of the image by the number
              of pixels in each ROI.
            * 'voxel' masks are instead indexed by ROI, with the data at each index being the shape of the volume by the number
              of voxels in each ROI.

            Specify your choice between these two as mask_type='image', 'pixel', 'voxel'
        iterator_options : dict, optional
            Options for controlling the iterative write process (buffer size, progress bars) when
            writing image masks and traces.

            Note: To configure chunk size and compression, use the backend configuration system
            via ``get_default_backend_configuration()`` and ``configure_backend()`` after calling
            this method. See the backend configuration documentation for details.
        stub_samples : int, default: 100
            The number of samples (frames) to use for testing. When provided, takes precedence over `stub_frames`.

        Returns
        -------

        """
        from ...tools.roiextractors import add_segmentation_to_nwbfile

        # Handle deprecation of stub_frames in favor of stub_samples
        if stub_frames is not None and stub_samples != 100:
            raise ValueError("Cannot specify both 'stub_frames' and 'stub_samples'. Use 'stub_samples' only.")

        if stub_frames is not None:
            warnings.warn(
                "The 'stub_frames' parameter is deprecated and will be removed on or after February 2026. "
                "Use 'stub_samples' instead.",
                FutureWarning,
                stacklevel=2,
            )
            effective_stub_samples = stub_frames
        else:
            effective_stub_samples = stub_samples

        if stub_test:
            effective_stub_samples = min([effective_stub_samples, self.segmentation_extractor.get_num_samples()])
            segmentation_extractor = self.segmentation_extractor.slice_samples(
                start_sample=0, end_sample=effective_stub_samples
            )
        else:
            segmentation_extractor = self.segmentation_extractor

        metadata = metadata or self.get_metadata()

        # Use the interface's metadata_key directly
        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            include_background_segmentation=include_background_segmentation,
            include_roi_centroids=include_roi_centroids,
            include_roi_acceptance=include_roi_acceptance,
            mask_type=mask_type,
            plane_segmentation_metadata_key=self.metadata_key,
            iterator_options=iterator_options,
        )
