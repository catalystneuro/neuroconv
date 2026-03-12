import math
import warnings
from typing import Literal

import numpy as np
import psutil
from pydantic import FilePath
from pynwb import NWBFile
from pynwb.base import Images
from pynwb.image import GrayscaleImage
from pynwb.ophys import (
    Fluorescence,
    ImageSegmentation,
    ImagingPlane,
    OnePhotonSeries,
    OpticalChannel,
    PlaneSegmentation,
    RoiResponseSeries,
    TwoPhotonSeries,
)
from roiextractors import (
    ImagingExtractor,
    MultiSegmentationExtractor,
    SegmentationExtractor,
)

from .imagingextractordatachunkiterator import ImagingExtractorDataChunkIterator
from .roiextractors_pending_deprecation import (
    _add_devices_to_nwbfile_old_list_format,
    _add_photon_series_to_nwbfile_old_list_format,
    _add_segmentation_to_nwbfile_old_list_format,
    get_nwb_segmentation_metadata,
)
from ..hdmf import SliceableDataChunkIterator
from ..nwb_helpers import (
    BACKEND_NWB_IO,
    HDF5BackendConfiguration,
    ZarrBackendConfiguration,
    configure_backend,
    get_default_backend_configuration,
    get_default_nwbfile_metadata,
    get_module,
    make_nwbfile_from_metadata,
)
from ..nwb_helpers._metadata_and_file_helpers import (
    _add_device_to_nwbfile,
    _resolve_backend,
    configure_and_write_nwbfile,
)
from ...utils import (
    calculate_regular_series_rate,
    dict_deep_update,
)
from ...utils.str_utils import human_readable_size


def _is_dict_based_metadata(metadata: dict) -> bool:
    """Detect whether metadata uses the new dict-based format or old list-based format.

    Dict-based format has top-level 'Devices' key and/or plural dict-valued keys under 'Ophys'
    ('ImagingPlanes', 'MicroscopySeries', 'PlaneSegmentations', 'RoiResponses').
    List-based format has 'Device' (list) and 'ImagingPlane'
    (list, singular) under 'Ophys'.

    Returns True for dict-based, False for list-based.
    """
    if "Devices" in metadata:
        return True

    ophys = metadata.get("Ophys", {})

    dict_based_keys = {"ImagingPlanes", "MicroscopySeries", "PlaneSegmentations", "RoiResponses", "SegmentationImages"}
    if dict_based_keys & ophys.keys():
        return True

    if "ImagingPlane" in ophys or "Device" in ophys:
        return False

    # Ambiguous or empty metadata defaults to dict-based (the new format)
    return True


def _get_ophys_metadata_placeholders():
    """
    Returns fresh ophys metadata with centralized placeholder values.

    Placeholders are kept in one place so they are easy to identify downstream and
    we make up as little metadata as possible. All fields included here are strictly
    required by the NWB schema. Each call returns an independent copy.

    Until something like https://github.com/NeurodataWithoutBorders/nwb-schema/issues/672
    is accepted, we will keep this approach.
    """
    metadata = get_default_nwbfile_metadata()

    default_metadata_key = "default_metadata_key"

    metadata["Devices"] = {
        default_metadata_key: {
            "name": "Microscope",
        },
    }

    metadata["Ophys"] = {
        "ImagingPlanes": {
            default_metadata_key: {
                "name": "ImagingPlane",
                "excitation_lambda": np.nan,
                "indicator": "unknown",
                "location": "unknown",
                "optical_channel": [
                    {
                        "name": "OpticalChannel",
                        "emission_lambda": np.nan,
                        "description": "An optical channel of the microscope.",
                    }
                ],
            },
        },
        "MicroscopySeries": {
            default_metadata_key: {
                "name": "MicroscopySeries",
                "unit": "n.a.",
                "imaging_plane_metadata_key": default_metadata_key,
            },
        },
        "PlaneSegmentations": {
            default_metadata_key: {
                "name": "PlaneSegmentation",
                "description": "Segmented ROIs",
                "imaging_plane_metadata_key": default_metadata_key,
            },
        },
        "RoiResponses": {
            default_metadata_key: {
                "raw": {
                    "name": "RoiResponseSeries",
                    "unit": "n.a.",
                },
                "deconvolved": {
                    "name": "Deconvolved",
                    "unit": "n.a.",
                },
                "neuropil": {
                    "name": "Neuropil",
                    "unit": "n.a.",
                },
                "denoised": {
                    "name": "Denoised",
                    "unit": "n.a.",
                },
                "baseline": {
                    "name": "Baseline",
                    "unit": "n.a.",
                },
                "dff": {
                    "name": "DfOverF",
                    "unit": "n.a.",
                },
            },
        },
        "SegmentationImages": {
            default_metadata_key: {
                "correlation": {
                    "name": "correlation_image",
                },
                "mean": {
                    "name": "mean_image",
                },
            },
        },
    }

    return metadata


def get_full_ophys_metadata():
    """
    Returns a fully specified ophys metadata example with realistic values.

    Users can call this to get a complete example of what the metadata structure looks like,
    edit only the fields they need, and discard the rest. Each call returns an independent
    copy so callers can modify it freely without affecting other calls.
    """
    metadata = get_default_nwbfile_metadata()

    metadata["Devices"] = {
        "my_microscope": {
            "name": "Microscope",
            "description": "Two-photon microscope",
        },
    }

    metadata["Ophys"] = {
        "ImagingPlanes": {
            "my_plane": {
                "name": "ImagingPlane",
                "description": "Imaging plane in V1",
                "excitation_lambda": 920.0,
                "indicator": "GCaMP6s",
                "location": "V1",
                "device_metadata_key": "my_microscope",
                "optical_channel": [
                    {
                        "name": "Green",
                        "description": "GCaMP emission",
                        "emission_lambda": 510.0,
                    }
                ],
            },
        },
        "MicroscopySeries": {
            "my_series": {
                "name": "TwoPhotonSeries",
                "description": "Two-photon calcium imaging",
                "unit": "n.a.",
                "imaging_plane_metadata_key": "my_plane",
            },
        },
        "PlaneSegmentations": {
            "my_segmentation": {
                "name": "PlaneSegmentation",
                "description": "ROIs detected by Suite2p",
                "imaging_plane_metadata_key": "my_plane",
            },
        },
        "RoiResponses": {
            "my_segmentation": {
                "raw": {
                    "name": "RoiResponseSeries",
                    "description": "Raw fluorescence traces",
                    "unit": "n.a.",
                },
                "neuropil": {
                    "name": "Neuropil",
                    "description": "Neuropil fluorescence",
                    "unit": "n.a.",
                },
                "deconvolved": {
                    "name": "Deconvolved",
                    "description": "Deconvolved activity",
                    "unit": "n.a.",
                },
                "dff": {
                    "name": "DfOverF",
                    "description": "Delta F over F",
                    "unit": "n.a.",
                },
            },
        },
        "SegmentationImages": {
            "my_segmentation": {
                "correlation": {
                    "name": "correlation_image",
                    "description": "Correlation image.",
                },
                "mean": {
                    "name": "mean_image",
                    "description": "Mean image.",
                },
            },
        },
    }

    return metadata


