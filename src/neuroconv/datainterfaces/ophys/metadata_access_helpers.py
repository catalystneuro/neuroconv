"""Helper functions for accessing ophys metadata with backward compatibility."""

from typing import Any, Dict


def get_imaging_plane_metadata(ophys_metadata: Dict[str, Any], metadata_key: str) -> Dict[str, Any]:
    """
    Get imaging plane metadata handling both old list and new dictionary structures.

    Parameters
    ----------
    ophys_metadata : dict
        The Ophys section of the metadata
    metadata_key : str
        The key to use for dictionary access

    Returns
    -------
    dict
        The imaging plane metadata
    """
    if "ImagingPlanes" in ophys_metadata:
        # New dictionary structure
        return ophys_metadata["ImagingPlanes"][metadata_key]
    else:
        # Old list structure (backward compatibility)
        return ophys_metadata["ImagingPlane"][0]


def get_photon_series_metadata(ophys_metadata: Dict[str, Any], series_type: str, metadata_key: str) -> Dict[str, Any]:
    """
    Get photon series metadata handling both old list and new dictionary structures.

    Parameters
    ----------
    ophys_metadata : dict
        The Ophys section of the metadata
    series_type : str
        Either "TwoPhotonSeries" or "OnePhotonSeries"
    metadata_key : str
        The key to use for dictionary access

    Returns
    -------
    dict
        The photon series metadata
    """
    if series_type in ophys_metadata and isinstance(ophys_metadata[series_type], dict):
        # New dictionary structure
        return ophys_metadata[series_type][metadata_key]
    else:
        # Old list structure (backward compatibility)
        return ophys_metadata[series_type][0]


def get_segmentation_metadata(ophys_metadata: Dict[str, Any], metadata_key: str) -> Dict[str, Any]:
    """
    Get image segmentation metadata handling both old list and new dictionary structures.

    Parameters
    ----------
    ophys_metadata : dict
        The Ophys section of the metadata
    metadata_key : str
        The key to use for dictionary access

    Returns
    -------
    dict
        The segmentation metadata
    """
    image_seg = ophys_metadata.get("ImageSegmentation", {})

    # Check if it's new dictionary format
    if isinstance(image_seg, dict) and "plane_segmentations" not in image_seg and metadata_key in image_seg:
        return image_seg[metadata_key]
    # Old list format
    elif "plane_segmentations" in image_seg and isinstance(image_seg["plane_segmentations"], list):
        return image_seg["plane_segmentations"][0]
    else:
        # Fallback for edge cases
        return {}
