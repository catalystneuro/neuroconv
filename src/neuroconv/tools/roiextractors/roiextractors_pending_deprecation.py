"""Deprecated roiextractors functions pending removal on or after March 2026.

These functions are kept for backward compatibility only. Use high-level
interface methods (e.g., BaseImagingExtractorInterface.add_to_nwbfile() or
BaseSegmentationExtractorInterface.add_to_nwbfile()) instead.
"""

import warnings
from typing import Literal

from pynwb import NWBFile
from pynwb.base import Images
from pynwb.image import GrayscaleImage
from pynwb.ophys import (
    ImageSegmentation,
    ImagingPlane,
    OnePhotonSeries,
    OpticalChannel,
    TwoPhotonSeries,
)
from roiextractors import (
    ImagingExtractor,
    SegmentationExtractor,
)

from .roiextractors import (
    _add_fluorescence_traces_to_nwbfile,
    _add_imaging_plane_to_nwbfile,
    _add_plane_segmentation,
    _get_default_ophys_metadata,
    _get_default_segmentation_metadata,
    _imaging_frames_to_hdmf_iterator,
    add_devices_to_nwbfile,
)
from ..nwb_helpers import get_module
from ...utils import calculate_regular_series_rate


def add_imaging_plane_to_nwbfile(
    nwbfile: NWBFile,
    metadata: dict,
    imaging_plane_name: str | None = None,
) -> NWBFile:
    """
    .. deprecated:: 0.8.2
        This function is deprecated and will be removed on or after March 2026.
        It is kept as-is for backward compatibility. Use high-level interface methods instead.
    """
    warnings.warn(
        "The 'add_imaging_plane_to_nwbfile' function is deprecated and will be removed on or after March 2026. "
        "This is a low-level function that should not be called directly. "
        "Use high-level interface methods like BaseImagingExtractorInterface.add_to_nwbfile() instead.",
        FutureWarning,
        stacklevel=2,
    )

    # Duplicated implementation - kept verbatim for backward compatibility
    default_metadata = _get_default_ophys_metadata()
    default_imaging_plane = default_metadata["Ophys"]["ImagingPlane"][0]

    # Track whether user explicitly provided a name
    user_provided_a_name = imaging_plane_name is not None

    imaging_plane_name = imaging_plane_name or default_imaging_plane["name"]

    if imaging_plane_name in nwbfile.imaging_planes:
        return nwbfile

    add_devices_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    if user_provided_a_name:
        # User explicitly requested a specific plane - search for it in metadata
        imaging_planes_list = metadata.get("Ophys", {}).get("ImagingPlane", [])
        metadata_found = next(
            (plane for plane in imaging_planes_list if plane["name"] == imaging_plane_name),
            None,
        )

        if metadata_found is None:
            raise ValueError(
                f"Metadata for Imaging Plane '{imaging_plane_name}' not found in metadata['Ophys']['ImagingPlane']."
            )

        # Copy user metadata to avoid mutation
        imaging_plane_kwargs = metadata_found.copy()

        # Fill in any missing required fields with defaults
        required_fields = ["name", "excitation_lambda", "indicator", "location", "device", "optical_channel"]
        for field in required_fields:
            if field not in imaging_plane_kwargs:
                imaging_plane_kwargs[field] = default_imaging_plane[field]
    else:
        # User didn't provide a name, use local copy of defaults as kwargs
        imaging_plane_kwargs = default_imaging_plane

    # Replace device name string with actual device object from nwbfile
    device_name = imaging_plane_kwargs["device"]
    imaging_plane_kwargs["device"] = nwbfile.devices[device_name]

    # Convert optical channel metadata dicts to OpticalChannel objects
    imaging_plane_kwargs["optical_channel"] = [
        OpticalChannel(**channel_metadata) for channel_metadata in imaging_plane_kwargs["optical_channel"]
    ]

    imaging_plane = ImagingPlane(**imaging_plane_kwargs)
    nwbfile.add_imaging_plane(imaging_plane)

    return nwbfile