def _add_imaging_plane_to_nwbfile(
    *,
    nwbfile: NWBFile,
    imaging_plane_metadata: dict,
    metadata: dict,
) -> ImagingPlane:
    """
    Add an imaging plane to an NWBFile.

    If an imaging plane with the same name already exists, the existing one is returned.

    The device is resolved via ``device_metadata_key`` in the imaging plane metadata,
    which requires the full metadata to look up the device in ``metadata["Devices"]``.
    If no ``device_metadata_key`` is set, a default device is created.

    Parameters
    ----------
    nwbfile : NWBFile
        The NWB file to add the imaging plane to.
    imaging_plane_metadata : dict
        Dictionary describing the imaging plane (already extracted by the caller).
    metadata : dict
        The full metadata dictionary, needed to resolve ``device_metadata_key``
        references in ``metadata["Devices"]``.

    Returns
    -------
    ImagingPlane
        The ImagingPlane object (either newly created or existing).
    """
    # Copy to avoid mutation
    imaging_plane_kwargs = imaging_plane_metadata.copy()

    # Validate required fields
    required_fields = ["name", "excitation_lambda", "indicator", "location", "optical_channel"]
    missing_fields = [field for field in required_fields if field not in imaging_plane_kwargs]
    if missing_fields:
        default_imaging_plane = _get_ophys_metadata_placeholders()["Ophys"]["ImagingPlanes"]["default_metadata_key"]
        placeholder_hint = "\n".join(f"  {field}: {default_imaging_plane[field]!r}" for field in missing_fields)
        raise ValueError(
            f"Imaging plane metadata is missing required fields.\n"
            f"For a complete NWB file, the following fields should be provided. "
            f"If missing, a placeholder can be used instead:\n{placeholder_hint}"
        )

    # Check if already exists
    imaging_plane_name = imaging_plane_kwargs["name"]
    if imaging_plane_name in nwbfile.imaging_planes:
        return nwbfile.imaging_planes[imaging_plane_name]

    # Resolve device
    device_metadata_key = imaging_plane_kwargs.pop("device_metadata_key", None)
    if device_metadata_key is not None:
        device_metadata = metadata["Devices"][device_metadata_key]
    else:
        device_metadata = _get_ophys_metadata_placeholders()["Devices"]["default_metadata_key"]
    device = _add_device_to_nwbfile(nwbfile=nwbfile, device_metadata=device_metadata)

    imaging_plane_kwargs["device"] = device

    # Convert optical channel metadata dicts to OpticalChannel objects
    imaging_plane_kwargs["optical_channel"] = [
        OpticalChannel(**channel_metadata) for channel_metadata in imaging_plane_kwargs["optical_channel"]
    ]

    imaging_plane = ImagingPlane(**imaging_plane_kwargs)
    nwbfile.add_imaging_plane(imaging_plane)

    return imaging_plane


def _add_photon_series_to_nwbfile(
    *,
    imaging: ImagingExtractor,
    nwbfile: NWBFile,
    metadata: dict,
    photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"],
    metadata_key: str,
    parent_container: Literal["acquisition", "processing/ophys"] = "acquisition",
    iterator_type: str | None = "v2",
    iterator_options: dict | None = None,
    always_write_timestamps: bool = False,
) -> NWBFile:
    """
    Add a photon series using the dict-based metadata format.

    Looks up the microscopy series in ``metadata["Ophys"]["MicroscopySeries"][metadata_key]``
    and creates it in the NWBFile. Resolves the imaging plane via ``imaging_plane_metadata_key``
    in the series metadata.

    Parameters
    ----------
    imaging : ImagingExtractor
        The imaging extractor to get the data from.
    nwbfile : NWBFile
        The NWB file to add the photon series to.
    metadata : dict
        The full metadata dictionary with dict-based format.
    photon_series_type : {'OnePhotonSeries', 'TwoPhotonSeries'}
        The NWB type of photon series to create.
    metadata_key : str
        The key in ``metadata["Ophys"]["MicroscopySeries"]`` identifying the series.
    parent_container : {'acquisition', 'processing/ophys'}, optional
        The container where the photon series is added, default is nwbfile.acquisition.
    iterator_type : str, default: 'v2'
        The type of iterator to use when adding the photon series to the NWB file.
    iterator_options : dict, optional
    always_write_timestamps : bool, default: False
        Set to True to always write timestamps.

    Returns
    -------
    NWBFile
        The NWBFile passed as an input with the photon series added.
    """
    iterator_options = iterator_options or dict()

    photon_series_metadata = metadata["Ophys"]["MicroscopySeries"][metadata_key]

    # Copy to avoid mutation
    photon_series_kwargs = photon_series_metadata.copy()

    # Validate required fields
    required_fields = ["name", "unit"]
    missing_fields = [field for field in required_fields if field not in photon_series_kwargs]
    if missing_fields:
        default_series = _get_ophys_metadata_placeholders()["Ophys"]["MicroscopySeries"]["default_metadata_key"]
        placeholder_hint = "\n".join(f"  {field}: {default_series[field]!r}" for field in missing_fields)
        raise ValueError(
            f"Microscopy series metadata is missing required fields.\n"
            f"For a complete NWB file, the following fields should be provided. "
            f"If missing, a placeholder can be used instead:\n{placeholder_hint}"
        )

    # Resolve imaging plane
    imaging_plane_metadata_key = photon_series_kwargs.pop("imaging_plane_metadata_key", None)
    if imaging_plane_metadata_key is not None:
        imaging_plane_metadata = metadata["Ophys"]["ImagingPlanes"][imaging_plane_metadata_key]
    else:
        default_metadata = _get_ophys_metadata_placeholders()
        imaging_plane_metadata = default_metadata["Ophys"]["ImagingPlanes"]["default_metadata_key"]
    imaging_plane = _add_imaging_plane_to_nwbfile(
        nwbfile=nwbfile,
        imaging_plane_metadata=imaging_plane_metadata,
        metadata=metadata,
    )
    photon_series_kwargs["imaging_plane"] = imaging_plane

    # Add dimension if not in metadata
    if "dimension" not in photon_series_kwargs:
        photon_series_kwargs["dimension"] = imaging.get_sample_shape()

    # Add data iterator
    imaging_extractor_iterator = _imaging_frames_to_hdmf_iterator(
        imaging=imaging,
        iterator_type=iterator_type,
        iterator_options=iterator_options,
    )
    photon_series_kwargs["data"] = imaging_extractor_iterator

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

    # Add the photon series to the nwbfile
    photon_series_map = dict(OnePhotonSeries=OnePhotonSeries, TwoPhotonSeries=TwoPhotonSeries)
    photon_series_class = photon_series_map[photon_series_type]
    photon_series = photon_series_class(**photon_series_kwargs)

    if parent_container == "acquisition":
        nwbfile.add_acquisition(photon_series)
    elif parent_container == "processing/ophys":
        ophys_module = get_module(nwbfile, name="ophys", description="contains optical physiology processed data")
        ophys_module.add(photon_series)

    return nwbfile


