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
from pynwb.device import Device
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
from ..nwb_helpers import get_default_nwbfile_metadata, get_module, make_or_load_nwbfile
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
    """Fill default metadata for segmentation using _get_default_ophys_metadata()."""
    from neuroconv.tools.nwb_helpers import get_default_nwbfile_metadata

    # Start with base NWB metadata
    metadata = get_default_nwbfile_metadata()

    # Get fresh ophys defaults and add to metadata
    ophys_defaults = _get_default_ophys_metadata()
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
    metadata = _get_default_ophys_metadata()

    # TODO: get_num_channels is deprecated, remove
    channel_name_list = imgextractor.get_channel_names() or ["OpticalChannel"]

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


def add_devices_to_nwbfile(nwbfile: NWBFile, metadata: dict | None = None) -> NWBFile:
    """
    Add optical physiology devices from metadata.

    Notes
    -----
    The metadata concerning the optical physiology should be stored in ``metadata['Ophys']['Device']``.

    Deprecation: Passing ``pynwb.device.Device`` objects directly inside
    ``metadata['Ophys']['Device']`` is deprecated and will be removed on or after March 2026.
    Please pass device definitions as dictionaries instead (e.g., ``{"name": "Microscope"}``).
    """
    # Get device metadata from user or use defaults
    metadata = metadata or {}
    device_metadata = metadata.get("Ophys", {}).get("Device")

    if device_metadata is None:
        default_metadata = _get_default_ophys_metadata()
        device_metadata = default_metadata["Ophys"]["Device"]

    for device in device_metadata:
        if not isinstance(device, dict):
            warnings.warn(
                "Passing pynwb.device.Device objects in metadata['Ophys']['Device'] is deprecated and will be "
                "removed on or after March 2026. Please pass device definitions as dictionaries instead.",
                FutureWarning,
                stacklevel=2,
            )
        device_name = device["name"] if isinstance(device, dict) else device.name
        if device_name not in nwbfile.devices:
            device = Device(**device) if isinstance(device, dict) else device
            nwbfile.add_device(device)

    return nwbfile


def _add_imaging_plane_to_nwbfile(
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
        The metadata in the neuroconv format. See `_get_default_ophys_metadata()` for an example.
    imaging_plane_name: str, optional
        The name of the imaging plane to be added. If None, this function adds the default imaging plane
        in _get_default_ophys_metadata().

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the imaging plane added.
    """
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
    # Get ImageSegmentation name from metadata or use default
    default_metadata = _get_default_segmentation_metadata()
    default_name = default_metadata["Ophys"]["ImageSegmentation"]["name"]

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


def _add_photon_series_to_nwbfile(
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
        required_fields = ["name", "description", "unit", "imaging_plane"]
        for field in required_fields:
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
    photon_series_index: int = 0,
    iterator_type: str | None = "v2",
    iterator_options: dict | None = None,
    parent_container: Literal["acquisition", "processing/ophys"] = "acquisition",
    always_write_timestamps: bool = False,
) -> NWBFile:
    """
    Add imaging data from an ImagingExtractor object to an NWBFile.

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
    iterator_type: str = "v2",
    iterator_options: dict | None = None,
    photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "TwoPhotonSeries",
):
    """
    Primary method for writing an ImagingExtractor object to an NWBFile.

    Parameters
    ----------
    imaging: ImagingExtractor
        The imaging extractor object to be written to nwb
    nwbfile_path: FilePath
        Path for where to write or load (if overwrite=False) the NWBFile.
        If specified, the context will always write to this location.
    nwbfile: NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling::

            write_recording(recording=my_recording_extractor, nwbfile=my_nwbfile)

        will result in the appropriate changes to the my_nwbfile object.
        If neither 'nwbfile_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
        and returned by the function.
    metadata: dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
    overwrite: bool, optional
        Whether to overwrite the NWBFile if one exists at the nwbfile_path.
        The default is False (append mode).
    verbose: bool, optional
        If 'nwbfile_path' is specified, informs user after a successful write operation.
        The default is True.
    iterator_type: {"v2", None}, default: 'v2'
        The type of iterator for chunked data writing.
        'v2': Uses iterative write with control over chunking and progress bars.
        None: Loads all data into memory before writing (not recommended for large datasets).
        Note: 'v1' is deprecated and will be removed on or after March 2026.
    iterator_options : dict, optional
        Options for controlling the iterative write process. See the
        `pynwb tutorial on iterative write <https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/plot_iterative_write.html#sphx-glr-tutorials-advanced-io-plot-iterative-write-py>`_
        for more information on chunked data writing.
    """
    assert (
        nwbfile_path is None or nwbfile is None
    ), "Either pass a nwbfile_path location, or nwbfile object, but not both!"
    if nwbfile is not None:
        assert isinstance(nwbfile, NWBFile), "'nwbfile' should be of type pynwb.NWBFile"

    iterator_options = iterator_options or dict()

    if metadata is None:
        metadata = dict()
    if hasattr(imaging, "nwb_metadata"):
        metadata = dict_deep_update(imaging.nwb_metadata, metadata, append_list=False)

    with make_or_load_nwbfile(
        nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=verbose
    ) as nwbfile_out:
        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
        )
    return nwbfile_out


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
    for i in range(sgmextractor.get_num_channels()):
        ch_name = sgmextractor.get_channel_names()[i]
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