def add_image_segmentation_to_nwbfile(nwbfile: NWBFile, metadata: dict) -> NWBFile:
    """
    .. deprecated:: 0.8.2
        This function is deprecated and will be removed on or after March 2026.
        It is kept as-is for backward compatibility. Use high-level interface methods instead.
    """
    warnings.warn(
        "The 'add_image_segmentation_to_nwbfile' function is deprecated and will be removed on or after March 2026. "
        "This is a low-level function that should not be called directly. "
        "Use high-level interface methods like BaseSegmentationExtractorInterface.add_to_nwbfile() instead.",
        FutureWarning,
        stacklevel=2,
    )

    # Duplicated implementation - kept verbatim for backward compatibility
    # Get ImageSegmentation name from metadata or use default
    default_metadata = _get_default_segmentation_metadata()
    default_name = default_metadata["Ophys"]["ImageSegmentation"]["name"]

    image_segmentation_name = metadata.get("Ophys", {}).get("ImageSegmentation", {}).get("name", default_name)

    ophys = get_module(nwbfile, "ophys", description="contains optical physiology processed data")

    # Add ImageSegmentation container if it doesn't already exist
    if image_segmentation_name not in ophys.data_interfaces:
        ophys.add(ImageSegmentation(name=image_segmentation_name))

    return nwbfile


def add_photon_series_to_nwbfile(
    imaging: ImagingExtractor,
    nwbfile: NWBFile,
    metadata: dict | None = None,
    photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "TwoPhotonSeries",
    photon_series_index: int = 0,
    parent_container: Literal["acquisition", "processing/ophys"] = "acquisition",
    iterator_type: str | None = "v2",
    iterator_options: dict | None = None,
    always_write_timestamps: bool = False,
) -> NWBFile:
    """
    .. deprecated:: 0.8.2
        This function is deprecated and will be removed on or after March 2026.
        It is kept as-is for backward compatibility. Use high-level interface methods instead.
    """
    warnings.warn(
        "The 'add_photon_series_to_nwbfile' function is deprecated and will be removed on or after March 2026. "
        "This is a low-level function that should not be called directly. "
        "Use high-level interface methods like BaseImagingExtractorInterface.add_to_nwbfile() instead.",
        FutureWarning,
        stacklevel=2,
    )

    # Duplicated implementation - kept verbatim for backward compatibility
    iterator_options = iterator_options or dict()
    metadata = metadata or {}

    assert photon_series_type in [
        "OnePhotonSeries",
        "TwoPhotonSeries",
    ], "'photon_series_type' must be either 'OnePhotonSeries' or 'TwoPhotonSeries'."

    assert parent_container in [
        "acquisition",
        "processing/ophys",
    ], "'parent_container' must be either 'acquisition' or 'processing/ophys'."

    # Get defaults from single source of truth
    default_metadata = _get_default_ophys_metadata()
    default_photon_series = default_metadata["Ophys"][photon_series_type][0]

    # Extract photon series metadata from user or use defaults
    user_photon_series_list = metadata.get("Ophys", {}).get(photon_series_type, [])
    if user_photon_series_list:
        if photon_series_index >= len(user_photon_series_list):
            raise IndexError(
                f"photon_series_index ({photon_series_index}) out of range. Must be less than {len(user_photon_series_list)}."
            )
        user_photon_series_metadata = user_photon_series_list[photon_series_index]

        # Determine if imaging_plane was user-provided, if the value is None this will be used
        # to signal that a default imaging plane should be created
        imaging_plane_name = user_photon_series_metadata.get("imaging_plane")

        # Build photon series metadata from user input
        photon_series_kwargs = user_photon_series_metadata.copy()
        # Fill missing required fields with defaults
        for field in ["name", "description", "unit", "imaging_plane"]:
            if field not in photon_series_kwargs:
                photon_series_kwargs[field] = default_photon_series[field]
    else:
        # User didn't provide photon series - use all defaults
        photon_series_kwargs = default_photon_series
        imaging_plane_name = None  # Will create default imaging plane

    # Add imaging plane (None signals to create default imaging plane)
    _add_imaging_plane_to_nwbfile(
        nwbfile=nwbfile,
        metadata=metadata,
        imaging_plane_name=imaging_plane_name,
    )

    imaging_plane_name = photon_series_kwargs["imaging_plane"]
    imaging_plane = nwbfile.get_imaging_plane(name=imaging_plane_name)
    photon_series_kwargs["imaging_plane"] = imaging_plane

    # Add dimension: respect user-provided metadata, else derive from extractor
    if "dimension" not in user_photon_series_metadata:
        photon_series_kwargs["dimension"] = imaging.get_sample_shape()

    # This adds the data in way that is memory efficient
    imaging_extractor_iterator = _imaging_frames_to_hdmf_iterator(
        imaging=imaging,
        iterator_type=iterator_type,
        iterator_options=iterator_options,
    )
    photon_series_kwargs["data"] = imaging_extractor_iterator

    # Add timestamps or rate
    if always_write_timestamps:
        timestamps = imaging.get_timestamps()
        photon_series_kwargs.update(timestamps=timestamps)
    else:
        # Resolve timestamps: user-set > native hardware > none
        timestamps_were_set = imaging.has_time_vector()
        if timestamps_were_set:
            timestamps = imaging.get_timestamps()
        else:
            timestamps = imaging.get_native_timestamps()

        timestamps_are_available = timestamps is not None

        if timestamps_are_available:
            rate = calculate_regular_series_rate(series=timestamps)
            timestamps_are_regular = rate is not None
            starting_time = timestamps[0]
        else:
            rate = float(imaging.get_sampling_frequency())
            timestamps_are_regular = True
            starting_time = 0.0

        if timestamps_are_regular:
            photon_series_kwargs.update(rate=rate, starting_time=starting_time)
        else:
            photon_series_kwargs.update(timestamps=timestamps)

    # Add the photon series to the nwbfile (either as OnePhotonSeries or TwoPhotonSeries)
    photon_series_map = dict(OnePhotonSeries=OnePhotonSeries, TwoPhotonSeries=TwoPhotonSeries)
    photon_series_class = photon_series_map[photon_series_type]
    photon_series = photon_series_class(**photon_series_kwargs)

    if parent_container == "acquisition":
        nwbfile.add_acquisition(photon_series)
    elif parent_container == "processing/ophys":
        ophys_module = get_module(nwbfile, name="ophys", description="contains optical physiology processed data")
        ophys_module.add(photon_series)

    return nwbfile


