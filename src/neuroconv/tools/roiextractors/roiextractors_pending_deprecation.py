"""Deprecated roiextractors functions pending removal.

These functions are kept for backward compatibility only. Use high-level
interface methods (e.g., BaseSegmentationExtractorInterface.add_to_nwbfile()) instead.
"""

import warnings

from pynwb import NWBFile
from roiextractors import SegmentationExtractor

from .roiextractors import _add_fluorescence_traces_to_nwbfile


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