def _add_plane_segmentation_to_nwbfile(
    *,
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict,
    metadata_key: str,
) -> NWBFile:
    """
    Add a PlaneSegmentation to an NWBFile using dict-based metadata.

    Masks are written in the extractor's native format (image, pixel, or voxel) as
    determined by ``_roi_masks.mask_tpe``. All extractor properties (including
    acceptance/rejection status and quality metrics) are written as columns on the
    PlaneSegmentation table via the roiextractors property system.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get the results from.
    nwbfile : NWBFile
        The NWB file to add the plane segmentation to.
    metadata : dict
        The full metadata dictionary with dict-based format.
    metadata_key : str
        The key in ``metadata["Ophys"]["PlaneSegmentations"]`` identifying the segmentation.

    Returns
    -------
    NWBFile
        The NWBFile with the added PlaneSegmentation.
    """
    plane_seg_metadata = metadata["Ophys"]["PlaneSegmentations"][metadata_key].copy()

    # Validate required fields
    required_fields = ["description"]
    missing_fields = [field for field in required_fields if field not in plane_seg_metadata]
    if missing_fields:
        default_plane_seg = _get_ophys_metadata_placeholders()["Ophys"]["PlaneSegmentations"]["default_metadata_key"]
        placeholder_hint = "\n".join(f"  {field}: {default_plane_seg[field]!r}" for field in missing_fields)
        raise ValueError(
            f"Plane segmentation metadata is missing required fields.\n"
            f"For a complete NWB file, the following fields should be provided. "
            f"If missing, a placeholder can be used instead:\n{placeholder_hint}"
        )

    # Resolve imaging plane
    imaging_plane_metadata_key = plane_seg_metadata.pop("imaging_plane_metadata_key", None)
    if imaging_plane_metadata_key is not None:
        imaging_plane_metadata = metadata["Ophys"]["ImagingPlanes"][imaging_plane_metadata_key]
    else:
        default_metadata = _get_ophys_metadata_placeholders()
        imaging_plane_metadata = default_metadata["Ophys"]["ImagingPlanes"]["default_metadata_key"]
    imaging_plane = _add_imaging_plane_to_nwbfile(
        nwbfile=nwbfile,
        imaging_plane_metadata=imaging_plane_metadata,
        metadata=metadata,
    )

    # Get or create ImageSegmentation container
    ophys_module = get_module(nwbfile, "ophys", description="contains optical physiology processed data")
    image_segmentation_name = "ImageSegmentation"
    if image_segmentation_name in ophys_module.data_interfaces:
        image_segmentation = ophys_module[image_segmentation_name]
    else:
        image_segmentation = ImageSegmentation(name=image_segmentation_name)
        ophys_module.add(image_segmentation)

    plane_segmentation_name = plane_seg_metadata["name"]

    # If PlaneSegmentation already exists, return early
    if plane_segmentation_name in image_segmentation.plane_segmentations:
        return nwbfile

    # Extract ROI data
    roi_ids = segmentation_extractor.get_roi_ids()

    # Detect native mask format from the extractor
    # TODO: open a discussion on roiextractors to expose mask_tpe as a public API
    native_mask_type = segmentation_extractor._roi_masks.mask_tpe  # e.g. "nwb-image_mask"
    mask_type = native_mask_type.replace("nwb-", "").replace("_mask", "")  # "image", "pixel", or "voxel"

    if mask_type == "image":
        image_or_pixel_masks = segmentation_extractor.get_roi_image_masks()
    else:
        image_or_pixel_masks = segmentation_extractor.get_roi_pixel_masks()

    # Build PlaneSegmentation object
    plane_seg_metadata["imaging_plane"] = imaging_plane
    plane_segmentation = PlaneSegmentation(**plane_seg_metadata)

    # Add ROIs
    roi_names = [str(roi_id) for roi_id in roi_ids]
    roi_indices = list(range(len(roi_ids)))
    plane_segmentation.add_column(name="roi_name", description="The unique identifier for each ROI.")

    if mask_type == "image":
        image_mask_array = image_or_pixel_masks.T
        for roi_index, roi_name in zip(roi_indices, roi_names):
            image_mask = image_mask_array[roi_index]
            plane_segmentation.add_roi(id=roi_index, roi_name=roi_name, image_mask=image_mask)
    else:
        mask_type_kwarg = f"{mask_type}_mask"
        pixel_masks = image_or_pixel_masks
        for roi_index, roi_name in zip(roi_indices, roi_names):
            pixel_mask = pixel_masks[roi_index]
            pixel_mask_to_write = [tuple(x) for x in pixel_mask]
            plane_segmentation.add_roi(id=roi_index, roi_name=roi_name, **{mask_type_kwarg: pixel_mask_to_write})

    # Add all extractor properties as columns (acceptance, quality metrics, etc.)
    available_properties = segmentation_extractor.get_property_keys()
    for property_key in available_properties:
        values = segmentation_extractor.get_property(key=property_key, ids=roi_ids)
        plane_segmentation.add_column(name=property_key, description="", data=values)

    image_segmentation.add_plane_segmentation(plane_segmentations=[plane_segmentation])

    return nwbfile


