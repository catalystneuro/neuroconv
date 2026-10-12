"""Old list-based roiextractors functions pending deprecation.

These functions use the old list-based metadata format and are kept for backward
compatibility during the migration to the new dict-based format. They will be
removed once the migration is complete.
"""

import warnings
from typing import Literal

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ophys import (
    ImagingPlane,
    OnePhotonSeries,
    OpticalChannel,
    TwoPhotonSeries,
)
from roiextractors import (
    ImagingExtractor,
    SegmentationExtractor,
)

from ..nwb_helpers import (
    get_default_nwbfile_metadata,
    get_module,
)
from ...utils import (
    DeepDict,
    calculate_regular_series_rate,
)


def _get_default_ophys_metadata_old_metadata_list():
    """
    Returns fresh ophys default metadata dictionary.

    Single source of truth for all ophys default metadata.
    Each call returns a new instance to prevent accidental mutation of global state.
    """
    metadata = get_default_nwbfile_metadata()

    metadata["Ophys"] = {
        "Device": [{"name": "Microscope"}],
        "ImagingPlane": [
            {
                "name": "ImagingPlane",
                "description": "The plane or volume being imaged by the microscope.",
                "excitation_lambda": np.nan,
                "indicator": "unknown",
                "location": "unknown",
                "device": "Microscope",
                "optical_channel": [
                    {
                        "name": "OpticalChannel",
                        "emission_lambda": np.nan,
                        "description": "An optical channel of the microscope.",
                    }
                ],
            }
        ],
        "TwoPhotonSeries": [
            {
                "name": "TwoPhotonSeries",
                "description": "Imaging data from two-photon excitation microscopy.",
                "unit": "n.a.",
                "imaging_plane": "ImagingPlane",
            }
        ],
        "OnePhotonSeries": [
            {
                "name": "OnePhotonSeries",
                "description": "Imaging data from one-photon excitation microscopy.",
                "unit": "n.a.",
                "imaging_plane": "ImagingPlane",
            }
        ],
        "Fluorescence": {
            "name": "Fluorescence",
            "PlaneSegmentation": {
                "raw": {
                    "name": "RoiResponseSeries",
                    "description": "Array of raw fluorescence traces.",
                    "unit": "n.a.",
                },
                "deconvolved": {"name": "Deconvolved", "description": "Array of deconvolved traces.", "unit": "n.a."},
                "neuropil": {"name": "Neuropil", "description": "Array of neuropil traces.", "unit": "n.a."},
                "denoised": {"name": "Denoised", "description": "Array of denoised traces.", "unit": "n.a."},
                "baseline": {"name": "Baseline", "description": "Array of baseline traces.", "unit": "n.a."},
                "background": {"name": "Background", "description": "Array of background traces.", "unit": "n.a."},
            },
            "BackgroundPlaneSegmentation": {
                "neuropil": {"name": "neuropil", "description": "Array of neuropil traces.", "unit": "n.a."}
            },
        },
        "DfOverF": {
            "name": "DfOverF",
            "PlaneSegmentation": {
                "dff": {"name": "RoiResponseSeries", "description": "Array of df/F traces.", "unit": "n.a."}
            },
        },
        "ImageSegmentation": {
            "name": "ImageSegmentation",
            "plane_segmentations": [
                {"name": "PlaneSegmentation", "description": "Segmented ROIs", "imaging_plane": "ImagingPlane"},
                {
                    "name": "BackgroundPlaneSegmentation",
                    "description": "Segmented Background Components",
                    "imaging_plane": "ImagingPlane",
                },
            ],
        },
        "SegmentationImages": {
            "name": "SegmentationImages",
            "description": "The summary images of the segmentation.",
            "PlaneSegmentation": {"correlation": {"name": "correlation", "description": "The correlation image."}},
        },
    }

    return metadata