def add_plane_segmentation_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict | None,
    plane_segmentation_name: str | None = None,
    include_roi_centroids: bool = True,
    include_roi_acceptance: bool = True,
    mask_type: Literal["image", "pixel", "voxel"] = "image",
    iterator_options: dict | None = None,
) -> NWBFile:
    """
    .. deprecated:: 0.8.2
        This function is deprecated and will be removed on or after March 2026.
        It is kept as-is for backward compatibility. Use high-level interface methods instead.
    """
    warnings.warn(
        "The 'add_plane_segmentation_to_nwbfile' function is deprecated and will be removed on or after March 2026. "
        "This is a low-level function that should not be called directly. "
        "Use high-level interface methods like BaseSegmentationExtractorInterface.add_to_nwbfile() instead.",
        FutureWarning,
        stacklevel=2,
    )

    # Duplicated implementation - kept verbatim for backward compatibility
    default_plane_segmentation_index = 0
    roi_ids = segmentation_extractor.get_roi_ids()
    if include_roi_acceptance:
        accepted_list = segmentation_extractor.get_accepted_list()
        is_id_accepted = [int(roi_id in accepted_list) for roi_id in roi_ids]
        rejected_list = segmentation_extractor.get_rejected_list()
        is_id_rejected = [int(roi_id in rejected_list) for roi_id in roi_ids]
    else:
        is_id_accepted, is_id_rejected = None, None
    if mask_type == "image":
        image_or_pixel_masks = segmentation_extractor.get_roi_image_masks()
    elif mask_type == "pixel" or mask_type == "voxel":
        image_or_pixel_masks = segmentation_extractor.get_roi_pixel_masks()
    else:
        raise AssertionError(
            "Keyword argument 'mask_type' must be one of either 'image', 'pixel', 'voxel'. " f"Received '{mask_type}'."
        )
    if include_roi_centroids:
        tranpose_image_convention = (1, 0) if len(segmentation_extractor.get_frame_shape()) == 2 else (1, 0, 2)
        roi_locations = segmentation_extractor.get_roi_locations()[tranpose_image_convention, :].T
    else:
        roi_locations = None

    # Prepare quality metrics data - always attempt to include if available
    segmentation_extractor_properties = {}
    available_properties = segmentation_extractor.get_property_keys()

    # Extract available quality metrics
    for property_key in available_properties:
        values = segmentation_extractor.get_property(key=property_key, ids=roi_ids)
        segmentation_extractor_properties[property_key] = {
            "data": values,
            "description": "",
        }

    nwbfile = _add_plane_segmentation(
        background_or_roi_ids=roi_ids,
        image_or_pixel_masks=image_or_pixel_masks,
        is_id_accepted=is_id_accepted,
        is_id_rejected=is_id_rejected,
        roi_locations=roi_locations,
        default_plane_segmentation_index=default_plane_segmentation_index,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_name=plane_segmentation_name,
        include_roi_centroids=include_roi_centroids,
        include_roi_acceptance=include_roi_acceptance,
        mask_type=mask_type,
        iterator_options=iterator_options,
        segmentation_extractor_properties=segmentation_extractor_properties,
    )
    return nwbfile