def _add_plane_segmentation_to_nwbfile(
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
    Private implementation. Adds the plane segmentation specified by the metadata to the image segmentation.

    If the plane segmentation already exists in the image segmentation, it is not added again.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get the results from.
    nwbfile : NWBFile
        The NWBFile to add the plane segmentation to.
    metadata : dict, optional
        The metadata for the plane segmentation.
    plane_segmentation_name : str, optional
        The name of the plane segmentation to be added.
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
    default_plane_segmentation_index: int,
    nwbfile: NWBFile,
    metadata: dict | None,
    plane_segmentation_name: str | None = None,
    include_roi_centroids: bool = False,
    roi_locations: np.ndarray | None = None,
    include_roi_acceptance: bool = False,
    is_id_accepted: list | None = None,
    is_id_rejected: list | None = None,
    mask_type: Literal["image", "pixel", "voxel"] = "image",
    iterator_options: dict | None = None,
    segmentation_extractor_properties: dict | None = None,
) -> NWBFile:
    iterator_options = iterator_options or dict()

    # Get defaults from single source of truth
    default_metadata = _get_default_ophys_metadata()
    default_plane_segmentation = default_metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][
        default_plane_segmentation_index
    ]

    # Add image segmentation container
    default_image_segmentation_name = default_metadata["Ophys"]["ImageSegmentation"]["name"]
    image_segmentation_metadata = metadata.get("Ophys", {}).get("ImageSegmentation", {})
    image_segmentation_name = image_segmentation_metadata.get("name", default_image_segmentation_name)
    _add_image_segmentation_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    ophys_module = get_module(nwbfile, "ophys", description="contains optical physiology processed data")
    image_segmentation = ophys_module[image_segmentation_name]

    # Track whether user explicitly provided a plane segmentation name
    user_provided_plane_segmentation_name = plane_segmentation_name is not None
    plane_segmentation_name = plane_segmentation_name or default_plane_segmentation["name"]

    # Extract plane segmentation metadata from user or use defaults
    user_plane_segmentations_list = image_segmentation_metadata.get("plane_segmentations", [])
    user_plane_segmentation = next(
        (ps for ps in user_plane_segmentations_list if ps["name"] == plane_segmentation_name),
        None,
    )

    if user_provided_plane_segmentation_name and user_plane_segmentation is None:
        # User requested a specific plane segmentation that doesn't exist in metadata
        raise ValueError(
            f"Metadata for Plane Segmentation '{plane_segmentation_name}' not found in metadata['Ophys']['ImageSegmentation']['plane_segmentations']."
        )

    if user_plane_segmentation is not None:
        # User provided plane segmentation use it and fill missing required fields
        plane_segmentation_kwargs = user_plane_segmentation.copy()
        required_fields = ["name", "description", "imaging_plane"]
        for field in required_fields:
            if field not in plane_segmentation_kwargs:
                plane_segmentation_kwargs[field] = default_plane_segmentation[field]
    else:
        # User didn't provide plane segmentation - use defaults
        plane_segmentation_kwargs = default_plane_segmentation

    # Add dependencies (passing unmodified metadata)
    # Check if user provided imaging plane metadata, otherwise use default
    imaging_plane_name_from_plane_seg = plane_segmentation_kwargs["imaging_plane"]
    user_imaging_planes_list = metadata.get("Ophys", {}).get("ImagingPlane", [])
    user_has_imaging_plane = any(
        plane["name"] == imaging_plane_name_from_plane_seg for plane in user_imaging_planes_list
    )

    imaging_plane_name_to_add = imaging_plane_name_from_plane_seg if user_has_imaging_plane else None
    _add_imaging_plane_to_nwbfile(nwbfile=nwbfile, metadata=metadata, imaging_plane_name=imaging_plane_name_to_add)

    if plane_segmentation_name in image_segmentation.plane_segmentations:
        # At the moment, we don't support extending an existing PlaneSegmentation.
        return nwbfile

    # Build PlaneSegmentation object
    imaging_plane = nwbfile.imaging_planes[imaging_plane_name_from_plane_seg]
    plane_segmentation_kwargs["imaging_plane"] = imaging_plane
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


