import warnings
from typing import Literal

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ophys import Fluorescence, ImageSegmentation, ImagingPlane, TwoPhotonSeries

from ...baseextractorinterface import BaseExtractorInterface
from ...utils import (
    DeepDict,
    fill_defaults,
    get_base_schema,
    get_schema_from_hdmf_class,
)


class BaseSegmentationExtractorInterface(BaseExtractorInterface):
    """Parent class for all SegmentationExtractorInterfaces."""

    keywords = ("segmentation", "roi", "cells")

    def __init__(self, verbose: bool = False, **source_data):
        super().__init__(**source_data)
        self.verbose = verbose
        self.segmentation_extractor = self._extractor_instance

    @property
    def roi_ids(self):
        """Get all ROI IDs of the segmentation data."""
        return self.segmentation_extractor.get_roi_ids()

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

    def get_metadata(self) -> DeepDict:
        from ...tools.roiextractors.roiextractors import _get_default_ophys_metadata

        metadata = super().get_metadata()

        # Get the default ophys metadata (single source of truth)
        ophys_defaults = _get_default_ophys_metadata()

        # Only include the fields relevant to segmentation (not imaging series)
        metadata["Ophys"] = {
            "Device": ophys_defaults["Ophys"]["Device"],
            "ImagingPlane": ophys_defaults["Ophys"]["ImagingPlane"],
            "Fluorescence": ophys_defaults["Ophys"]["Fluorescence"],
            "DfOverF": ophys_defaults["Ophys"]["DfOverF"],
            "ImageSegmentation": ophys_defaults["Ophys"]["ImageSegmentation"],
            "SegmentationImages": ophys_defaults["Ophys"]["SegmentationImages"],
        }

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
        *args,
        stub_test: bool = False,
        stub_frames: int | None = None,
        include_background_segmentation: bool = False,
        include_roi_centroids: bool = True,
        include_roi_acceptance: bool = True,
        mask_type: Literal["image", "pixel", "voxel"] = "image",
        plane_segmentation_name: str | None = None,
        iterator_options: dict | None = None,
        stub_samples: int = 100,
        roi_ids_to_add: list[str | int] | None = None,
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
        plane_segmentation_name : str, optional
            The name of the plane segmentation to be added.
        iterator_options : dict, optional
            Options for controlling the iterative write process (buffer size, progress bars) when
            writing image masks and traces.

            Note: To configure chunk size and compression, use the backend configuration system
            via ``get_default_backend_configuration()`` and ``configure_backend()`` after calling
            this method. See the backend configuration documentation for details.
        stub_samples : int, default: 100
            The number of samples (frames) to use for testing. When provided, takes precedence over `stub_frames`.
        roi_ids_to_add : list of str or int, optional
            The ROI IDs to include in the NWB file. If ``None`` (default), all ROIs are included.
            Use this to filter out rejected or unwanted ROIs and reduce file size.
            Neuropil traces (e.g., from Suite2p) share the same IDs as their corresponding cells
            and are automatically included when those cell IDs are selected.
            The IDs must be a subset of the IDs returned by ``self.roi_ids``.

        Returns
        -------

        """
        from ...tools.roiextractors import add_segmentation_to_nwbfile

        # TODO: Remove this block in August 2026 or after when positional arguments are no longer supported.
        if args:
            parameter_names = [
                "stub_test",
                "stub_frames",
                "include_background_segmentation",
                "include_roi_centroids",
                "include_roi_acceptance",
                "mask_type",
                "plane_segmentation_name",
                "iterator_options",
                "stub_samples",
                "roi_ids_to_add",
            ]
            num_positional_args_before_args = 2  # nwbfile, metadata
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"add_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                    f"{len(args) + num_positional_args_before_args} were given. "
                    "Note: Positional arguments are deprecated and will be removed in August 2026 or after. Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to add_to_nwbfile is deprecated "
                f"and will be removed in August 2026 or after. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            stub_test = positional_values.get("stub_test", stub_test)
            stub_frames = positional_values.get("stub_frames", stub_frames)
            include_background_segmentation = positional_values.get(
                "include_background_segmentation", include_background_segmentation
            )
            include_roi_centroids = positional_values.get("include_roi_centroids", include_roi_centroids)
            include_roi_acceptance = positional_values.get("include_roi_acceptance", include_roi_acceptance)
            mask_type = positional_values.get("mask_type", mask_type)
            plane_segmentation_name = positional_values.get("plane_segmentation_name", plane_segmentation_name)
            iterator_options = positional_values.get("iterator_options", iterator_options)
            stub_samples = positional_values.get("stub_samples", stub_samples)
            roi_ids_to_add = positional_values.get("roi_ids_to_add", roi_ids_to_add)

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

        segmentation_extractor = self.segmentation_extractor

        if roi_ids_to_add is not None:
            segmentation_extractor = segmentation_extractor.select_rois(roi_ids=roi_ids_to_add)

        if stub_test:
            effective_stub_samples = min([effective_stub_samples, segmentation_extractor.get_num_samples()])
            segmentation_extractor = segmentation_extractor.slice_samples(
                start_sample=0, end_sample=effective_stub_samples
            )

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