def _add_roi_response_traces_to_nwbfile(
    *,
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict,
    metadata_key: str,
    iterator_options: dict | None = None,
) -> NWBFile:
    """
    Add ROI response traces to an NWBFile using dict-based metadata.

    Adds all traces as ``RoiResponseSeries`` inside a single ``Fluorescence`` container,
    without splitting into ``Fluorescence`` and ``DfOverF``. This follows the direction
    of nwb-schema#616 and ndx-microscopy's single-container pattern
    (``MicroscopyResponseSeriesContainer``).

    The same ``metadata_key`` is used to look up both the ``RoiResponses`` entry and the
    ``PlaneSegmentations`` entry, coupling the two implicitly.

    If ``metadata_key`` is not present in ``metadata["Ophys"]["RoiResponses"]``, placeholder
    metadata is used for all available traces. If ``metadata_key`` is present but the extractor
    has no trace data, a ``ValueError`` is raised.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor containing trace data.
    nwbfile : NWBFile
        The NWB file to add traces to.
    metadata : dict
        The full metadata dictionary with dict-based format. Not modified by this function.
    metadata_key : str
        The key used to look up both ``metadata["Ophys"]["RoiResponses"]`` and
        ``metadata["Ophys"]["PlaneSegmentations"]``.
    iterator_options : dict, optional
        Options for the data chunk iterator.

    Returns
    -------
    NWBFile
        The NWBFile with the added traces.
    """
    iterator_options = iterator_options or dict()

    # Get traces from extractor, filter None/empty
    traces_dict = segmentation_extractor.get_traces_dict()
    traces_to_add = {
        trace_name: trace for trace_name, trace in traces_dict.items() if trace is not None and trace.size != 0
    }

    roi_responses = metadata.get("Ophys", {}).get("RoiResponses", {})
    user_provided_roi_responses = metadata_key in roi_responses

    if user_provided_roi_responses and not traces_to_add:
        raise ValueError("RoiResponses metadata was provided but the segmentation extractor has no trace data.")

    if not traces_to_add:
        return nwbfile

    # Use user-provided metadata or fall back to placeholders
    user_provided_roi_responses_metadata = user_provided_roi_responses and metadata_key != "default_metadata_key"
    if user_provided_roi_responses:
        roi_responses_metadata = roi_responses[metadata_key].copy()
        if user_provided_roi_responses_metadata:
            requested_traces = set(roi_responses_metadata.keys())
            available_traces = set(traces_to_add.keys())
            missing_traces = requested_traces - available_traces
            if missing_traces:
                warnings.warn(
                    f"RoiResponses metadata specifies traces {missing_traces} "
                    f"but the segmentation extractor has no data for them. "
                    f"These traces will be skipped."
                )
    else:
        roi_responses_metadata = _get_ophys_metadata_placeholders()["Ophys"]["RoiResponses"]["default_metadata_key"]

    # Resolve PlaneSegmentation via the same metadata_key
    plane_segmentation_name = metadata["Ophys"]["PlaneSegmentations"][metadata_key]["name"]
    ophys_module = get_module(nwbfile, "ophys", description="contains optical physiology processed data")
    image_segmentation = ophys_module["ImageSegmentation"]
    plane_segmentation = image_segmentation.plane_segmentations[plane_segmentation_name]

    # Create ROI table region
    roi_ids = segmentation_extractor.get_roi_ids()
    available_roi_names = list(plane_segmentation["roi_name"][:])
    roi_names = [str(roi_id) for roi_id in roi_ids]
    region = [available_roi_names.index(roi_name) for roi_name in roi_names]
    imaging_plane_name = plane_segmentation.imaging_plane.name
    roi_table_region = plane_segmentation.create_roi_table_region(
        region=region,
        description=f"The ROIs for {imaging_plane_name}.",
    )

    # Resolve timestamps
    timestamps_were_set = segmentation_extractor.has_time_vector()
    if timestamps_were_set:
        timestamps = segmentation_extractor.get_timestamps()
    else:
        timestamps = segmentation_extractor.get_native_timestamps()

    timestamps_are_available = timestamps is not None

    if timestamps_are_available:
        rate = calculate_regular_series_rate(series=timestamps)
        timestamps_are_regular = rate is not None
        starting_time = timestamps[0]
    else:
        rate = float(segmentation_extractor.get_sampling_frequency())
        timestamps_are_regular = True
        starting_time = 0.0

    # All traces go into a single Fluorescence container, matching the pattern from
    # ndx-microscopy (single MicroscopyResponseSeriesContainer) and avoiding the
    # Fluorescence/DfOverF split that nwb-schema#616 proposes to remove.
    fluorescence_name = "Fluorescence"
    if fluorescence_name in ophys_module.data_interfaces:
        fluorescence = ophys_module[fluorescence_name]
    else:
        fluorescence = Fluorescence(name=fluorescence_name)
        ophys_module.add(fluorescence)

    for trace_name, trace_data in traces_to_add.items():
        # Skip traces not in metadata
        if trace_name not in roi_responses_metadata:
            continue

        trace_metadata = roi_responses_metadata[trace_name]

        # Validate required fields
        required_fields = ["unit"]
        missing_fields = [field for field in required_fields if field not in trace_metadata]
        if missing_fields:
            default_roi_responses = _get_ophys_metadata_placeholders()["Ophys"]["RoiResponses"]["default_metadata_key"]
            default_trace = default_roi_responses.get(
                trace_name, next(v for v in default_roi_responses.values() if isinstance(v, dict))
            )
            placeholder_hint = "\n".join(f"  {field}: {default_trace[field]!r}" for field in missing_fields)
            raise ValueError(
                f"ROI response series '{trace_name}' metadata is missing required fields.\n"
                f"For a complete NWB file, the following fields should be provided. "
                f"If missing, a placeholder can be used instead:\n{placeholder_hint}"
            )

        # Skip if series already exists
        series_name = trace_metadata["name"]
        if series_name in fluorescence.roi_response_series:
            continue

        roi_response_series_kwargs = trace_metadata.copy()
        roi_response_series_kwargs["data"] = SliceableDataChunkIterator(trace_data, **iterator_options)
        roi_response_series_kwargs["rois"] = roi_table_region

        if timestamps_are_regular:
            roi_response_series_kwargs["starting_time"] = starting_time
            roi_response_series_kwargs["rate"] = rate
        else:
            roi_response_series_kwargs["timestamps"] = timestamps

        roi_response_series = RoiResponseSeries(**roi_response_series_kwargs)
        fluorescence.add_roi_response_series(roi_response_series)

    return nwbfile


def _add_summary_images_to_nwbfile(
    *,
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict,
    metadata_key: str,
) -> NWBFile:
    """
    Add summary images (e.g. mean and correlation) to an NWBFile.

    Images are added to a single ``Images`` container named ``"SegmentationImages"``
    in the ``ophys`` processing module. If the extractor has no images, this is a no-op.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor containing image data.
    nwbfile : NWBFile
        The NWB file to add images to.
    metadata : dict
        The full metadata dictionary. Image metadata is looked up under
        ``metadata["Ophys"]["SegmentationImages"][metadata_key]``.
    metadata_key : str
        The key identifying which segmentation's image metadata to use.

    Returns
    -------
    NWBFile
        The NWBFile with the added summary images.
    """
    images_dict = segmentation_extractor.get_images_dict()
    images_to_add = {img_name: img for img_name, img in images_dict.items() if img is not None}
    if not images_to_add:
        return nwbfile

    # Look up per-image metadata for this segmentation
    segmentation_images_metadata = metadata.get("Ophys", {}).get("SegmentationImages", {})
    user_provided_images_metadata = (
        metadata_key in segmentation_images_metadata and metadata_key != "default_metadata_key"
    )
    if metadata_key in segmentation_images_metadata:
        images_metadata = segmentation_images_metadata[metadata_key]
        if user_provided_images_metadata:
            requested_images = set(images_metadata.keys())
            available_images = set(images_to_add.keys())
            missing_images = requested_images - available_images
            if missing_images:
                warnings.warn(
                    f"SegmentationImages metadata specifies images {missing_images} "
                    f"but the segmentation extractor has no data for them. "
                    f"These images will be skipped."
                )
    else:
        placeholders = _get_ophys_metadata_placeholders()
        images_metadata = placeholders["Ophys"]["SegmentationImages"]["default_metadata_key"]

    # Get or create the single shared Images container
    container_name = "SegmentationImages"
    container_description = "Summary images for segmentation."
    ophys_module = get_module(nwbfile=nwbfile, name="ophys", description="contains optical physiology processed data")

    if container_name not in ophys_module.data_interfaces:
        ophys_module.add(Images(name=container_name, description=container_description))
    image_collection = ophys_module.data_interfaces[container_name]

    for img_type, img_data in images_to_add.items():
        # Skip image types not in metadata (metadata controls what gets written)
        if img_type not in images_metadata:
            continue

        image_metadata = images_metadata[img_type]
        image_name = image_metadata.get("name", img_type)
        image_description = image_metadata.get("description", f"Summary image: {img_type}.")

        # Skip if an image with this name already exists in the container
        if image_name in image_collection.images:
            continue

        # NWB uses width x height (columns, rows); roiextractors uses height x width (rows, columns)
        image_collection.add_image(GrayscaleImage(name=image_name, data=img_data.T, description=image_description))

    return nwbfile