def add_background_plane_segmentation_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict | None,
    background_plane_segmentation_name: str | None = None,
    mask_type: Literal["image", "pixel", "voxel"] = "image",
    iterator_options: dict | None = None,
) -> NWBFile:
    """
    .. deprecated:: 0.8.2
        This function is deprecated and will be removed on or after March 2026.
        It is kept as-is for backward compatibility. Use high-level interface methods instead.
    """
    warnings.warn(
        "The 'add_background_plane_segmentation_to_nwbfile' function is deprecated and will be removed on or after March 2026. "
        "This is a low-level function that should not be called directly. "
        "Use high-level interface methods like BaseSegmentationExtractorInterface.add_to_nwbfile() instead.",
        FutureWarning,
        stacklevel=2,
    )

    # Duplicated implementation - kept verbatim for backward compatibility
    default_plane_segmentation_index = 1
    background_ids = segmentation_extractor.get_background_ids()
    if mask_type == "image":
        image_or_pixel_masks = segmentation_extractor.get_background_image_masks()
    elif mask_type == "pixel" or mask_type == "voxel":
        image_or_pixel_masks = segmentation_extractor.get_background_pixel_masks()
    else:
        raise AssertionError(
            "Keyword argument 'mask_type' must be one of either 'image', 'pixel', 'voxel'. " f"Received '{mask_type}'."
        )
    nwbfile = _add_plane_segmentation(
        background_or_roi_ids=background_ids,
        image_or_pixel_masks=image_or_pixel_masks,
        default_plane_segmentation_index=default_plane_segmentation_index,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_name=background_plane_segmentation_name,
        mask_type=mask_type,
        iterator_options=iterator_options,
    )
    return nwbfile


def add_fluorescence_traces_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict | None,
    plane_segmentation_name: str | None = None,
    include_background_segmentation: bool = False,
    iterator_options: dict | None = None,
) -> NWBFile:
    """
    .. deprecated:: 0.8.2
        This function is deprecated and will be removed on or after March 2026.
        It is kept as-is for backward compatibility. Use high-level interface methods instead.
    """
    warnings.warn(
        "The 'add_fluorescence_traces_to_nwbfile' function is deprecated and will be removed on or after March 2026. "
        "This is a low-level function that should not be called directly. "
        "Use high-level interface methods like BaseSegmentationExtractorInterface.add_to_nwbfile() instead.",
        FutureWarning,
        stacklevel=2,
    )

    # Duplicated implementation - kept verbatim for backward compatibility
    default_plane_segmentation_index = 0

    traces_to_add = segmentation_extractor.get_traces_dict()
    # Filter empty data and background traces
    traces_to_add = {
        trace_name: trace for trace_name, trace in traces_to_add.items() if trace is not None and trace.size != 0
    }
    if include_background_segmentation:
        traces_to_add.pop("neuropil", None)
    if not traces_to_add:
        return nwbfile

    roi_ids = segmentation_extractor.get_roi_ids()
    nwbfile = _add_fluorescence_traces_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        traces_to_add=traces_to_add,
        background_or_roi_ids=roi_ids,
        nwbfile=nwbfile,
        metadata=metadata,
        default_plane_segmentation_index=default_plane_segmentation_index,
        plane_segmentation_name=plane_segmentation_name,
        iterator_options=iterator_options,
    )
    return nwbfile


