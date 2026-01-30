import math
import warnings
from collections import defaultdict
from typing import Literal

import numpy as np
import psutil

# from hdmf.common import VectorData
from hdmf.data_utils import DataChunkIterator
from pydantic import FilePath
from pynwb import NWBFile
from pynwb.base import Images
from pynwb.image import GrayscaleImage
from pynwb.ophys import (
    DfOverF,
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
    _resolve_backend,
    configure_and_write_nwbfile,
)
from ...utils import (
    DeepDict,
    calculate_regular_series_rate,
    dict_deep_update,
)
from ...utils.str_utils import human_readable_size


def _get_default_ophys_metadata():
    """
    Returns fresh ophys default metadata dictionary.

    Single source of truth for all ophys default metadata.
    Each call returns a new instance to prevent accidental mutation of global state.

    Structure (dictionary-based with single default key):
    -----------------------------------------------------
    All default entries use "default_metadata_key" as the dictionary key.
    This provides a consistent fallback when user-provided metadata is missing.

    metadata["Devices"] = {
        "default_metadata_key": {"name": "Microscope", ...}
    }
    metadata["Ophys"] = {
        "ImagingPlanes": {
            "default_metadata_key": {
                "name": "ImagingPlane",
                "device_metadata_key": "default_metadata_key",
                ...
            }
        },
        "MicroscopySeries": {
            "default_metadata_key": {...}
        },
        "PlaneSegmentations": {
            "default_metadata_key": {...}
        },
        "RoiResponses": {
            "default_metadata_key": {
                "raw": {...}, "dff": {...}, ...
            }
        },
        "SegmentationImages": {...}
    }
    """
    metadata = get_default_nwbfile_metadata()

    default_metadata_key = "default_metadata_key"

    # Top-level Devices dictionary (modality-agnostic)
    metadata["Devices"] = {default_metadata_key: {"name": "Microscope"}}

    metadata["Ophys"] = {
        # ImagingPlanes: dictionary keyed by metadata_key
        "ImagingPlanes": {
            default_metadata_key: {
                "name": "ImagingPlane",
                "description": "The plane or volume being imaged by the microscope.",
                "excitation_lambda": np.nan,
                "indicator": "unknown",
                "location": "unknown",
                "device_metadata_key": default_metadata_key,
                "optical_channel": [
                    {
                        "name": "OpticalChannel",
                        "emission_lambda": np.nan,
                        "description": "An optical channel of the microscope.",
                    }
                ],
            }
        },
        # MicroscopySeries: dictionary keyed by metadata_key (unified for one/two photon)
        "MicroscopySeries": {
            default_metadata_key: {
                "name": "MicroscopySeries",
                "description": "Imaging data from excitation microscopy.",
                "unit": "n.a.",
                "imaging_plane_metadata_key": default_metadata_key,
            }
        },
        # PlaneSegmentations: dictionary keyed by metadata_key
        "PlaneSegmentations": {
            default_metadata_key: {
                "name": "PlaneSegmentation",
                "description": "Segmented ROIs",
                "imaging_plane_metadata_key": default_metadata_key,
            },
        },
        # RoiResponses: dictionary keyed by metadata_key
        # Contains trace metadata organized by trace type (raw, dff, etc.)
        "RoiResponses": {
            default_metadata_key: {
                "raw": {
                    "name": "RoiResponseSeries",
                    "description": "Array of raw fluorescence traces.",
                    "unit": "n.a.",
                },
                "deconvolved": {
                    "name": "Deconvolved",
                    "description": "Array of deconvolved traces.",
                    "unit": "n.a.",
                },
                "neuropil": {
                    "name": "Neuropil",
                    "description": "Array of neuropil traces.",
                    "unit": "n.a.",
                },
                "denoised": {
                    "name": "Denoised",
                    "description": "Array of denoised traces.",
                    "unit": "n.a.",
                },
                "baseline": {
                    "name": "Baseline",
                    "description": "Array of baseline traces.",
                    "unit": "n.a.",
                },
                "background": {
                    "name": "Background",
                    "description": "Array of background traces.",
                    "unit": "n.a.",
                },
                "dff": {
                    "name": "DfOverFSeries",
                    "description": "Array of df/F traces.",
                    "unit": "n.a.",
                },
            },
        },
        # SegmentationImages: keyed by metadata_key
        "SegmentationImages": {
            "name": "SegmentationImages",
            "description": "The summary images of the segmentation.",
            default_metadata_key: {
                "correlation": {
                    "name": "correlation",
                    "description": "The correlation image.",
                },
                "mean": {
                    "name": "mean",
                    "description": "The mean image.",
                },
            },
        },
    }

    return metadata


def _get_default_segmentation_metadata() -> DeepDict:
    """Fill default metadata for segmentation using _get_default_ophys_metadata()."""
    from neuroconv.tools.nwb_helpers import get_default_nwbfile_metadata

    # Start with base NWB metadata
    metadata = get_default_nwbfile_metadata()

    # Get fresh ophys defaults and add to metadata
    ophys_defaults = _get_default_ophys_metadata()

    # Include top-level Devices
    metadata["Devices"] = ophys_defaults["Devices"]

    # Include only segmentation-relevant ophys components
    metadata["Ophys"] = {
        "ImagingPlanes": ophys_defaults["Ophys"]["ImagingPlanes"],
        "PlaneSegmentations": ophys_defaults["Ophys"]["PlaneSegmentations"],
        "RoiResponses": ophys_defaults["Ophys"]["RoiResponses"],
        "SegmentationImages": ophys_defaults["Ophys"]["SegmentationImages"],
    }

    return metadata