def _add_segmentation_to_nwbfile(
    *,
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict,
    metadata_key: str,
    iterator_options: dict | None = None,
) -> NWBFile:
    """
    Add segmentation data to an NWBFile using dict-based metadata.

    Orchestrates adding the PlaneSegmentation and ROI response traces.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor containing all segmentation data.
    nwbfile : NWBFile
        The NWB file to add segmentation data to.
    metadata : dict
        The full metadata dictionary with dict-based format.
    metadata_key : str
        The key used across ``PlaneSegmentations`` and ``RoiResponses``.
    iterator_options : dict, optional
        Options for the data chunk iterator.

    Returns
    -------
    NWBFile
        The NWBFile with the added segmentation data.
    """
    _add_plane_segmentation_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        nwbfile=nwbfile,
        metadata=metadata,
        metadata_key=metadata_key,
    )

    _add_roi_response_traces_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        nwbfile=nwbfile,
        metadata=metadata,
        metadata_key=metadata_key,
        iterator_options=iterator_options,
    )

    _add_summary_images_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        nwbfile=nwbfile,
        metadata=metadata,
        metadata_key=metadata_key,
    )

    return nwbfile


def _check_if_imaging_fits_into_memory(imaging: ImagingExtractor) -> None:
    """
    Raise an error if the full traces of an imaging extractor are larger than available memory.

    Parameters
    ----------
    imaging : ImagingExtractor
        An imaging extractor object from roiextractors.

    Raises
    ------
    MemoryError
    """
    element_size_in_bytes = imaging.get_dtype().itemsize
    sample_shape = imaging.get_sample_shape()
    num_samples = imaging.get_num_samples()

    traces_size_in_bytes = num_samples * math.prod(sample_shape) * element_size_in_bytes
    available_memory_in_bytes = psutil.virtual_memory().available

    if traces_size_in_bytes > available_memory_in_bytes:
        message = (
            f"Memory error, full TwoPhotonSeries data is {human_readable_size(traces_size_in_bytes, binary=True)} but "
            f"only {human_readable_size(available_memory_in_bytes, binary=True)} are available! "
            "Please use iterator_type='v2'."
        )
        raise MemoryError(message)


def _imaging_frames_to_hdmf_iterator(
    imaging: ImagingExtractor,
    iterator_type: str | None = "v2",
    iterator_options: dict | None = None,
):
    """
    Private auxiliary method to wrap frames from an ImagingExtractor into a DataChunkIterator.

    Parameters
    ----------
    imaging : ImagingExtractor
        The imaging extractor to get the data from.
    iterator_type : {"v2", None}, default: 'v2'
        The type of iterator for chunked data writing.
        'v2': Uses iterative write with control over chunking and progress bars.
        None: Loads all data into memory before writing (not recommended for large datasets).
    iterator_options : dict, optional
        Options for controlling the iterative write process. See the
        `pynwb tutorial on iterative write <https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/plot_iterative_write.html#sphx-glr-tutorials-advanced-io-plot-iterative-write-py>`_
        for more information on chunked data writing.

    Returns
    -------
    iterator
        The frames of the imaging extractor wrapped in an iterator for chunked writing.
    """

    assert iterator_type in ["v2", None], "'iterator_type' must be either 'v2' (recommended) or None."
    iterator_options = dict() if iterator_options is None else iterator_options

    if iterator_type is None:
        _check_if_imaging_fits_into_memory(imaging=imaging)
        return imaging.get_series().transpose((0, 2, 1))

    return ImagingExtractorDataChunkIterator(imaging_extractor=imaging, **iterator_options)


def add_imaging_to_nwbfile(
    imaging: ImagingExtractor,
    nwbfile: NWBFile,
    metadata: dict | None = None,
    *args,  # TODO: change to * (keyword only) on or after September 2026
    photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "TwoPhotonSeries",
    photon_series_index: int = 0,
    iterator_type: str | None = "v2",
    iterator_options: dict | None = None,
    parent_container: Literal["acquisition", "processing/ophys"] = "acquisition",
    always_write_timestamps: bool = False,
    # TODO: move metadata_key after metadata once positional args removed (September 2026)
    metadata_key: str | None = None,
) -> NWBFile:
    """
    Add imaging data from an ImagingExtractor object to an NWBFile.

    Supports both old list-based metadata (via ``photon_series_index``) and
    new dict-based metadata (via ``metadata_key``).

    Parameters
    ----------
    imaging : ImagingExtractor
        The extractor object containing the imaging data.
    nwbfile : NWBFile
        The NWB file where the imaging data will be added.
    metadata : dict, optional
        Metadata for the NWBFile, by default None.
    photon_series_type : {"TwoPhotonSeries", "OnePhotonSeries"}, optional
        The type of photon series to be added, by default "TwoPhotonSeries".
    photon_series_index : int, optional
        The index of the photon series in the provided imaging data, by default 0.
        Used with the old list-based metadata format.
    iterator_type : str, optional
        The type of iterator to use for adding the data. Commonly used to manage large datasets, by default "v2".
    iterator_options : dict, optional
        Additional options for controlling the iteration process, by default None.
    parent_container : {"acquisition", "processing/ophys"}, optional
        Specifies the parent container to which the photon series should be added, either as part of "acquisition" or
        under the "processing/ophys" module, by default "acquisition".
    always_write_timestamps : bool, default: False
        Set to True to always write timestamps.
        By default (False), the function checks if the timestamps are uniformly sampled, and if so, stores the data
        using a regular sampling rate instead of explicit timestamps. If set to True, timestamps will be written
        explicitly, regardless of whether the sampling rate is uniform.
    metadata_key : str, optional
        The key in ``metadata["Ophys"]["MicroscopySeries"]`` identifying the series.
        When provided, uses the new dict-based metadata format and ``photon_series_index`` is ignored.

    Returns
    -------
    NWBFile
        The NWB file with the imaging data added

    """
    # TODO: Remove this block in September 2026 or after when positional arguments are no longer supported.
    if args:
        parameter_names = [
            "photon_series_type",
            "photon_series_index",
            "iterator_type",
            "iterator_options",
            "parent_container",
            "always_write_timestamps",
        ]
        num_positional_args_before_args = 3  # imaging, nwbfile, metadata
        if len(args) > len(parameter_names):
            raise TypeError(
                f"add_imaging_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                f"{len(args) + num_positional_args_before_args} were given. "
                "Note: Positional arguments are deprecated and will be removed in September 2026 or after. Please use keyword arguments."
            )
        positional_values = dict(zip(parameter_names, args))
        passed_as_positional = list(positional_values.keys())
        warnings.warn(
            f"Passing arguments positionally to add_imaging_to_nwbfile is deprecated "
            f"and will be removed in September 2026 or after. "
            f"The following arguments were passed positionally: {passed_as_positional}. "
            "Please use keyword arguments instead.",
            FutureWarning,
            stacklevel=2,
        )
        photon_series_type = positional_values.get("photon_series_type", photon_series_type)
        photon_series_index = positional_values.get("photon_series_index", photon_series_index)
        iterator_type = positional_values.get("iterator_type", iterator_type)
        iterator_options = positional_values.get("iterator_options", iterator_options)
        parent_container = positional_values.get("parent_container", parent_container)
        always_write_timestamps = positional_values.get("always_write_timestamps", always_write_timestamps)

    if metadata is None:
        metadata = _get_ophys_metadata_placeholders()

    if _is_dict_based_metadata(metadata):
        metadata_key = metadata_key or "default_metadata_key"
        nwbfile = _add_photon_series_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            metadata_key=metadata_key,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
            parent_container=parent_container,
            always_write_timestamps=always_write_timestamps,
        )
    else:
        _add_devices_to_nwbfile_old_list_format(nwbfile=nwbfile, metadata=metadata)
        nwbfile = _add_photon_series_to_nwbfile_old_list_format(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            photon_series_index=photon_series_index,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
            parent_container=parent_container,
            always_write_timestamps=always_write_timestamps,
        )

    return nwbfile