def add_background_plane_segmentation_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict | None,
    background_plane_segmentation_name: str | None = None,
    mask_type: Literal["image", "pixel", "voxel"] = "image",
    iterator_options: dict | None = None,
) -> NWBFile:
    """
    Add background plane segmentation data from a SegmentationExtractor object to an NWBFile.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The extractor object containing background segmentation data.
    nwbfile : NWBFile
        The NWB file to which the background plane segmentation will be added.
    metadata : dict, optional
        Metadata for the NWBFile, by default None.
    background_plane_segmentation_name : str, optional
        The name of the background PlaneSegmentation object to be added, by default None.
    mask_type : str,
        Type of mask to use for segmentation; options are "image", "pixel", or "voxel", by default "image".
    iterator_options : dict, optional
        Options for iterating over the segmentation data, by default None.
    Returns
    -------
    NWBFile
        The NWBFile with the added background plane segmentation data.
    """

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
    Adds the fluorescence traces specified by the metadata to the nwb file.
    The fluorescence traces that are added are the one located in metadata["Ophys"]["Fluorescence"].
    The df/F traces that are added are the one located in metadata["Ophys"]["DfOverF"].

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get the traces from.
    nwbfile : NWBFile
        The nwbfile to add the fluorescence traces to.
    metadata : dict
        The metadata for the fluorescence traces.
    plane_segmentation_name : str, optional
        The name of the plane segmentation that identifies which plane to add the fluorescence traces to.
    include_background_segmentation : bool, default: False
        Whether to include the background plane segmentation and fluorescence traces in the NWB file. If False,
        neuropil traces are included in the main plane segmentation rather than the background plane segmentation.
    iterator_options : dict, optional

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the fluorescence traces added.
    """
    default_plane_segmentation_index = 0

    traces_to_add = segmentation_extractor.get_traces_dict()
    # Filter empty data and background traces
    traces_to_add = {
        trace_name: trace for trace_name, trace in traces_to_add.items() if trace is not None and trace.size != 0
    }
    if include_background_segmentation:
        traces_to_add.pop("neuropil")
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


def _add_fluorescence_traces_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    traces_to_add: dict,
    background_or_roi_ids: list,
    nwbfile: NWBFile,
    metadata: dict | None,
    default_plane_segmentation_index: int,
    plane_segmentation_name: str | None = None,
    iterator_options: dict | None = None,
):
    iterator_options = iterator_options or dict()

    # Get defaults from single source of truth
    default_metadata = _get_default_ophys_metadata()
    default_plane_segmentation_name = default_metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][
        default_plane_segmentation_index
    ]["name"]

    # Determine plane segmentation name for metadata lookup
    plane_segmentation_name_for_lookup = plane_segmentation_name or default_plane_segmentation_name

    # Extract DfOverF metadata from user or use defaults
    default_df_over_f = default_metadata["Ophys"]["DfOverF"]
    user_df_over_f = metadata.get("Ophys", {}).get("DfOverF", {})
    df_over_f_name = user_df_over_f.get("name", default_df_over_f["name"])

    # Extract Fluorescence metadata from user or use defaults
    default_fluorescence = default_metadata["Ophys"]["Fluorescence"]
    user_fluorescence = metadata.get("Ophys", {}).get("Fluorescence", {})
    fluorescence_name = user_fluorescence.get("name", default_fluorescence["name"])

    # Create a reference for ROIs from the plane segmentation (passing unmodified metadata and original plane_segmentation_name)
    roi_table_region = _create_roi_table_region(
        segmentation_extractor=segmentation_extractor,
        background_or_roi_ids=background_or_roi_ids,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_name=plane_segmentation_name,  # Pass original (possibly None) value
    )

    trace_to_data_interface = defaultdict()
    traces_to_add_to_fluorescence_data_interface = [
        trace_name for trace_name in traces_to_add.keys() if trace_name != "dff"
    ]
    if traces_to_add_to_fluorescence_data_interface:
        fluorescence_data_interface = _get_segmentation_data_interface(
            nwbfile=nwbfile, data_interface_name=fluorescence_name
        )
        trace_to_data_interface.default_factory = lambda: fluorescence_data_interface

    if "dff" in traces_to_add:
        df_over_f_data_interface = _get_segmentation_data_interface(nwbfile=nwbfile, data_interface_name=df_over_f_name)
        trace_to_data_interface.update(dff=df_over_f_data_interface)

    for trace_name, trace in traces_to_add.items():
        # Decide which data interface to use based on the trace name
        data_interface = trace_to_data_interface[trace_name]
        is_dff = isinstance(data_interface, DfOverF)

        # Get trace-specific metadata from user or use defaults
        if is_dff:
            user_plane_traces = user_df_over_f.get(plane_segmentation_name_for_lookup, {})
            default_plane_traces = default_df_over_f.get(plane_segmentation_name_for_lookup, {})
            # Fall back to default plane if custom plane not in defaults
            if not default_plane_traces:
                default_plane_traces = default_df_over_f.get(default_plane_segmentation_name, {})
        else:
            user_plane_traces = user_fluorescence.get(plane_segmentation_name_for_lookup, {})
            default_plane_traces = default_fluorescence.get(plane_segmentation_name_for_lookup, {})
            # Fall back to default plane if custom plane not in defaults
            if not default_plane_traces:
                default_plane_traces = default_fluorescence.get(default_plane_segmentation_name, {})

        # Extract trace metadata from user or use defaults
        user_trace_metadata = user_plane_traces.get(trace_name)
        default_trace_metadata = default_plane_traces.get(trace_name)

        if user_trace_metadata is None and default_trace_metadata is None:
            raise ValueError(
                f"Metadata for trace '{trace_name}' not found for plane segmentation '{plane_segmentation_name_for_lookup}' "
                f"in {'DfOverF' if is_dff else 'Fluorescence'} metadata."
            )

        # Build roi response series kwargs from user metadata or defaults
        if user_trace_metadata is not None:
            roi_response_series_kwargs = dict(user_trace_metadata)
            # Fill missing required fields with defaults
            required_fields = ["name", "description", "unit"]
            for field in required_fields:
                if field not in roi_response_series_kwargs:
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
    plane_segmentation_name: str | None = None,
):
    """Private method to create ROI table region.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get the results from.
    nwbfile : NWBFile
        The NWBFile to add the plane segmentation to.
    metadata : dict, optional
        The metadata for the plane segmentation.
    plane_segmentation_name : str, optional
        The name of the plane segmentation that identifies which plane to add the ROI table region to.
    """
    # Get ImageSegmentation name from user metadata or use default
    default_metadata = _get_default_ophys_metadata()

    _add_plane_segmentation_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_name=plane_segmentation_name,
    )

    # Determine the actual plane segmentation name that was added (could be default if None was passed)
    if plane_segmentation_name is None:
        # Use the default PlaneSegmentation name
        plane_segmentation_name = default_metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]["name"]

    ophys_module = get_module(nwbfile, "ophys", description="contains optical physiology processed data")

    default_image_segmentation_name = default_metadata["Ophys"]["ImageSegmentation"]["name"]
    image_segmentation_name = (
        metadata.get("Ophys", {}).get("ImageSegmentation", {}).get("name", default_image_segmentation_name)
    )
    image_segmentation = ophys_module[image_segmentation_name]

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
    Adds the fluorescence traces specified by the metadata to the nwb file.
    The fluorescence traces that are added are the one located in metadata["Ophys"]["Fluorescence"].
    The df/F traces that are added are the one located in metadata["Ophys"]["DfOverF"].

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get the traces from.
    nwbfile : NWBFile
        The nwbfile to add the fluorescence traces to.
    metadata : dict
        The metadata for the fluorescence traces.
    plane_segmentation_name : str, optional
        The name of the plane segmentation that identifies which plane to add the fluorescence traces to.
    iterator_options : dict, optional

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the fluorescence traces added.
    """
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
    Adds summary images (i.e. mean and correlation) to the nwbfile using an image container object pynwb.Image

    Parameters
    ----------
    nwbfile : NWBFile
        An previously defined -in memory- NWBFile.
    segmentation_extractor : SegmentationExtractor
        A segmentation extractor object from roiextractors.
    metadata: dict, optional
        The metadata for the summary images is located in metadata["Ophys"]["SegmentationImages"].
    plane_segmentation_name: str, optional
        The name of the plane segmentation that identifies which images to add.

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the summary images added.
    """
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
    plane_segmentation_name: str | None = None,
    background_plane_segmentation_name: str | None = None,
    include_background_segmentation: bool = False,
    include_roi_centroids: bool = True,
    include_roi_acceptance: bool = True,
    mask_type: Literal["image", "pixel", "voxel"] = "image",
    iterator_options: dict | None = None,
) -> NWBFile:
    """
    Add segmentation data from a SegmentationExtractor object to an NWBFile.

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
    background_plane_segmentation_name : str, optional
        The name of the background PlaneSegmentation, if any, by default None.
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

    # Add PlaneSegmentation:
    _add_plane_segmentation_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_name=plane_segmentation_name,
        include_roi_centroids=include_roi_centroids,
        include_roi_acceptance=include_roi_acceptance,
        mask_type=mask_type,
        iterator_options=iterator_options,
    )
    if include_background_segmentation:
        add_background_plane_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            background_plane_segmentation_name=background_plane_segmentation_name,
            mask_type=mask_type,
            iterator_options=iterator_options,
        )

    # Add fluorescence traces:
    add_fluorescence_traces_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_name=plane_segmentation_name,
        include_background_segmentation=include_background_segmentation,
        iterator_options=iterator_options,
    )

    if include_background_segmentation:
        add_background_fluorescence_traces_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            background_plane_segmentation_name=background_plane_segmentation_name,
            iterator_options=iterator_options,
        )

    # Adding summary images (mean and correlation)
    add_summary_images_to_nwbfile(
        nwbfile=nwbfile,
        segmentation_extractor=segmentation_extractor,
        metadata=metadata,
        plane_segmentation_name=plane_segmentation_name,
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
    iterator_options: dict | None = None,
) -> NWBFile:
    """
    Primary method for writing an SegmentationExtractor object to an NWBFile.

    Parameters
    ----------
    segmentation_extractor: SegmentationExtractor
        The segmentation extractor object to be written to nwb
    nwbfile_path: FilePath
        Path for where to write or load (if overwrite=False) the NWBFile.
        If specified, the context will always write to this location.
    nwbfile: NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling::

            write_segmentation_to_nwbfile(segmentation_extractor=my_segmentation_extractor, nwbfile=my_nwbfile)

        will result in the appropriate changes to the my_nwbfile object.
        If neither 'nwbfile_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
        and returned by the function.
    metadata: dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
    overwrite: bool, default: False
        Whether to overwrite the NWBFile if one exists at the nwbfile_path.
    verbose: bool, default: True
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
    mask_type : str, default: 'image'
        There are three types of ROI masks in NWB, 'image', 'pixel', and 'voxel'.

        * 'image' masks have the same shape as the reference images the segmentation was applied to, and weight each pixel
          by its contribution to the ROI (typically boolean, with 0 meaning 'not in the ROI').
        * 'pixel' masks are instead indexed by ROI, with the data at each index being the shape of the image by the number
          of pixels in each ROI.
        * 'voxel' masks are instead indexed by ROI, with the data at each index being the shape of the volume by the number
          of voxels in each ROI.

        Specify your choice between these two as mask_type='image', 'pixel', 'voxel'
    iterator_options: dict, optional
        A dictionary with options for the internal iterators that process the data.
    """
    assert (
        nwbfile_path is None or nwbfile is None
    ), "Either pass a nwbfile_path location, or nwbfile object, but not both!"

    iterator_options = iterator_options or dict()

    # Parse metadata correctly considering the MultiSegmentationExtractor function:
    if isinstance(segmentation_extractor, MultiSegmentationExtractor):
        segmentation_extractors = segmentation_extractor.segmentations
        if metadata is not None:
            assert isinstance(metadata, list), (
                "For MultiSegmentationExtractor enter 'metadata' as a list of " "SegmentationExtractor metadata"
            )
            assert len(metadata) == len(segmentation_extractor), (
                "The 'metadata' argument should be a list with the same "
                "number of elements as the segmentations in the "
                "MultiSegmentationExtractor"
            )
    else:
        segmentation_extractors = [segmentation_extractor]
        if metadata is not None and not isinstance(metadata, list):
            metadata = [metadata]
    metadata_base_list = [
        get_nwb_segmentation_metadata(segmentation_extractor) for segmentation_extractor in segmentation_extractors
    ]

    # Updating base metadata with new:
    for num, data in enumerate(metadata_base_list):
        metadata_input = metadata[num] if metadata else {}
        metadata_base_list[num] = dict_deep_update(metadata_base_list[num], metadata_input, append_list=False)
    metadata_base_common = metadata_base_list[0]

    with make_or_load_nwbfile(
        nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata_base_common, overwrite=overwrite, verbose=verbose
    ) as nwbfile_out:
        _ = get_module(nwbfile=nwbfile_out, name="ophys", description="contains optical physiology processed data")
        for plane_no_loop, (segmentation_extractor, metadata) in enumerate(
            zip(segmentation_extractors, metadata_base_list)
        ):
            add_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile_out,
                metadata=metadata,
                plane_num=plane_no_loop,
                include_background_segmentation=include_background_segmentation,
                include_roi_centroids=include_roi_centroids,
                include_roi_acceptance=include_roi_acceptance,
                mask_type=mask_type,
                iterator_options=iterator_options,
            )

    return nwbfile_out
