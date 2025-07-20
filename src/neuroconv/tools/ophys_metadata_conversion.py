"""Utilities for converting between old list-based and new dictionary-based ophys metadata structures."""

import warnings
from copy import deepcopy
from typing import Any, Dict


def is_old_ophys_metadata_format(metadata: Dict[str, Any]) -> bool:
    """
    Check if metadata is in old list-based format.

    Parameters
    ----------
    metadata : dict
        The metadata dictionary to check.

    Returns
    -------
    bool
        True if metadata is in old list format, False otherwise.
    """
    if "Ophys" not in metadata:
        return False

    ophys = metadata["Ophys"]
    return (
        ("ImagingPlane" in ophys and isinstance(ophys.get("ImagingPlane"), list))
        or ("TwoPhotonSeries" in ophys and isinstance(ophys.get("TwoPhotonSeries"), list))
        or ("OnePhotonSeries" in ophys and isinstance(ophys.get("OnePhotonSeries"), list))
        or ("ImageSegmentation" in ophys and "plane_segmentations" in ophys.get("ImageSegmentation", {}))
    )


def convert_ophys_metadata_to_dict(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert old list-based ophys metadata to new dictionary format.

    Parameters
    ----------
    metadata : dict
        The metadata dictionary to convert.

    Returns
    -------
    dict
        Metadata with ophys components converted to dictionary format.
    """
    if "Ophys" not in metadata or not is_old_ophys_metadata_format(metadata):
        return metadata

    # Create a deep copy to avoid modifying the original
    metadata = deepcopy(metadata)
    ophys = metadata["Ophys"]

    # Convert ImagingPlane list to ImagingPlanes dict
    if "ImagingPlane" in ophys and isinstance(ophys["ImagingPlane"], list):
        imaging_planes_dict = {}
        for i, plane in enumerate(ophys["ImagingPlane"]):
            # Try to use a metadata_key if present, otherwise generate one
            key = plane.get("metadata_key", f"imaging_plane_{i}")
            imaging_planes_dict[key] = plane
        ophys["ImagingPlanes"] = imaging_planes_dict
        del ophys["ImagingPlane"]

        warnings.warn(
            "Ophys metadata structure has changed: 'ImagingPlane' list is now 'ImagingPlanes' dictionary. "
            "Your metadata has been automatically converted. Please update your code to use the new structure.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Convert TwoPhotonSeries list to dict
    if "TwoPhotonSeries" in ophys and isinstance(ophys["TwoPhotonSeries"], list):
        two_photon_dict = {}
        for i, series in enumerate(ophys["TwoPhotonSeries"]):
            # Try to use a metadata_key if present, otherwise generate one
            key = series.get("metadata_key", f"two_photon_series_{i}")
            # Update imaging_plane reference if we converted ImagingPlanes
            if "ImagingPlanes" in ophys and "imaging_plane" in series:
                old_plane_name = series["imaging_plane"]
                # Find the key for this plane name
                for plane_key, plane_data in ophys["ImagingPlanes"].items():
                    if plane_data.get("name") == old_plane_name:
                        series["imaging_plane"] = plane_key
                        break
            two_photon_dict[key] = series
        ophys["TwoPhotonSeries"] = two_photon_dict

        warnings.warn(
            "Ophys metadata structure has changed: 'TwoPhotonSeries' list is now a dictionary. "
            "Your metadata has been automatically converted. Please update your code to use the new structure.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Convert OnePhotonSeries list to dict
    if "OnePhotonSeries" in ophys and isinstance(ophys["OnePhotonSeries"], list):
        one_photon_dict = {}
        for i, series in enumerate(ophys["OnePhotonSeries"]):
            # Try to use a metadata_key if present, otherwise generate one
            key = series.get("metadata_key", f"one_photon_series_{i}")
            # Update imaging_plane reference if we converted ImagingPlanes
            if "ImagingPlanes" in ophys and "imaging_plane" in series:
                old_plane_name = series["imaging_plane"]
                # Find the key for this plane name
                for plane_key, plane_data in ophys["ImagingPlanes"].items():
                    if plane_data.get("name") == old_plane_name:
                        series["imaging_plane"] = plane_key
                        break
            one_photon_dict[key] = series
        ophys["OnePhotonSeries"] = one_photon_dict

        warnings.warn(
            "Ophys metadata structure has changed: 'OnePhotonSeries' list is now a dictionary. "
            "Your metadata has been automatically converted. Please update your code to use the new structure.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Convert ImageSegmentation plane_segmentations list to dict
    if "ImageSegmentation" in ophys and "plane_segmentations" in ophys["ImageSegmentation"]:
        plane_segmentations = ophys["ImageSegmentation"]["plane_segmentations"]
        if isinstance(plane_segmentations, list):
            segmentation_dict = {}
            for i, segmentation in enumerate(plane_segmentations):
                # Try to use a metadata_key if present, otherwise generate one
                key = segmentation.get("metadata_key", f"segmentation_{i}")
                # Update imaging_plane reference if we converted ImagingPlanes
                if "ImagingPlanes" in ophys and "imaging_plane" in segmentation:
                    old_plane_name = segmentation["imaging_plane"]
                    # Find the key for this plane name
                    for plane_key, plane_data in ophys["ImagingPlanes"].items():
                        if plane_data.get("name") == old_plane_name:
                            segmentation["imaging_plane"] = plane_key
                            break
                segmentation_dict[key] = segmentation

            # Remove plane_segmentations and add the segmentations directly
            del ophys["ImageSegmentation"]["plane_segmentations"]
            # Keep any existing properties like name
            for key, value in segmentation_dict.items():
                ophys["ImageSegmentation"][key] = value

            warnings.warn(
                "Ophys metadata structure has changed: 'ImageSegmentation.plane_segmentations' list is now "
                "direct dictionary entries in 'ImageSegmentation'. Your metadata has been automatically converted. "
                "Please update your code to use the new structure.",
                DeprecationWarning,
                stacklevel=2,
            )

    return metadata


def get_plane_segmentation_metadata(metadata: Dict[str, Any], key_or_name: str) -> Dict[str, Any] | None:
    """
    Get plane segmentation metadata by key or name, handling both old and new formats.

    Parameters
    ----------
    metadata : dict
        The metadata dictionary.
    key_or_name : str
        Either the metadata key (new format) or the plane segmentation name (old format).

    Returns
    -------
    dict or None
        The plane segmentation metadata if found, None otherwise.
    """
    if "Ophys" not in metadata or "ImageSegmentation" not in metadata["Ophys"]:
        return None

    image_seg = metadata["Ophys"]["ImageSegmentation"]

    # Check if it's new dictionary format
    if isinstance(image_seg, dict) and "plane_segmentations" not in image_seg:
        # Try direct key access first
        if key_or_name in image_seg:
            return image_seg[key_or_name]
        # Then try to find by name
        for key, seg_data in image_seg.items():
            if isinstance(seg_data, dict) and seg_data.get("name") == key_or_name:
                return seg_data
    # Old list format
    elif "plane_segmentations" in image_seg and isinstance(image_seg["plane_segmentations"], list):
        for seg_data in image_seg["plane_segmentations"]:
            if seg_data.get("name") == key_or_name:
                return seg_data

    return None


def get_imaging_plane_metadata(metadata: Dict[str, Any], key_or_name: str) -> Dict[str, Any] | None:
    """
    Get imaging plane metadata by key or name, handling both old and new formats.

    Parameters
    ----------
    metadata : dict
        The metadata dictionary.
    key_or_name : str
        Either the metadata key (new format) or the imaging plane name (old format).

    Returns
    -------
    dict or None
        The imaging plane metadata if found, None otherwise.
    """
    if "Ophys" not in metadata:
        return None

    ophys = metadata["Ophys"]

    # Check new dictionary format
    if "ImagingPlanes" in ophys and isinstance(ophys["ImagingPlanes"], dict):
        # Try direct key access first
        if key_or_name in ophys["ImagingPlanes"]:
            return ophys["ImagingPlanes"][key_or_name]
        # Then try to find by name
        for key, plane_data in ophys["ImagingPlanes"].items():
            if plane_data.get("name") == key_or_name:
                return plane_data
    # Old list format
    elif "ImagingPlane" in ophys and isinstance(ophys["ImagingPlane"], list):
        for plane_data in ophys["ImagingPlane"]:
            if plane_data.get("name") == key_or_name:
                return plane_data

    return None