def write_imaging_to_nwbfile(
    imaging: ImagingExtractor,
    nwbfile_path: FilePath | None = None,
    nwbfile: NWBFile | None = None,
    metadata: dict | None = None,
    overwrite: bool = False,
    verbose: bool = False,
    photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "TwoPhotonSeries",
    *,
    iterator_type: str | None = "v2",
    iterator_options: dict | None = None,
    backend: Literal["hdf5", "zarr"] | None = None,
    backend_configuration: HDF5BackendConfiguration | ZarrBackendConfiguration | None = None,
    append_on_disk_nwbfile: bool = False,
) -> NWBFile | None:
    """
    Primary method for writing an ImagingExtractor object to an NWBFile.

    Parameters
    ----------
    imaging : ImagingExtractor
        The imaging extractor object to be written to nwb.
    nwbfile_path : FilePath, optional
        Path for where to write the NWBFile.
        If not provided, only adds data to the in-memory nwbfile without writing to disk.
        **Deprecated**: Using this function without nwbfile_path is deprecated.
        Use ``add_imaging_to_nwbfile`` instead.
    nwbfile : NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling::

            write_imaging_to_nwbfile(imaging=my_imaging_extractor, nwbfile=my_nwbfile)

        will result in the appropriate changes to the my_nwbfile object.
    metadata : dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
    overwrite : bool, default: False
        Whether to overwrite the NWBFile if one exists at the nwbfile_path.
    verbose : bool, default: False
        If 'nwbfile_path' is specified, informs user after a successful write operation.
    photon_series_type : {"TwoPhotonSeries", "OnePhotonSeries"}, default: "TwoPhotonSeries"
        The type of photon series to add.
    iterator_type : {"v2", None}, default: "v2"
        The type of iterator for chunked data writing.
        'v2': Uses iterative write with control over chunking and progress bars.
        None: Loads all data into memory before writing (not recommended for large datasets).
    iterator_options : dict, optional
        Options for controlling the iterative write process. See the
        `pynwb tutorial on iterative write <https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/plot_iterative_write.html#sphx-glr-tutorials-advanced-io-plot-iterative-write-py>`_
        for more information on chunked data writing.
    backend : {"hdf5", "zarr"}, optional
        The type of backend to use when writing the file.
        If a ``backend_configuration`` is not specified, the default type will be "hdf5".
        If a ``backend_configuration`` is specified, then the type will be auto-detected.
    backend_configuration : HDF5BackendConfiguration or ZarrBackendConfiguration, optional
        The configuration model to use when configuring the datasets for this backend.
    append_on_disk_nwbfile : bool, default: False
        Whether to append to an existing NWBFile on disk. If True, the ``nwbfile`` parameter must be None.

    Returns
    -------
    NWBFile or None
        The NWBFile object when writing a new file or using an in-memory nwbfile.
        Returns None when appending to an existing file on disk (append_on_disk_nwbfile=True).
        **Deprecated**: Returning NWBFile in append mode is deprecated and will return None on or after June 2026.
    """
    # Handle deprecated usage without nwbfile_path
    if nwbfile_path is None:
        warnings.warn(
            "Using 'write_imaging_to_nwbfile' without 'nwbfile_path' to only add data to an in-memory nwbfile "
            "is deprecated and will be removed on or after June 2026. Use 'add_imaging_to_nwbfile' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if nwbfile is None:
            raise ValueError(
                "Either 'nwbfile_path' or 'nwbfile' must be provided. "
                "To add data to an in-memory nwbfile, use 'add_imaging_to_nwbfile' instead."
            )
        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
        )
        return nwbfile

    iterator_options = iterator_options or dict()

    if metadata is None:
        metadata = dict()
    if hasattr(imaging, "nwb_metadata"):
        metadata = dict_deep_update(imaging.nwb_metadata, metadata, append_list=False)

    appending_to_in_memory_nwbfile = nwbfile is not None
    file_initially_exists = nwbfile_path.exists()
    allowed_to_modify_existing = overwrite or append_on_disk_nwbfile

    if file_initially_exists and not allowed_to_modify_existing:
        raise FileExistsError(
            f"The file at '{nwbfile_path}' already exists. Set overwrite=True to overwrite the existing file "
            "or append_on_disk_nwbfile=True to append to the existing file."
        )

    if append_on_disk_nwbfile and appending_to_in_memory_nwbfile:
        raise ValueError(
            "Cannot append to an existing file on disk while also providing an in-memory NWBFile. "
            "Either set append_on_disk_nwbfile=False to write the in-memory NWBFile to disk, "
            "or remove the nwbfile parameter to append to the existing file on disk."
        )

    # Resolve backend
    backend = _resolve_backend(backend=backend, backend_configuration=backend_configuration)

    # Determine if we're writing a new file or appending
    writing_new_file = not append_on_disk_nwbfile

    if writing_new_file:
        # Writing mode: create or use provided nwbfile and write
        if nwbfile is None:
            nwbfile = make_nwbfile_from_metadata(metadata=metadata)

        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
        )

        if backend_configuration is None:
            backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)

        configure_and_write_nwbfile(
            nwbfile=nwbfile,
            nwbfile_path=nwbfile_path,
            backend=backend,
            backend_configuration=backend_configuration,
        )

        if verbose:
            print(f"NWB file saved at {nwbfile_path}!")

        return nwbfile

    else:
        # Append mode: read existing file, add data, write back
        warnings.warn(
            "Returning an NWBFile object when using append_on_disk_nwbfile=True is deprecated "
            "and will return None on or after June 2026.",
            DeprecationWarning,
            stacklevel=2,
        )

        IO = BACKEND_NWB_IO[backend]

        with IO(path=str(nwbfile_path), mode="r+", load_namespaces=True) as io:
            nwbfile = io.read()

            add_imaging_to_nwbfile(
                imaging=imaging,
                nwbfile=nwbfile,
                metadata=metadata,
                photon_series_type=photon_series_type,
                iterator_type=iterator_type,
                iterator_options=iterator_options,
            )

            if backend_configuration is None:
                backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)

            configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

            io.write(nwbfile)

        if verbose:
            print(f"NWB file saved at {nwbfile_path}!")

        return nwbfile