def _get_default_segmentation_metadata() -> DeepDict:
    """Fill default metadata for segmentation using _get_ophys_metadata_placeholders()."""
    from neuroconv.tools.nwb_helpers import get_default_nwbfile_metadata

    # Start with base NWB metadata
    metadata = get_default_nwbfile_metadata()

    # Get fresh ophys defaults and add to metadata
    ophys_defaults = _get_default_ophys_metadata_old_metadata_list()
    metadata["Ophys"] = {
        "Device": ophys_defaults["Ophys"]["Device"],
        "ImagingPlane": ophys_defaults["Ophys"]["ImagingPlane"],
        "Fluorescence": ophys_defaults["Ophys"]["Fluorescence"],
        "DfOverF": ophys_defaults["Ophys"]["DfOverF"],
        "ImageSegmentation": ophys_defaults["Ophys"]["ImageSegmentation"],
        "SegmentationImages": ophys_defaults["Ophys"]["SegmentationImages"],
    }

    return metadata


def get_nwb_imaging_metadata(
    imgextractor: ImagingExtractor,
    photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
) -> dict:
    """
    Convert metadata from the ImagingExtractor into nwb specific metadata.

    Parameters
    ----------
    imgextractor : ImagingExtractor
        The imaging extractor to get metadata from.
    photon_series_type : {'OnePhotonSeries', 'TwoPhotonSeries'}, optional
        The type of photon series to create metadata for.

    Returns
    -------
    dict
        Dictionary containing metadata for devices, imaging planes, and photon series
        specific to the imaging data.
    """
    # Get fresh ophys defaults
    metadata = _get_default_ophys_metadata_old_metadata_list()

    channel_name_list = ["OpticalChannel"]

    # Update optical channels based on extractor data
    optical_channels = []
    for channel_name in channel_name_list:
        optical_channel = metadata["Ophys"]["ImagingPlane"][0]["optical_channel"][0].copy()
        optical_channel["name"] = channel_name
        optical_channels.append(optical_channel)

    # Update imaging plane with correct optical channels
    metadata["Ophys"]["ImagingPlane"][0]["optical_channel"] = optical_channels

    # Add photon series with dimension from extractor
    photon_series_metadata = metadata["Ophys"][photon_series_type][0].copy()
    photon_series_metadata["dimension"] = list(imgextractor.get_sample_shape())
    metadata["Ophys"][photon_series_type] = [photon_series_metadata]

    # Keep only Device, ImagingPlane, and the specific photon series type
    metadata["Ophys"] = {
        "Device": metadata["Ophys"]["Device"],
        "ImagingPlane": metadata["Ophys"]["ImagingPlane"],
        photon_series_type: metadata["Ophys"][photon_series_type],
    }

    return metadata


def _add_devices_to_nwbfile_old_list_format(nwbfile: NWBFile, metadata: dict | None = None) -> NWBFile:
    """
    Add optical physiology devices from old list-based metadata.

    Private implementation used internally by old list-based functions.
    """
    metadata = metadata or {}
    device_metadata = metadata.get("Ophys", {}).get("Device")

    if device_metadata is None:
        default_metadata = _get_default_ophys_metadata_old_metadata_list()
        device_metadata = default_metadata["Ophys"]["Device"]

    for device in device_metadata:
        if device["name"] not in nwbfile.devices:
            nwbfile.add_device(Device(**device))

    return nwbfile


def add_devices_to_nwbfile(nwbfile: NWBFile, metadata: dict | None = None) -> NWBFile:
    """
    Add optical physiology devices from metadata.

    .. deprecated::
        ``add_devices_to_nwbfile`` is deprecated and will be removed on or after February 2027.
    """
    warnings.warn(
        "add_devices_to_nwbfile is deprecated and will be removed on or after February 2027. "
        "Use _add_device_to_nwbfile with the new dict-based metadata format (metadata['Devices']) instead.",
        FutureWarning,
        stacklevel=2,
    )
    return _add_devices_to_nwbfile_old_list_format(nwbfile=nwbfile, metadata=metadata)