def get_nwb_imaging_metadata(
    imgextractor: ImagingExtractor,
    metadata_key: str = "default",
) -> dict:
    """
    Extract provenance metadata from the ImagingExtractor.

    This function returns only data that can be extracted from the source,
    following the provenance-first principle. Defaults are not included here;
    they are applied at NWB object creation time using the default metadata.

    Parameters
    ----------
    imgextractor : ImagingExtractor
        The imaging extractor to get metadata from.
    metadata_key : str, default: "default"
        The key to use for this imaging data in the metadata dictionaries.
        This key is used directly (e.g., "visual_cortex" becomes the key in
        metadata["Ophys"]["MicroscopySeries"]["visual_cortex"]).

    Returns
    -------
    dict
        Dictionary containing only source-extracted metadata for this interface,
        keyed by the provided metadata_key.
    """
    # Get channel names from extractor (provenance data)
    channel_name_list = imgextractor.get_channel_names() or []

    # Build optical channels from extractor data
    optical_channels = []
    for channel_name in channel_name_list:
        optical_channel = {
            "name": channel_name,
            "description": "An optical channel of the microscope.",
        }
        optical_channels.append(optical_channel)

    # Build metadata structure with provenance data only
    metadata = get_default_nwbfile_metadata()

    # Only include imaging plane if we have channel data
    imaging_plane_metadata = {}
    if optical_channels:
        imaging_plane_metadata["optical_channel"] = optical_channels

    # Microscopy series with source-extracted data
    microscopy_series_metadata = {
        "dimension": list(imgextractor.get_sample_shape()),
    }

    # Add rate if available from extractor
    sampling_frequency = imgextractor.get_sampling_frequency()
    if sampling_frequency is not None:
        microscopy_series_metadata["rate"] = float(sampling_frequency)

    # Build the metadata structure using the metadata_key directly
    metadata["Ophys"] = {
        "ImagingPlanes": {metadata_key: imaging_plane_metadata} if imaging_plane_metadata else {},
        "MicroscopySeries": {metadata_key: microscopy_series_metadata},
    }

    return metadata


def add_devices_to_nwbfile(nwbfile: NWBFile, metadata: dict | None = None) -> NWBFile:
    """
    Add optical physiology devices from metadata.

    This function uses the new dictionary-based Devices structure where devices
    are stored at the top level of metadata, keyed by their metadata_key:

        metadata["Devices"] = {
            "device_key": {"name": "MyDevice", "description": "..."},
            ...
        }

    Parameters
    ----------
    nwbfile : NWBFile
        The NWB file to add devices to.
    metadata : dict, optional
        Metadata dictionary with top-level 'Devices' key.
        If not provided, uses default ophys metadata.

    Returns
    -------
    NWBFile
        The NWBFile with devices added.
    """
    from ..nwb_helpers._metadata_and_file_helpers import (
        add_devices_to_nwbfile as _add_devices_to_nwbfile,
    )

    # Get device metadata from user or use defaults
    # Create a working copy to avoid mutating the original metadata
    working_metadata = dict(metadata or {})

    if "Devices" not in working_metadata:
        default_metadata = _get_default_ophys_metadata()
        working_metadata["Devices"] = default_metadata["Devices"]

    _add_devices_to_nwbfile(nwbfile=nwbfile, metadata=working_metadata)

    return nwbfile


def _add_imaging_plane_to_nwbfile(
    nwbfile: NWBFile,
    metadata: dict,
    imaging_plane_metadata_key: str | None = None,
) -> NWBFile:
    """
    Private implementation. Adds the imaging plane specified by the metadata to the nwb file.

    Uses the new dictionary-based structure where imaging planes are stored in:
    metadata["Ophys"]["ImagingPlanes"][metadata_key]

    Parameters
    ----------
    nwbfile : NWBFile
        An previously defined -in memory- NWBFile.
    metadata : dict
        The metadata in the neuroconv format. See `_get_default_ophys_metadata()` for an example.
    imaging_plane_metadata_key : str, optional
        The metadata key of the imaging plane to be added. If None, uses the default imaging plane.

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the imaging plane added.
    """
    default_metadata = _get_default_ophys_metadata()
    default_metadata_key = "default_metadata_key"
    default_imaging_plane = default_metadata["Ophys"]["ImagingPlanes"][default_metadata_key]

    # Determine which metadata key to use
    metadata_key = imaging_plane_metadata_key or default_metadata_key

    # Add devices first
    add_devices_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    # Get imaging planes dictionary from metadata
    imaging_planes = metadata.get("Ophys", {}).get("ImagingPlanes", {})

    if metadata_key in imaging_planes:
        # User provided metadata for this key
        imaging_plane_kwargs = dict(imaging_planes[metadata_key])

        # Fill in any missing required fields with defaults
        required_fields = [
            "name",
            "excitation_lambda",
            "indicator",
            "location",
            "device_metadata_key",
            "optical_channel",
        ]
        for field in required_fields:
            if field not in imaging_plane_kwargs:
                imaging_plane_kwargs[field] = default_imaging_plane[field]
    else:
        # Use defaults
        imaging_plane_kwargs = default_imaging_plane.copy()

    imaging_plane_name = imaging_plane_kwargs["name"]

    # Skip if imaging plane already exists
    if imaging_plane_name in nwbfile.imaging_planes:
        return nwbfile

    # Resolve device_metadata_key to actual device name and object
    device_metadata_key = imaging_plane_kwargs.pop("device_metadata_key", None)

    if device_metadata_key is not None:
        # Look up device name from Devices metadata
        devices_metadata = metadata.get("Devices", {})
        if device_metadata_key in devices_metadata:
            device_name = devices_metadata[device_metadata_key].get("name", device_metadata_key)
        else:
            # Fall back to default device
            default_device_info = default_metadata["Devices"][default_metadata_key]
            device_name = default_device_info["name"]
            # Ensure the default device is added to the nwbfile
            if device_name not in nwbfile.devices:
                nwbfile.create_device(**default_device_info)
    else:
        # Legacy support: if "device" is provided directly as a string
        device_name = imaging_plane_kwargs.pop("device", "Microscope")
        # Ensure the device exists
        if device_name not in nwbfile.devices:
            nwbfile.create_device(name=device_name)

    imaging_plane_kwargs["device"] = nwbfile.devices[device_name]

    # Convert optical channel metadata dicts to OpticalChannel objects
    imaging_plane_kwargs["optical_channel"] = [
        OpticalChannel(**channel_metadata) for channel_metadata in imaging_plane_kwargs["optical_channel"]
    ]

    imaging_plane = ImagingPlane(**imaging_plane_kwargs)
    nwbfile.add_imaging_plane(imaging_plane)

    return nwbfile


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
        imaging_plane_kwargs = dict(metadata_found)

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