def add_segmentation_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict | None = None,
    *args,  # TODO: change to * (keyword only) on or after September 2026
    plane_segmentation_name: str | None = None,
    background_plane_segmentation_name: str | None = None,
    include_background_segmentation: bool = False,
    include_roi_centroids: bool = True,
    include_roi_acceptance: bool = True,
    mask_type: Literal["image", "pixel", "voxel"] = "image",
    iterator_options: dict | None = None,
    # TODO: move metadata_key after metadata once positional args removed (September 2026)
    metadata_key: str | None = None,
) -> NWBFile:
    """
    Add segmentation data from a SegmentationExtractor object to an NWBFile.

    Supports both old list-based metadata and new dict-based metadata (via ``metadata_key``).

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The extractor object containing segmentation data.
    nwbfile : NWBFile
        The NWB file where the segmentation data will be added.
    metadata : dict, optional
        Metadata for the NWBFile, by default None.
    plane_segmentation_name : str, optional
        The name of the PlaneSegmentation object to be added, by default None.
        Used with the old list-based metadata format.
    background_plane_segmentation_name : str, optional
        The name of the background PlaneSegmentation, if any, by default None.
        Used with the old list-based metadata format.
    include_background_segmentation : bool, optional
        If True, includes background plane segmentation, by default False.
        Used with the old list-based metadata format.
    include_roi_centroids : bool, optional
        If True, includes the centroids of the regions of interest (ROIs), by default True.
    include_roi_acceptance : bool, optional
        If True, includes the acceptance status of ROIs, by default True.
    mask_type : str
        Type of mask to use for segmentation; can be either "image" or "pixel", by default "image".
    iterator_options : dict, optional
        Options for iterating over the data, by default None.
    metadata_key : str, optional
        The key in ``metadata["Ophys"]["PlaneSegmentations"]`` identifying the segmentation.
        When provided, uses the new dict-based metadata format.

    Returns
    -------
    NWBFile
        The NWBFile with the added segmentation data.
    """
    # TODO: Remove this block in September 2026 or after when positional arguments are no longer supported.
    if args:
        parameter_names = [
            "plane_segmentation_name",
            "background_plane_segmentation_name",
            "include_background_segmentation",
            "include_roi_centroids",
            "include_roi_acceptance",
            "mask_type",
            "iterator_options",
        ]
        num_positional_args_before_args = 3  # segmentation_extractor, nwbfile, metadata
        if len(args) > len(parameter_names):
            raise TypeError(
                f"add_segmentation_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                f"{len(args) + num_positional_args_before_args} were given. "
                "Note: Positional arguments are deprecated and will be removed in September 2026 or after. Please use keyword arguments."
            )
        positional_values = dict(zip(parameter_names, args))
        passed_as_positional = list(positional_values.keys())
        warnings.warn(
            f"Passing arguments positionally to add_segmentation_to_nwbfile is deprecated "
            f"and will be removed in September 2026 or after. "
            f"The following arguments were passed positionally: {passed_as_positional}. "
            "Please use keyword arguments instead.",
            FutureWarning,
            stacklevel=2,
        )
        plane_segmentation_name = positional_values.get("plane_segmentation_name", plane_segmentation_name)
        background_plane_segmentation_name = positional_values.get(
            "background_plane_segmentation_name", background_plane_segmentation_name
        )
        include_background_segmentation = positional_values.get(
            "include_background_segmentation", include_background_segmentation
        )
        include_roi_centroids = positional_values.get("include_roi_centroids", include_roi_centroids)
        include_roi_acceptance = positional_values.get("include_roi_acceptance", include_roi_acceptance)
        mask_type = positional_values.get("mask_type", mask_type)
        iterator_options = positional_values.get("iterator_options", iterator_options)

    if metadata is None:
        metadata = _get_ophys_metadata_placeholders()

    if _is_dict_based_metadata(metadata):
        metadata_key = metadata_key or "default_metadata_key"
        nwbfile = _add_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            metadata_key=metadata_key,
            iterator_options=iterator_options,
        )
    else:
        nwbfile = _add_segmentation_to_nwbfile_old_list_format(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            plane_segmentation_name=plane_segmentation_name,
            background_plane_segmentation_name=background_plane_segmentation_name,
            include_background_segmentation=include_background_segmentation,
            include_roi_centroids=include_roi_centroids,
            include_roi_acceptance=include_roi_acceptance,
            mask_type=mask_type,
            iterator_options=iterator_options,
        )

    return nwbfile