def _add_imaging_plane_to_nwbfile_old_list_format(
    nwbfile: NWBFile,
    metadata: dict,
    imaging_plane_name: str | None = None,
) -> NWBFile:
    """
    Private implementation. Adds the imaging plane specified by the metadata to the nwb file.
    The imaging plane that is added is the one located in metadata["Ophys"]["ImagingPlane"][imaging_plane_index]

    Parameters
    ----------
    nwbfile : NWBFile
        An previously defined -in memory- NWBFile.
    metadata : dict
        The metadata in the neuroconv format. See `_get_ophys_metadata_placeholders()` for an example.
    imaging_plane_name: str, optional
        The name of the imaging plane to be added. If None, this function adds the default imaging plane
        in _get_ophys_metadata_placeholders().

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the imaging plane added.
    """
    default_metadata = _get_default_ophys_metadata_old_metadata_list()
    default_imaging_plane = default_metadata["Ophys"]["ImagingPlane"][0]

    # Track whether user explicitly provided a name
    user_provided_a_name = imaging_plane_name is not None

    imaging_plane_name = imaging_plane_name or default_imaging_plane["name"]

    if imaging_plane_name in nwbfile.imaging_planes:
        return nwbfile

    _add_devices_to_nwbfile_old_list_format(nwbfile=nwbfile, metadata=metadata)

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


def _add_photon_series_to_nwbfile_old_list_format(
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
    Private implementation. Add photon series to NWB file.

    Adds photon series from ImagingExtractor to NWB file object.
    The photon series can be added to the NWB file either as a TwoPhotonSeries
    or OnePhotonSeries object.

    Parameters
    ----------
    imaging : ImagingExtractor
        The imaging extractor to get the data from.
    nwbfile : NWBFile
        The nwbfile to add the photon series to.
    metadata: dict
        The metadata for the photon series.
    photon_series_type: {'OnePhotonSeries', 'TwoPhotonSeries'}, optional
        The type of photon series to add, default is TwoPhotonSeries.
    photon_series_index: int, default: 0
        The metadata for the photon series is a list of the different photon series to add.
        Specify which element of the list with this parameter.
    parent_container: {'acquisition', 'processing/ophys'}, optional
        The container where the photon series is added, default is nwbfile.acquisition.
        When 'processing/ophys' is chosen, the photon series is added to ``nwbfile.processing['ophys']``.
    iterator_type: str, default: 'v2'
        The type of iterator to use when adding the photon series to the NWB file.
    iterator_options: dict, optional
    always_write_timestamps : bool, default: False
        Set to True to always write timestamps.
        By default (False), the function checks if the timestamps are uniformly sampled, and if so, stores the data
        using a regular sampling rate instead of explicit timestamps. If set to True, timestamps will be written
        explicitly, regardless of whether the sampling rate is uniform.

    Returns
    -------
    NWBFile
        The NWBFile passed as an input with the photon series added.
    """
    from .roiextractors import _imaging_frames_to_hdmf_iterator

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
    default_metadata = _get_default_ophys_metadata_old_metadata_list()
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
        required_fields = ["name", "description", "unit", "imaging_plane"]
        for field in required_fields:
            if field not in photon_series_kwargs:
                photon_series_kwargs[field] = default_photon_series[field]
    else:
        # User didn't provide photon series - use all defaults
        photon_series_kwargs = default_photon_series
        imaging_plane_name = None  # Will create default imaging plane

    # Add imaging plane (None signals to create default imaging plane)
    _add_imaging_plane_to_nwbfile_old_list_format(
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


def get_nwb_segmentation_metadata(sgmextractor: SegmentationExtractor) -> dict:
    """
    Convert metadata from the segmentation into nwb specific metadata.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get metadata from.

    Returns
    -------
    dict
        Dictionary containing metadata for devices, imaging planes, image segmentation,
        and fluorescence data specific to the segmentation.
    """
    metadata = _get_default_segmentation_metadata()
    # Optical Channel name:
    channel_names = sgmextractor._channel_names
    for i, ch_name in enumerate(channel_names):
        if i == 0:
            metadata["Ophys"]["ImagingPlane"][0]["optical_channel"][i]["name"] = ch_name
        else:
            metadata["Ophys"]["ImagingPlane"][0]["optical_channel"].append(
                dict(
                    name=ch_name,
                    emission_lambda=np.nan,
                    description=f"{ch_name} description",
                )
            )

    plane_segmentation_name = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]["name"]
    for trace_name, trace_data in sgmextractor.get_traces_dict().items():
        # raw traces have already default name ("RoiResponseSeries")
        if trace_name in ["raw", "dff"]:
            continue
        if trace_data is not None and len(trace_data.shape) != 0:
            metadata["Ophys"]["Fluorescence"][plane_segmentation_name][trace_name] = dict(
                name=trace_name.capitalize(),
                description=f"description of {trace_name} traces",
            )

    return metadata
