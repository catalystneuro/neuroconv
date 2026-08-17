import warnings
from typing import Literal

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ophys import Fluorescence, ImageSegmentation, ImagingPlane, TwoPhotonSeries

from ._metadata_schema import _get_ophys_registry_entry_definitions, _keyed_registry
from ._metadata_template import (
    _get_device_model_template_entry,
    _get_device_template_entry,
    _get_imaging_plane_template_entry,
    _resolve_device_metadata_key,
)
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

    def __init__(self, verbose: bool = False, metadata_key: str | None = None, **source_data):
        super().__init__(**source_data)
        self.verbose = verbose
        self.segmentation_extractor = self._extractor_instance
        self.metadata_key = metadata_key

    @property
    def roi_ids(self):
        """Get all ROI IDs of the segmentation data."""
        return self.segmentation_extractor.get_roi_ids()

    def get_metadata_schema(self) -> dict:
        """
        Compile the metadata schema.

        The registries are objects keyed by ``metadata_key``, and the entries stay permissive: an entry is
        passed to a pynwb constructor, so it may legitimately carry any field that constructor takes. What is
        pinned is the shape, that an entry is an object, and the cross-reference fields
        (``device_metadata_key``, ``imaging_plane_metadata_key``) that no hdmf class knows about. Traces and
        summary images are keyed twice, by plane segmentation and then by trace or image name.

        Metadata in the old list-based format is validated against
        ``_get_metadata_schema_for_old_list_format``, and both go when that format does.
        """
        from ...basedatainterface import BaseDataInterface

        metadata_schema = BaseDataInterface.get_metadata_schema(self)
        metadata_schema["properties"]["Ophys"] = get_base_schema(tag="Ophys")
        metadata_schema["properties"]["Ophys"]["required"] = []
        metadata_schema["properties"]["Ophys"]["properties"] = dict(
            ImagingPlanes=_keyed_registry("#/properties/Ophys/definitions/ImagingPlaneEntry"),
            PlaneSegmentations=_keyed_registry("#/properties/Ophys/definitions/PlaneSegmentationEntry"),
            RoiResponses=_keyed_registry("#/properties/Ophys/definitions/RoiResponsesEntry"),
            SegmentationImages=_keyed_registry("#/properties/Ophys/definitions/SegmentationImagesEntry"),
        )
        metadata_schema["properties"]["Ophys"]["definitions"] = _get_ophys_registry_entry_definitions()
        return metadata_schema

    def _get_metadata_schema_for_old_list_format(self) -> dict:
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

    def get_metadata(self, *, use_new_metadata_format: bool = False) -> DeepDict:
        if use_new_metadata_format:
            return super().get_metadata()

        from ...tools.roiextractors.roiextractors_pending_deprecation import (
            _get_default_ophys_metadata_old_metadata_list,
        )

        metadata = super().get_metadata()

        # Get the default ophys metadata (single source of truth)
        ophys_defaults = _get_default_ophys_metadata_old_metadata_list()

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

    def get_metadata_template(self) -> DeepDict:
        """Return the segmentation this interface writes, sized to its traces, with the blanks marked.

        The counterpart to :meth:`get_metadata`, which reports only what the source recorded and so
        leaves a user no indication of what else the file needs. This returns those same values wrapped
        in the structure the writer expects. Fill in the blanks and pass the result to ``add_to_nwbfile``
        or ``run_conversion``; a blank still ``None`` at write time is an error rather than a value.

        One plane segmentation, one response series per trace the pipeline produced and one summary image
        per image it produced, all under this interface's ``metadata_key``, on an imaging plane that hangs
        off one microscope. The segmentation, its traces and its images share the one key because the
        writer resolves all three through it, so rename them together or not at all.

        Only the traces and images this segmentation actually holds are offered, since naming one it does
        not hold writes nothing and warns. Those inner keys are roiextractors' own vocabulary (``raw``,
        ``dff``, ``neuropil``, ``deconvolved``, ``correlation``, ``mean``) and are the one set of keys here
        that cannot be renamed; the ``name`` inside each is what the object is called in the file.
        """
        # What ``add_segmentation_to_nwbfile`` falls back to for an interface constructed without a key.
        metadata_key = self.metadata_key or "default_metadata_key"
        # Prefilled through the same transitional shim the writers use, so an interface whose
        # ``get_metadata`` still answers in the old list format does not leak that shape into the
        # template. When the old format goes the shim goes with it, and this becomes
        # ``self.get_metadata()`` with nothing else to change.
        source_metadata = self._get_metadata_for_writing()
        device_metadata_key = _resolve_device_metadata_key(source_metadata=source_metadata, metadata_key=metadata_key)

        ophys = dict(
            ImagingPlanes={metadata_key: _get_imaging_plane_template_entry(device_metadata_key=device_metadata_key)},
            PlaneSegmentations={
                metadata_key: dict(name=None, description=None, imaging_plane_metadata_key=metadata_key)
            },
        )

        # Sized to the data, the same filter the writers apply: an entry for a trace or an image the
        # extractor does not hold is a blank nobody can fill, since the object is never written.
        traces_dict = self.segmentation_extractor.get_traces_dict()
        available_traces = [
            trace_name for trace_name, trace in traces_dict.items() if trace is not None and trace.size != 0
        ]
        if available_traces:
            ophys["RoiResponses"] = {
                metadata_key: {
                    trace_name: dict(name=None, description=None, unit=None) for trace_name in available_traces
                }
            }

        images_dict = self.segmentation_extractor.get_images_dict()
        available_images = [image_name for image_name, image in images_dict.items() if image is not None]
        if available_images:
            ophys["SegmentationImages"] = {
                metadata_key: {image_name: dict(name=None, description=None) for image_name in available_images}
            }

        device_model_metadata_key = f"{device_metadata_key}_model"
        template = DeepDict(
            dict(
                DeviceModels={device_model_metadata_key: _get_device_model_template_entry()},
                Devices={
                    device_metadata_key: _get_device_template_entry(device_model_metadata_key=device_model_metadata_key)
                },
                Ophys=ophys,
            )
        )

        # The blanks are a floor rather than an override: whatever the source recorded wins over the
        # template, so a field the interface was able to read is never handed back as one to fill in.
        template.deep_update(source_metadata)
        return template

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
        *args,  # TODO: change to * (keyword only) on or after August 2026
        stub_test: bool = False,
        include_background_segmentation: bool = False,
        include_roi_centroids: bool = True,
        include_roi_acceptance: bool | None = None,
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
        include_background_segmentation : bool, default: False
            Whether to include the background plane segmentation and fluorescence traces in the NWB file. If False,
            neuropil traces are included in the main plane segmentation rather than the background plane segmentation.
        include_roi_centroids : bool, default: True
            Whether to include the ROI centroids on the PlaneSegmentation table.
            If there are a very large number of ROIs (such as in whole-brain recordings),
            you may wish to disable this for faster write speeds.
        include_roi_acceptance : bool, optional
            Deprecated and ignored. ROI acceptance is now written automatically as a
            column on the PlaneSegmentation table whenever the segmentation extractor
            exposes acceptance/rejection through its property system.
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
            The number of samples (frames) to use for testing.
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

        if include_roi_acceptance is not None:
            warnings.warn(
                "`include_roi_acceptance` is deprecated and has no effect. ROI acceptance is now "
                "written automatically as a column on the PlaneSegmentation table whenever the "
                "segmentation extractor exposes acceptance/rejection through its property system. "
                "This parameter will be removed on or after November 2026.",
                DeprecationWarning,
                stacklevel=2,
            )

        segmentation_extractor = self.segmentation_extractor

        if roi_ids_to_add is not None:
            segmentation_extractor = segmentation_extractor.select_rois(roi_ids=roi_ids_to_add)

        if stub_test:
            stub_samples = min([stub_samples, segmentation_extractor.get_num_samples()])
            segmentation_extractor = segmentation_extractor.slice_samples(start_sample=0, end_sample=stub_samples)

        metadata = metadata or self._get_metadata_for_writing()

        add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            include_background_segmentation=include_background_segmentation,
            include_roi_centroids=include_roi_centroids,
            mask_type=mask_type,
            plane_segmentation_name=plane_segmentation_name,
            iterator_options=iterator_options,
            metadata_key=self.metadata_key,
        )