def add_background_fluorescence_traces_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict | None,
    background_plane_segmentation_name: str | None = None,
    iterator_options: dict | None = None,
    compression_options: dict | None = None,  # TODO: remove completely after 10/1/2024
) -> NWBFile:
    """
    .. deprecated:: 0.8.2
        This function is deprecated and will be removed on or after March 2026.
        It is kept as-is for backward compatibility. Use high-level interface methods instead.
    """
    warnings.warn(
        "The 'add_background_fluorescence_traces_to_nwbfile' function is deprecated and will be removed on or after March 2026. "
        "This is a low-level function that should not be called directly. "
        "Use high-level interface methods like BaseSegmentationExtractorInterface.add_to_nwbfile() instead.",
        FutureWarning,
        stacklevel=2,
    )

    # Duplicated implementation - kept verbatim for backward compatibility
    # TODO: remove completely after 10/1/2024
    if compression_options is not None:
        warnings.warn(
            message=(
                "Specifying compression methods and their options at the level of tool functions has been deprecated. "
                "Please use the `configure_backend` tool function for this purpose."
            ),
            category=DeprecationWarning,
            stacklevel=2,
        )

    default_plane_segmentation_index = 1

    traces_to_add = segmentation_extractor.get_traces_dict()
    # Filter empty data and background traces
    traces_to_add = {
        trace_name: trace
        for trace_name, trace in traces_to_add.items()
        if trace is not None and trace.size != 0 and trace_name == "neuropil"
    }
    if not traces_to_add:
        return nwbfile

    background_ids = segmentation_extractor.get_background_ids()
    nwbfile = _add_fluorescence_traces_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        traces_to_add=traces_to_add,
        background_or_roi_ids=background_ids,
        nwbfile=nwbfile,
        metadata=metadata,
        default_plane_segmentation_index=default_plane_segmentation_index,
        plane_segmentation_name=background_plane_segmentation_name,
        iterator_options=iterator_options,
    )
    return nwbfile


def add_summary_images_to_nwbfile(
    nwbfile: NWBFile,
    segmentation_extractor: SegmentationExtractor,
    metadata: dict | None = None,
    plane_segmentation_name: str | None = None,
) -> NWBFile:
    """
    .. deprecated:: 0.8.2
        This function is deprecated and will be removed on or after March 2026.
        It is kept as-is for backward compatibility. Use high-level interface methods instead.
    """
    warnings.warn(
        "The 'add_summary_images_to_nwbfile' function is deprecated and will be removed on or after March 2026. "
        "This is a low-level function that should not be called directly. "
        "Use high-level interface methods like BaseSegmentationExtractorInterface.add_to_nwbfile() instead.",
        FutureWarning,
        stacklevel=2,
    )

    # Duplicated implementation - kept verbatim for backward compatibility
    metadata = metadata or dict()

    # Get defaults from single source of truth
    default_metadata = _get_default_ophys_metadata()
    default_segmentation_images = default_metadata["Ophys"]["SegmentationImages"]

    # Extract SegmentationImages metadata from user or use defaults
    user_segmentation_images = metadata.get("Ophys", {}).get("SegmentationImages", {})

    # Get container name and description
    images_container_name = user_segmentation_images.get("name", default_segmentation_images["name"])
    images_container_description = user_segmentation_images.get(
        "description", default_segmentation_images["description"]
    )

    images_dict = segmentation_extractor.get_images_dict()
    images_to_add = {img_name: img for img_name, img in images_dict.items() if img is not None}
    if not images_to_add:
        return nwbfile

    ophys_module = get_module(nwbfile=nwbfile, name="ophys", description="contains optical physiology processed data")

    # Add Images container if it doesn't exist
    if images_container_name not in ophys_module.data_interfaces:
        ophys_module.add(Images(name=images_container_name, description=images_container_description))
    image_collection = ophys_module.data_interfaces[images_container_name]

    # Determine plane segmentation name
    default_plane_segmentation_name = default_metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]["name"]
    plane_segmentation_name = plane_segmentation_name or default_plane_segmentation_name

    # Get images metadata for this plane segmentation
    if plane_segmentation_name in user_segmentation_images:
        images_metadata = user_segmentation_images[plane_segmentation_name]
    elif plane_segmentation_name in default_segmentation_images:
        images_metadata = default_segmentation_images[plane_segmentation_name]
    else:
        raise ValueError(
            f"Plane segmentation '{plane_segmentation_name}' not found in metadata['Ophys']['SegmentationImages']"
        )

    for img_name, img in images_to_add.items():
        image_kwargs = dict(name=img_name, data=img.T)
        image_metadata = images_metadata.get(img_name, None)
        if image_metadata is not None:
            image_kwargs.update(image_metadata)

        # Note that nwb uses the conversion width x height (columns, rows) and roiextractors uses the transpose
        image_collection.add_image(GrayscaleImage(**image_kwargs))

    return nwbfile