def write_segmentation_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile_path: FilePath | None = None,
    nwbfile: NWBFile | None = None,
    metadata: dict | None = None,
    overwrite: bool = False,
    verbose: bool = False,
    include_background_segmentation: bool = False,
    include_roi_centroids: bool = True,
    include_roi_acceptance: bool = True,
    mask_type: Literal["image", "pixel", "voxel"] = "image",
    *,
    iterator_options: dict | None = None,
    backend: Literal["hdf5", "zarr"] | None = None,
    backend_configuration: HDF5BackendConfiguration | ZarrBackendConfiguration | None = None,
    append_on_disk_nwbfile: bool = False,
) -> NWBFile | None:
    """
    Primary method for writing a SegmentationExtractor object to an NWBFile.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor object to be written to nwb.
    nwbfile_path : FilePath, optional
        Path for where to write the NWBFile.
        If not provided, only adds data to the in-memory nwbfile without writing to disk.
        **Deprecated**: Using this function without nwbfile_path is deprecated.
        Use ``add_segmentation_to_nwbfile`` instead.
    nwbfile : NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling::

            write_segmentation_to_nwbfile(segmentation_extractor=my_segmentation_extractor, nwbfile=my_nwbfile)

        will result in the appropriate changes to the my_nwbfile object.
    metadata : dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
    overwrite : bool, default: False
        Whether to overwrite the NWBFile if one exists at the nwbfile_path.
    verbose : bool, default: False
        If 'nwbfile_path' is specified, informs user after a successful write operation.
    include_background_segmentation : bool, default: False
        Whether to include the background plane segmentation and fluorescence traces in the NWB file. If False,
        neuropil traces are included in the main plane segmentation rather than the background plane segmentation.
    include_roi_centroids : bool, default: True
        Whether to include the ROI centroids on the PlaneSegmentation table.
        If there are a very large number of ROIs (such as in whole-brain recordings), you may wish to disable this for
        faster write speeds.
    include_roi_acceptance : bool, default: True
        Whether to include if the detected ROI was 'accepted' or 'rejected'.
        If there are a very large number of ROIs (such as in whole-brain recordings), you may wish to disable this for
        faster write speeds.
    mask_type : {"image", "pixel", "voxel"}, default: "image"
        There are three types of ROI masks in NWB, 'image', 'pixel', and 'voxel'.

        * 'image' masks have the same shape as the reference images the segmentation was applied to, and weight each pixel
          by its contribution to the ROI (typically boolean, with 0 meaning 'not in the ROI').
        * 'pixel' masks are instead indexed by ROI, with the data at each index being the shape of the image by the number
          of pixels in each ROI.
        * 'voxel' masks are instead indexed by ROI, with the data at each index being the shape of the volume by the number
          of voxels in each ROI.

        Specify your choice between these two as mask_type='image', 'pixel', 'voxel'
    iterator_options : dict, optional
        A dictionary with options for the internal iterators that process the data.
    backend : {"hdf5", "zarr"}, optional
        The type of backend to use when writing the file.
        If a ``backend_configuration`` is not specified, the default type will be "hdf5".
        If a ``backend_configuration`` is specified, then the type will be auto-detected.
    backend_configuration : HDF5BackendConfiguration or ZarrBackendConfiguration, optional
        The configuration model to use when configuring the datasets for this backend.
    append_on_disk_nwbfile : bool, default: False
        Whether to append to an existing NWBFile on disk. If True, the ``nwbfile`` parameter must be None.

    Returns
    -------
    NWBFile or None
        The NWBFile object when writing a new file or using an in-memory nwbfile.
        Returns None when appending to an existing file on disk (append_on_disk_nwbfile=True).
        **Deprecated**: Returning NWBFile in append mode is deprecated and will return None on or after June 2026.
    """
    iterator_options = iterator_options or dict()

    # Parse metadata correctly considering the MultiSegmentationExtractor function:
    if isinstance(segmentation_extractor, MultiSegmentationExtractor):
        segmentation_extractors = segmentation_extractor.segmentations
        if metadata is not None:
            assert isinstance(
                metadata, list
            ), "For MultiSegmentationExtractor enter 'metadata' as a list of SegmentationExtractor metadata"
            assert len(metadata) == len(segmentation_extractor), (
                "The 'metadata' argument should be a list with the same "
                "number of elements as the segmentations in the "
                "MultiSegmentationExtractor"
            )
    else:
        segmentation_extractors = [segmentation_extractor]
        if metadata is not None and not isinstance(metadata, list):
            metadata = [metadata]

    metadata_base_list = [get_nwb_segmentation_metadata(seg_extractor) for seg_extractor in segmentation_extractors]

    # Updating base metadata with new:
    for num, data in enumerate(metadata_base_list):
        metadata_input = metadata[num] if metadata else {}
        metadata_base_list[num] = dict_deep_update(metadata_base_list[num], metadata_input, append_list=False)
    metadata_base_common = metadata_base_list[0]

    # Handle deprecated usage without nwbfile_path
    if nwbfile_path is None:
        warnings.warn(
            "Using 'write_segmentation_to_nwbfile' without 'nwbfile_path' to only add data to an in-memory nwbfile "
            "is deprecated and will be removed on or after June 2026. Use 'add_segmentation_to_nwbfile' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if nwbfile is None:
            raise ValueError(
                "Either 'nwbfile_path' or 'nwbfile' must be provided. "
                "To add data to an in-memory nwbfile, use 'add_segmentation_to_nwbfile' instead."
            )
        _ = get_module(nwbfile=nwbfile, name="ophys", description="contains optical physiology processed data")
        for seg_extractor, seg_metadata in zip(segmentation_extractors, metadata_base_list):
            add_segmentation_to_nwbfile(
                segmentation_extractor=seg_extractor,
                nwbfile=nwbfile,
                metadata=seg_metadata,
                include_background_segmentation=include_background_segmentation,
                include_roi_centroids=include_roi_centroids,
                include_roi_acceptance=include_roi_acceptance,
                mask_type=mask_type,
                iterator_options=iterator_options,
            )
        return nwbfile

    appending_to_in_memory_nwbfile = nwbfile is not None
    file_initially_exists = nwbfile_path.exists()
    allowed_to_modify_existing = overwrite or append_on_disk_nwbfile

    if file_initially_exists and not allowed_to_modify_existing:
        raise FileExistsError(
            f"The file at '{nwbfile_path}' already exists. Set overwrite=True to overwrite the existing file "
            "or append_on_disk_nwbfile=True to append to the existing file."
        )

    if append_on_disk_nwbfile and appending_to_in_memory_nwbfile:
        raise ValueError(
            "Cannot append to an existing file on disk while also providing an in-memory NWBFile. "
            "Either set append_on_disk_nwbfile=False to write the in-memory NWBFile to disk, "
            "or remove the nwbfile parameter to append to the existing file on disk."
        )

    # Resolve backend
    backend = _resolve_backend(backend=backend, backend_configuration=backend_configuration)

    # Determine if we're writing a new file or appending
    writing_new_file = not append_on_disk_nwbfile

    if writing_new_file:
        # Writing mode: create or use provided nwbfile and write
        if nwbfile is None:
            nwbfile = make_nwbfile_from_metadata(metadata=metadata_base_common)

        _ = get_module(nwbfile=nwbfile, name="ophys", description="contains optical physiology processed data")
        for seg_extractor, seg_metadata in zip(segmentation_extractors, metadata_base_list):
            add_segmentation_to_nwbfile(
                segmentation_extractor=seg_extractor,
                nwbfile=nwbfile,
                metadata=seg_metadata,
                include_background_segmentation=include_background_segmentation,
                include_roi_centroids=include_roi_centroids,
                include_roi_acceptance=include_roi_acceptance,
                mask_type=mask_type,
                iterator_options=iterator_options,
            )

        if backend_configuration is None:
            backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)

        configure_and_write_nwbfile(
            nwbfile=nwbfile,
            nwbfile_path=nwbfile_path,
            backend=backend,
            backend_configuration=backend_configuration,
        )

        if verbose:
            print(f"NWB file saved at {nwbfile_path}!")

        return nwbfile

    else:
        # Append mode: read existing file, add data, write back
        warnings.warn(
            "Returning an NWBFile object when using append_on_disk_nwbfile=True is deprecated "
            "and will return None on or after June 2026.",
            DeprecationWarning,
            stacklevel=2,
        )

        IO = BACKEND_NWB_IO[backend]

        with IO(path=str(nwbfile_path), mode="r+", load_namespaces=True) as io:
            nwbfile = io.read()

            _ = get_module(nwbfile=nwbfile, name="ophys", description="contains optical physiology processed data")
            for seg_extractor, seg_metadata in zip(segmentation_extractors, metadata_base_list):
                add_segmentation_to_nwbfile(
                    segmentation_extractor=seg_extractor,
                    nwbfile=nwbfile,
                    metadata=seg_metadata,
                    include_background_segmentation=include_background_segmentation,
                    include_roi_centroids=include_roi_centroids,
                    include_roi_acceptance=include_roi_acceptance,
                    mask_type=mask_type,
                    iterator_options=iterator_options,
                )

            if backend_configuration is None:
                backend_configuration = get_default_backend_configuration(nwbfile=nwbfile, backend=backend)

            configure_backend(nwbfile=nwbfile, backend_configuration=backend_configuration)

            io.write(nwbfile)

        if verbose:
            print(f"NWB file saved at {nwbfile_path}!")

        return nwbfile