def _add_image_segmentation_to_nwbfile(nwbfile: NWBFile, metadata: dict) -> NWBFile:
    """
    Private implementation. Adds the image segmentation container to the nwb file.

    Parameters
    ----------
    nwbfile : NWBFile
        The nwbfile to add the image segmentation to.
    metadata: dict
        The metadata in the neuroconv format. See `_get_default_segmentation_metadata()` for an example.

    Returns
    -------
    NWBFile
        The NWBFile passed as an input with the image segmentation added.
    """
    # Default name for ImageSegmentation container
    default_name = "ImageSegmentation"

    # Allow users to override the name via metadata if needed
    image_segmentation_name = metadata.get("Ophys", {}).get("ImageSegmentation", {}).get("name", default_name)

    ophys = get_module(nwbfile, "ophys", description="contains optical physiology processed data")

    # Add ImageSegmentation container if it doesn't already exist
    if image_segmentation_name not in ophys.data_interfaces:
        ophys.add(ImageSegmentation(name=image_segmentation_name))

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

    # Delegate to private implementation
    return _add_image_segmentation_to_nwbfile(nwbfile=nwbfile, metadata=metadata)


def _add_photon_series_to_nwbfile(
    imaging: ImagingExtractor,
    nwbfile: NWBFile,
    metadata: dict | None = None,
    photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "TwoPhotonSeries",
    microscopy_series_metadata_key: str | None = None,
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

    Uses the new dictionary-based MicroscopySeries structure:
    metadata["Ophys"]["MicroscopySeries"][metadata_key]

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
    microscopy_series_metadata_key: str, optional
        The metadata key for the microscopy series in metadata["Ophys"]["MicroscopySeries"].
        If None, uses default.
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

    # Get defaults
    default_metadata = _get_default_ophys_metadata()
    default_metadata_key = "default_metadata_key"
    default_series = default_metadata["Ophys"]["MicroscopySeries"][default_metadata_key]

    # Determine which metadata key to use
    series_key = microscopy_series_metadata_key or default_metadata_key

    # Get microscopy series metadata from user or build defaults
    microscopy_series = metadata.get("Ophys", {}).get("MicroscopySeries", {})

    if series_key in microscopy_series:
        # User provided metadata for this key
        photon_series_kwargs = dict(microscopy_series[series_key])

        # Fill missing required fields with defaults
        required_fields = ["name", "description", "unit", "imaging_plane_metadata_key"]
        for field in required_fields:
            if field not in photon_series_kwargs:
                photon_series_kwargs[field] = default_series[field]
    else:
        # Use defaults
        photon_series_kwargs = dict(default_series)

    # Resolve imaging_plane_metadata_key to actual imaging plane
    imaging_plane_metadata_key = photon_series_kwargs.pop("imaging_plane_metadata_key", default_metadata_key)

    # Add imaging plane
    _add_imaging_plane_to_nwbfile(
        nwbfile=nwbfile,
        metadata=metadata,
        imaging_plane_metadata_key=imaging_plane_metadata_key,
    )

    # Get the imaging plane name from metadata
    imaging_planes = metadata.get("Ophys", {}).get("ImagingPlanes", {})
    if imaging_plane_metadata_key in imaging_planes:
        imaging_plane_name = imaging_planes[imaging_plane_metadata_key].get("name", "ImagingPlane")
    else:
        imaging_plane_name = default_metadata["Ophys"]["ImagingPlanes"][default_metadata_key]["name"]

    imaging_plane = nwbfile.get_imaging_plane(name=imaging_plane_name)
    photon_series_kwargs["imaging_plane"] = imaging_plane

    # Add dimension: respect user-provided metadata, else derive from extractor
    if "dimension" not in photon_series_kwargs:
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
        # Remove rate/starting_time if present since timestamps are exclusive
        photon_series_kwargs.pop("rate", None)
        photon_series_kwargs.pop("starting_time", None)
    else:
        imaging_has_timestamps = imaging.has_time_vector()
        if imaging_has_timestamps:
            timestamps = imaging.get_timestamps()
            estimated_rate = calculate_regular_series_rate(series=timestamps)
            starting_time = timestamps[0]
        else:
            estimated_rate = float(imaging.get_sampling_frequency())
            starting_time = 0.0

        if estimated_rate:
            photon_series_kwargs.update(rate=estimated_rate, starting_time=starting_time)
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
        photon_series_kwargs = dict(user_photon_series_metadata)
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
        # Remove rate/starting_time if present since timestamps are exclusive
        photon_series_kwargs.pop("rate", None)
        photon_series_kwargs.pop("starting_time", None)
    else:
        imaging_has_timestamps = imaging.has_time_vector()
        if imaging_has_timestamps:
            timestamps = imaging.get_timestamps()
            estimated_rate = calculate_regular_series_rate(series=timestamps)
            starting_time = timestamps[0]
        else:
            estimated_rate = float(imaging.get_sampling_frequency())
            starting_time = 0.0

        if estimated_rate:
            photon_series_kwargs.update(rate=estimated_rate, starting_time=starting_time)
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
        Note: 'v1' is deprecated and will be removed on or after March 2026.
    iterator_options : dict, optional
        Options for controlling the iterative write process. See the
        `pynwb tutorial on iterative write <https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/plot_iterative_write.html#sphx-glr-tutorials-advanced-io-plot-iterative-write-py>`_
        for more information on chunked data writing.

    Returns
    -------
    iterator
        The frames of the imaging extractor wrapped in an iterator for chunked writing.
    """

    def data_generator(imaging):
        num_samples = imaging.get_num_samples()
        for i in range(num_samples):
            yield imaging.get_series(start_sample=i, end_sample=i + 1).squeeze().T

    assert iterator_type in ["v1", "v2", None], "'iterator_type' must be either 'v2' (recommended) or None."
    iterator_options = dict() if iterator_options is None else iterator_options

    if iterator_type is None:
        _check_if_imaging_fits_into_memory(imaging=imaging)
        return imaging.get_series().transpose((0, 2, 1))

    if iterator_type == "v1":
        warnings.warn(
            "iterator_type='v1' is deprecated and will be removed on or after March 2026. "
            "Use iterator_type='v2' for better chunking control and progress bar support.",
            FutureWarning,
            stacklevel=2,
        )
        if "buffer_size" not in iterator_options:
            iterator_options.update(buffer_size=10)
        return DataChunkIterator(data=data_generator(imaging), **iterator_options)

    return ImagingExtractorDataChunkIterator(imaging_extractor=imaging, **iterator_options)


def add_imaging_to_nwbfile(
    imaging: ImagingExtractor,
    nwbfile: NWBFile,
    metadata: dict | None = None,
    photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "TwoPhotonSeries",
    microscopy_series_metadata_key: str | None = None,
    iterator_type: str | None = "v2",
    iterator_options: dict | None = None,
    parent_container: Literal["acquisition", "processing/ophys"] = "acquisition",
    always_write_timestamps: bool = False,
) -> NWBFile:
    """
    Add imaging data from an ImagingExtractor object to an NWBFile.

    Uses the new dictionary-based metadata structure:
    - metadata["Devices"] for device information
    - metadata["Ophys"]["ImagingPlanes"] for imaging plane information
    - metadata["Ophys"]["MicroscopySeries"] for microscopy series information

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
    microscopy_series_metadata_key : str, optional
        The metadata key to use for looking up the microscopy series in
        metadata["Ophys"]["MicroscopySeries"]. If None, uses default.
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

    Returns
    -------
    NWBFile
        The NWB file with the imaging data added

    """
    add_devices_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
    nwbfile = _add_photon_series_to_nwbfile(
        imaging=imaging,
        nwbfile=nwbfile,
        metadata=metadata,
        photon_series_type=photon_series_type,
        microscopy_series_metadata_key=microscopy_series_metadata_key,
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
        Note: 'v1' is deprecated and will be removed on or after March 2026.
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


def get_nwb_segmentation_metadata(
    sgmextractor: SegmentationExtractor,
    metadata_key: str = "default",
) -> dict:
    """
    Extract provenance metadata from the SegmentationExtractor.

    This function returns only data that can be extracted from the source,
    following the provenance-first principle. Defaults are not included here;
    they are applied at NWB object creation time using the default metadata.

    Parameters
    ----------
    sgmextractor : SegmentationExtractor
        The segmentation extractor to get metadata from.
    metadata_key : str, default: "default"
        The key to use for this segmentation data in the metadata dictionaries.
        This key is used directly (e.g., "suite2p" becomes the key in
        metadata["Ophys"]["PlaneSegmentations"]["suite2p"]).

    Returns
    -------
    dict
        Dictionary containing only source-extracted metadata for this interface,
        keyed by the provided metadata_key.
    """
    from neuroconv.tools.nwb_helpers import get_default_nwbfile_metadata

    # Get channel names from extractor (provenance data)
    channel_name_list = sgmextractor.get_channel_names() or []

    # Build optical channels from extractor data
    optical_channels = []
    for channel_name in channel_name_list:
        optical_channel = {
            "name": channel_name,
            "description": "An optical channel of the microscope.",
        }
        optical_channels.append(optical_channel)

    # Build metadata structure with provenance data only
    metadata = get_default_nwbfile_metadata()

    # Only include imaging plane if we have channel data
    imaging_plane_metadata = {}
    if optical_channels:
        imaging_plane_metadata["optical_channel"] = optical_channels

    # Plane segmentation metadata (provenance only - no defaults)
    plane_segmentation_metadata = {}

    # ROI responses - extract trace types that exist in the extractor
    roi_responses_metadata = {}
    for trace_name, trace_data in sgmextractor.get_traces_dict().items():
        if trace_data is not None and len(trace_data.shape) != 0:
            # Only include trace types that have data
            roi_responses_metadata[trace_name] = {}

    # Segmentation images - check what summary images exist
    segmentation_images_metadata = {}
    images_dict = sgmextractor.get_images_dict()
    if images_dict:
        for image_name, image_data in images_dict.items():
            if image_data is not None and len(image_data.shape) != 0:
                segmentation_images_metadata[image_name] = {}

    # Build the metadata structure using the metadata_key directly
    metadata["Ophys"] = {
        "ImagingPlanes": {metadata_key: imaging_plane_metadata} if imaging_plane_metadata else {},
        "PlaneSegmentations": {metadata_key: plane_segmentation_metadata},
        "RoiResponses": {metadata_key: roi_responses_metadata} if roi_responses_metadata else {},
        "SegmentationImages": {metadata_key: segmentation_images_metadata} if segmentation_images_metadata else {},
    }

    return metadata


def _add_plane_segmentation_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict | None,
    plane_segmentation_metadata_key: str | None = None,
    include_roi_centroids: bool = True,
    include_roi_acceptance: bool = True,
    mask_type: Literal["image", "pixel", "voxel"] = "image",
    iterator_options: dict | None = None,
) -> NWBFile:
    """
    Private implementation. Adds the plane segmentation specified by the metadata to the image segmentation.

    Uses the new dictionary-based structure:
    metadata["Ophys"]["PlaneSegmentations"][metadata_key]

    If the plane segmentation already exists in the image segmentation, it is not added again.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get the results from.
    nwbfile : NWBFile
        The NWBFile to add the plane segmentation to.
    metadata : dict, optional
        The metadata for the plane segmentation.
    plane_segmentation_metadata_key : str, optional
        The metadata key for the plane segmentation in metadata["Ophys"]["PlaneSegmentations"].
        If None, uses default.
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

        Specify your choice between these two as mask_type='image', 'pixel', 'voxel'.
    iterator_options : dict, optional
        The options to use when iterating over the image masks of the segmentation extractor.

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the plane segmentation added.
    """

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
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_metadata_key=plane_segmentation_metadata_key,
        include_roi_centroids=include_roi_centroids,
        include_roi_acceptance=include_roi_acceptance,
        mask_type=mask_type,
        iterator_options=iterator_options,
        segmentation_extractor_properties=segmentation_extractor_properties,
    )
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


def _add_plane_segmentation(
    background_or_roi_ids: list[int | str],
    image_or_pixel_masks: np.ndarray,
    nwbfile: NWBFile,
    metadata: dict | None,
    plane_segmentation_metadata_key: str | None = None,
    include_roi_centroids: bool = False,
    roi_locations: np.ndarray | None = None,
    include_roi_acceptance: bool = False,
    is_id_accepted: list | None = None,
    is_id_rejected: list | None = None,
    mask_type: Literal["image", "pixel", "voxel"] = "image",
    iterator_options: dict | None = None,
    segmentation_extractor_properties: dict | None = None,
) -> NWBFile:
    """
    Add a plane segmentation to the NWB file using the new dictionary-based structure.

    Uses metadata["Ophys"]["PlaneSegmentations"][metadata_key] for configuration.
    """
    iterator_options = iterator_options or dict()

    # Get defaults from single source of truth
    default_metadata = _get_default_ophys_metadata()
    default_metadata_key = "default_metadata_key"
    default_plane_seg = default_metadata["Ophys"]["PlaneSegmentations"][default_metadata_key]

    # Determine which metadata key to use
    segmentation_key = plane_segmentation_metadata_key or default_metadata_key

    # Get plane segmentations from metadata
    plane_segmentations = metadata.get("Ophys", {}).get("PlaneSegmentations", {})

    if segmentation_key in plane_segmentations:
        # User provided metadata for this key
        plane_segmentation_kwargs = dict(plane_segmentations[segmentation_key])

        # Fill in missing required fields with defaults
        required_fields = ["name", "description", "imaging_plane_metadata_key"]
        for field in required_fields:
            if field not in plane_segmentation_kwargs:
                plane_segmentation_kwargs[field] = default_plane_seg.get(field, None)
    else:
        # Use defaults
        plane_segmentation_kwargs = dict(default_plane_seg)

    plane_segmentation_name = plane_segmentation_kwargs.get("name", "PlaneSegmentation")

    # Add image segmentation container
    _add_image_segmentation_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    ophys_module = get_module(nwbfile, "ophys", description="contains optical physiology processed data")

    # Get the image segmentation name from metadata (may be customized)
    image_segmentation_name = metadata.get("Ophys", {}).get("ImageSegmentation", {}).get("name", "ImageSegmentation")
    image_segmentation = ophys_module[image_segmentation_name]

    # Skip if plane segmentation already exists
    if plane_segmentation_name in image_segmentation.plane_segmentations:
        return nwbfile

    # Resolve imaging_plane_metadata_key to actual imaging plane
    imaging_plane_metadata_key = plane_segmentation_kwargs.pop("imaging_plane_metadata_key", default_metadata_key)

    # Add imaging plane
    _add_imaging_plane_to_nwbfile(
        nwbfile=nwbfile,
        metadata=metadata,
        imaging_plane_metadata_key=imaging_plane_metadata_key,
    )

    # Get the imaging plane name from metadata
    imaging_planes = metadata.get("Ophys", {}).get("ImagingPlanes", {})
    if imaging_plane_metadata_key in imaging_planes:
        imaging_plane_name = imaging_planes[imaging_plane_metadata_key].get("name", "ImagingPlane")
    else:
        imaging_plane_name = default_metadata["Ophys"]["ImagingPlanes"][default_metadata_key]["name"]

    imaging_plane = nwbfile.imaging_planes[imaging_plane_name]
    plane_segmentation_kwargs["imaging_plane"] = imaging_plane

    # Build PlaneSegmentation object
    plane_segmentation = PlaneSegmentation(**plane_segmentation_kwargs)

    roi_names = [str(roi_id) for roi_id in background_or_roi_ids]
    roi_indices = [background_or_roi_ids.index(roi_id) for roi_id in background_or_roi_ids]
    plane_segmentation.add_column(
        name="roi_name",
        description="The unique identifier for each ROI.",
    )

    if mask_type == "image":
        image_mask_array = image_or_pixel_masks.T
        for roi_index, roi_name in zip(roi_indices, roi_names):
            image_mask = image_mask_array[roi_index]
            plane_segmentation.add_roi(**{"id": roi_index, "roi_name": roi_name, "image_mask": image_mask})
    else:  # mask_type is "pixel" or "voxel"
        pixel_masks = image_or_pixel_masks
        num_pixel_dims = pixel_masks[0].shape[1]

        assert num_pixel_dims in [3, 4], (
            "The segmentation extractor returned a pixel mask that is not 3- or 4- dimensional! "
            "Please open a ticket with https://github.com/catalystneuro/roiextractors/issues"
        )
        if mask_type == "pixel" and num_pixel_dims == 4:
            warnings.warn(
                "Specified mask_type='pixel', but ROIExtractors returned 4-dimensional masks. "
                "Using mask_type='voxel' instead."
            )
            mask_type = "voxel"
        if mask_type == "voxel" and num_pixel_dims == 3:
            warnings.warn(
                "Specified mask_type='voxel', but ROIExtractors returned 3-dimensional masks. "
                "Using mask_type='pixel' instead."
            )
            mask_type = "pixel"

        mask_type_kwarg = f"{mask_type}_mask"

        for roi_index, roi_name in zip(roi_indices, roi_names):
            pixel_mask = pixel_masks[roi_index]
            pixel_mask_to_write = [tuple(x) for x in pixel_mask]
            plane_segmentation.add_roi(**{"id": roi_index, "roi_name": roi_name, mask_type_kwarg: pixel_mask_to_write})

    if include_roi_centroids:
        # ROIExtractors uses height x width x (depth), but NWB uses width x height x depth
        plane_segmentation.add_column(
            name="ROICentroids",
            description="The x, y, (z) centroids of each ROI.",
            data=roi_locations,
        )

    if include_roi_acceptance:
        plane_segmentation.add_column(
            name="Accepted",
            description="1 if ROI was accepted or 0 if rejected as a cell during segmentation operation.",
            data=is_id_accepted,
        )
        plane_segmentation.add_column(
            name="Rejected",
            description="1 if ROI was rejected or 0 if accepted as a cell during segmentation operation.",
            data=is_id_rejected,
        )

    default_segmentation_extractor_properties = {
        "snr": "Signal-to-noise ratio for each component",
        "r_values": "Spatial correlation values for each component",
        "cnn_preds": "CNN classifier predictions for component quality",
    }

    # Always add quality metrics if they are available
    if segmentation_extractor_properties:
        for column_name, column_info in segmentation_extractor_properties.items():
            description = default_segmentation_extractor_properties.get(column_name, column_info.get("description", ""))
            plane_segmentation.add_column(name=column_name, description=description, data=column_info["data"])

    image_segmentation.add_plane_segmentation(plane_segmentations=[plane_segmentation])
    return nwbfile


def _add_background_plane_segmentation_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict | None,
    background_plane_segmentation_metadata_key: str | None = None,
    mask_type: Literal["image", "pixel", "voxel"] = "image",
    iterator_options: dict | None = None,
) -> NWBFile:
    """
    Private implementation. Add background plane segmentation data from a SegmentationExtractor object to an NWBFile.

    Uses the new dictionary-based structure:
    metadata["Ophys"]["PlaneSegmentations"][metadata_key]

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The extractor object containing background segmentation data.
    nwbfile : NWBFile
        The NWB file to which the background plane segmentation will be added.
    metadata : dict, optional
        Metadata for the NWBFile, by default None.
    background_plane_segmentation_metadata_key : str, optional
        The metadata key for the background plane segmentation in metadata["Ophys"]["PlaneSegmentations"].
        If None, uses default_background_plane_segmentation_metadata_key.
    mask_type : str,
        Type of mask to use for segmentation; options are "image", "pixel", or "voxel", by default "image".
    iterator_options : dict, optional
        Options for iterating over the segmentation data, by default None.
    Returns
    -------
    NWBFile
        The NWBFile with the added background plane segmentation data.
    """

    # Use the default background key if not provided
    segmentation_key = (
        background_plane_segmentation_metadata_key or "default_background_plane_segmentation_metadata_key"
    )

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
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_metadata_key=segmentation_key,
        mask_type=mask_type,
        iterator_options=iterator_options,
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

    # Map old plane_segmentation_name parameter to new metadata key structure
    # If plane_segmentation_name is provided, use it as the metadata key, otherwise use default
    plane_segmentation_metadata_key = plane_segmentation_name or "default_metadata_key"

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
        plane_segmentation_metadata_key=plane_segmentation_metadata_key,
        iterator_options=iterator_options,
    )
    return nwbfile


def _add_fluorescence_traces_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    traces_to_add: dict,
    background_or_roi_ids: list,
    nwbfile: NWBFile,
    metadata: dict | None,
    plane_segmentation_metadata_key: str | None = None,
    iterator_options: dict | None = None,
):
    """
    Add fluorescence traces to the NWB file using the new RoiResponses structure.

    Uses metadata["Ophys"]["RoiResponses"][metadata_key] for trace configuration.
    DFF traces go to DfOverF container, all other traces go to Fluorescence container.
    """
    iterator_options = iterator_options or dict()

    # Get defaults from single source of truth
    default_metadata = _get_default_ophys_metadata()
    default_metadata_key = "default_metadata_key"

    # Determine which metadata key to use
    segmentation_key = plane_segmentation_metadata_key or default_metadata_key

    # Get RoiResponses metadata from user or use defaults
    user_roi_responses = metadata.get("Ophys", {}).get("RoiResponses", {})
    default_roi_responses = default_metadata["Ophys"]["RoiResponses"]

    # Get trace metadata for this plane segmentation
    user_traces = user_roi_responses.get(segmentation_key, {})
    default_traces = default_roi_responses.get(segmentation_key, {})
    # Fall back to default key if custom key not in defaults
    if not default_traces:
        default_traces = default_roi_responses.get(default_metadata_key, {})

    # Create a reference for ROIs from the plane segmentation
    roi_table_region = _create_roi_table_region(
        segmentation_extractor=segmentation_extractor,
        background_or_roi_ids=background_or_roi_ids,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_metadata_key=segmentation_key,
    )

    # Set up data interfaces - dff goes to DfOverF, others go to Fluorescence
    trace_to_data_interface = defaultdict()
    traces_to_add_to_fluorescence = [trace_name for trace_name in traces_to_add.keys() if trace_name != "dff"]
    if traces_to_add_to_fluorescence:
        fluorescence_data_interface = _get_segmentation_data_interface(
            nwbfile=nwbfile, data_interface_name="Fluorescence"
        )
        trace_to_data_interface.default_factory = lambda: fluorescence_data_interface

    if "dff" in traces_to_add:
        df_over_f_data_interface = _get_segmentation_data_interface(nwbfile=nwbfile, data_interface_name="DfOverF")
        trace_to_data_interface.update(dff=df_over_f_data_interface)

    for trace_name, trace in traces_to_add.items():
        # Decide which data interface to use based on the trace name
        data_interface = trace_to_data_interface[trace_name]

        # Get trace-specific metadata from user or use defaults
        user_trace_metadata = user_traces.get(trace_name)
        default_trace_metadata = default_traces.get(trace_name)

        if user_trace_metadata is None and default_trace_metadata is None:
            raise ValueError(
                f"Metadata for trace '{trace_name}' not found in RoiResponses for segmentation key '{segmentation_key}'."
            )

        # Build roi response series kwargs from user metadata or defaults
        if user_trace_metadata is not None:
            roi_response_series_kwargs = dict(user_trace_metadata)
            # Fill missing required fields with defaults
            required_fields = ["name", "description", "unit"]
            for field in required_fields:
                if field not in roi_response_series_kwargs and default_trace_metadata:
                    roi_response_series_kwargs[field] = default_trace_metadata[field]
        else:
            # Use defaults
            roi_response_series_kwargs = dict(default_trace_metadata)

        if roi_response_series_kwargs["name"] in data_interface.roi_response_series:
            continue

        # Add data and rois
        roi_response_series_kwargs["data"] = SliceableDataChunkIterator(trace, **iterator_options)
        roi_response_series_kwargs["rois"] = roi_table_region

        # Deprecation warning for user-provided rate in metadata
        if user_trace_metadata is not None and "rate" in user_trace_metadata:
            warnings.warn(
                f"Passing 'rate' in metadata for trace '{trace_name}' is deprecated and will be removed on or after March 2026. "
                f"The rate will be automatically calculated from the segmentation extractor's timestamps or sampling frequency.",
                FutureWarning,
                stacklevel=2,
            )

        segmentation_has_timestamps = segmentation_extractor.has_time_vector()
        if segmentation_has_timestamps:
            timestamps = segmentation_extractor.get_timestamps()
            estimated_rate = calculate_regular_series_rate(series=timestamps)
            starting_time = timestamps[0]
        else:
            estimated_rate = float(segmentation_extractor.get_sampling_frequency())
            starting_time = 0.0

        if estimated_rate:
            # Regular timestamps or no timestamps - use rate
            roi_response_series_kwargs["starting_time"] = starting_time
            # Use metadata rate if provided, otherwise use estimated/sampled rate
            if "rate" not in roi_response_series_kwargs:
                roi_response_series_kwargs["rate"] = estimated_rate
        else:
            # Irregular timestamps - use explicit timestamps
            # Remove rate from metadata if present (can't specify both rate and timestamps)
            roi_response_series_kwargs.pop("rate", None)
            roi_response_series_kwargs["timestamps"] = timestamps

        # Build the roi response series
        roi_response_series = RoiResponseSeries(**roi_response_series_kwargs)

        # Add trace to the data interface
        data_interface.add_roi_response_series(roi_response_series)

    return nwbfile


def _create_roi_table_region(
    segmentation_extractor: SegmentationExtractor,
    background_or_roi_ids: list,
    nwbfile: NWBFile,
    metadata: dict,
    plane_segmentation_metadata_key: str | None = None,
):
    """Private method to create ROI table region.

    Uses the new dictionary-based PlaneSegmentations structure.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get the results from.
    nwbfile : NWBFile
        The NWBFile to add the plane segmentation to.
    metadata : dict, optional
        The metadata for the plane segmentation.
    plane_segmentation_metadata_key : str, optional
        The metadata key for the plane segmentation in metadata["Ophys"]["PlaneSegmentations"].
    """
    default_metadata = _get_default_ophys_metadata()
    default_metadata_key = "default_metadata_key"

    # Determine which metadata key to use
    segmentation_key = plane_segmentation_metadata_key or default_metadata_key

    _add_plane_segmentation_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_metadata_key=segmentation_key,
    )

    # Get the plane segmentation name from metadata
    plane_segmentations = metadata.get("Ophys", {}).get("PlaneSegmentations", {})
    if segmentation_key in plane_segmentations:
        plane_segmentation_name = plane_segmentations[segmentation_key].get("name", "PlaneSegmentation")
    else:
        plane_segmentation_name = default_metadata["Ophys"]["PlaneSegmentations"][default_metadata_key]["name"]

    ophys_module = get_module(nwbfile, "ophys", description="contains optical physiology processed data")
    image_segmentation = ophys_module["ImageSegmentation"]

    # Get plane segmentation from the image segmentation
    plane_segmentation = image_segmentation.plane_segmentations[plane_segmentation_name]
    available_roi_names = list(plane_segmentation["roi_name"][:])

    # Create a reference for ROIs from the plane segmentation
    roi_names = [str(roi_id) for roi_id in background_or_roi_ids]
    region = [available_roi_names.index(roi_name) for roi_name in roi_names]

    imaging_plane_name = plane_segmentation.imaging_plane.name
    roi_table_region = plane_segmentation.create_roi_table_region(
        region=region,
        description=f"The ROIs for {imaging_plane_name}.",
    )

    return roi_table_region


def _get_segmentation_data_interface(nwbfile: NWBFile, data_interface_name: str):
    """Private method to get the container for the segmentation data.
    If the container does not exist, it is created."""
    ophys = get_module(nwbfile, "ophys", description="contains optical physiology processed data")

    if data_interface_name in ophys.data_interfaces:
        return ophys.get(data_interface_name)

    if data_interface_name == "DfOverF":
        data_interface = DfOverF(name=data_interface_name)
    else:
        data_interface = Fluorescence(name=data_interface_name)

    # Add the data interface to the ophys module
    ophys.add(data_interface)

    return data_interface


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


def _add_summary_images_to_nwbfile(
    nwbfile: NWBFile,
    segmentation_extractor: SegmentationExtractor,
    metadata: dict | None = None,
    plane_segmentation_metadata_key: str | None = None,
) -> NWBFile:
    """
    Private implementation. Adds summary images (i.e. mean and correlation) to the nwbfile using an image container object pynwb.Image

    Uses metadata["Ophys"]["SegmentationImages"][metadata_key] for image configuration.

    Parameters
    ----------
    nwbfile : NWBFile
        An previously defined -in memory- NWBFile.
    segmentation_extractor : SegmentationExtractor
        A segmentation extractor object from roiextractors.
    metadata: dict, optional
        The metadata for the summary images is located in metadata["Ophys"]["SegmentationImages"].
    plane_segmentation_metadata_key: str, optional
        The metadata key for the plane segmentation that identifies which images to add.

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the summary images added.
    """
    metadata = metadata or dict()

    # Get defaults from single source of truth
    default_metadata = _get_default_ophys_metadata()
    default_metadata_key = "default_metadata_key"
    default_segmentation_images = default_metadata["Ophys"]["SegmentationImages"]

    # Determine which metadata key to use
    segmentation_key = plane_segmentation_metadata_key or default_metadata_key

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

    # Get images metadata for this plane segmentation
    if segmentation_key in user_segmentation_images:
        images_metadata = user_segmentation_images[segmentation_key]
    elif segmentation_key in default_segmentation_images:
        images_metadata = default_segmentation_images[segmentation_key]
    else:
        raise ValueError(
            f"Plane segmentation '{segmentation_key}' not found in metadata['Ophys']['SegmentationImages']"
        )

    for img_name, img in images_to_add.items():
        # Check if image with this name already exists in the collection
        if img_name in image_collection.images:
            continue  # Skip if image already exists

        image_kwargs = dict(name=img_name, data=img.T)
        image_metadata = images_metadata.get(img_name, None)
        if image_metadata is not None:
            image_kwargs.update(image_metadata)

        # Note that nwb uses the conversion width x height (columns, rows) and roiextractors uses the transpose
        image_collection.add_image(GrayscaleImage(**image_kwargs))

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


def add_segmentation_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict | None = None,
    plane_segmentation_metadata_key: str | None = None,
    background_plane_segmentation_metadata_key: str | None = None,
    include_background_segmentation: bool = False,
    include_roi_centroids: bool = True,
    include_roi_acceptance: bool = True,
    mask_type: Literal["image", "pixel", "voxel"] = "image",
    iterator_options: dict | None = None,
) -> NWBFile:
    """
    Add segmentation data from a SegmentationExtractor object to an NWBFile.

    Uses the new dictionary-based metadata structure:
    - metadata["Devices"] for device information
    - metadata["Ophys"]["ImagingPlanes"] for imaging plane information
    - metadata["Ophys"]["PlaneSegmentations"] for plane segmentation information
    - metadata["Ophys"]["RoiResponses"] for fluorescence trace metadata

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The extractor object containing segmentation data.
    nwbfile : NWBFile
        The NWB file where the segmentation data will be added.
    metadata : dict, optional
        Metadata for the NWBFile, by default None.
    plane_segmentation_metadata_key : str, optional
        The metadata key for the plane segmentation in metadata["Ophys"]["PlaneSegmentations"].
        If None, uses default.
    background_plane_segmentation_metadata_key : str, optional
        The metadata key for the background plane segmentation, if any. If None, uses default.
    include_background_segmentation : bool, optional
        If True, includes background plane segmentation, by default False.
    include_roi_centroids : bool, optional
        If True, includes the centroids of the regions of interest (ROIs), by default True.
    include_roi_acceptance : bool, optional
        If True, includes the acceptance status of ROIs, by default True.
    mask_type : str
        Type of mask to use for segmentation; can be either "image" or "pixel", by default "image".
    iterator_options : dict, optional
        Options for iterating over the data, by default None.

    Returns
    -------
    NWBFile
        The NWBFile with the added segmentation data.
    """

    # Add device:
    add_devices_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    # Determine which metadata keys to use
    segmentation_key = plane_segmentation_metadata_key or "default_plane_segmentation_metadata_key"
    background_key = background_plane_segmentation_metadata_key or "default_background_plane_segmentation_metadata_key"

    # Add PlaneSegmentation:
    _add_plane_segmentation_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_metadata_key=segmentation_key,
        include_roi_centroids=include_roi_centroids,
        include_roi_acceptance=include_roi_acceptance,
        mask_type=mask_type,
        iterator_options=iterator_options,
    )
    if include_background_segmentation:
        _add_background_plane_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            background_plane_segmentation_metadata_key=background_key,
            mask_type=mask_type,
            iterator_options=iterator_options,
        )

    # Add fluorescence traces (preprocessing inline to call private function):
    traces_to_add = segmentation_extractor.get_traces_dict()
    # Filter empty data and background traces
    traces_to_add = {
        trace_name: trace for trace_name, trace in traces_to_add.items() if trace is not None and trace.size != 0
    }
    if include_background_segmentation:
        traces_to_add.pop("neuropil", None)
    if traces_to_add:
        roi_ids = segmentation_extractor.get_roi_ids()
        _add_fluorescence_traces_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            traces_to_add=traces_to_add,
            background_or_roi_ids=roi_ids,
            nwbfile=nwbfile,
            metadata=metadata,
            plane_segmentation_metadata_key=segmentation_key,
            iterator_options=iterator_options,
        )

    if include_background_segmentation:
        # Add background fluorescence traces (preprocessing inline to call private function):
        traces_to_add = segmentation_extractor.get_traces_dict()
        # Filter empty data and background traces
        traces_to_add = {
            trace_name: trace
            for trace_name, trace in traces_to_add.items()
            if trace is not None and trace.size != 0 and trace_name == "neuropil"
        }
        if traces_to_add:
            background_ids = segmentation_extractor.get_background_ids()
            _add_fluorescence_traces_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                traces_to_add=traces_to_add,
                background_or_roi_ids=background_ids,
                nwbfile=nwbfile,
                metadata=metadata,
                plane_segmentation_metadata_key=background_key,
                iterator_options=iterator_options,
            )

    # Adding summary images (mean and correlation)
    _add_summary_images_to_nwbfile(
        nwbfile=nwbfile,
        segmentation_extractor=segmentation_extractor,
        metadata=metadata,
        plane_segmentation_metadata_key=segmentation_key,
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
