"""Convert metadata written in the old list-based format into the dict-based one.

Transitional. The old format is converted where metadata enters the library, so everything downstream
sees one shape and the old write paths become unreachable. This module goes when the old format does.

The translator recognizes the old format and never the new one, so anything it does not recognize is
passed through untouched. It builds the converted blocks rather than editing a copy, which is what keeps
the caller's dictionary intact and makes translating an already-translated dictionary a no-op: the entry
points nest (``run_conversion`` calls ``add_to_nwbfile``, a converter's calls each interface's), so the
same metadata reaches it more than once per conversion.
"""

import warnings
from functools import lru_cache

from .dict import DeepDict

# Column descriptions, which are list-shaped in both formats.
_ECEPHYS_LIST_BLOCKS = ("Electrodes", "UnitProperties")
# Blocks the new format adds beside the registries. They are mappings, so without naming them here the
# translator would take one for an ``es_key``-addressed series and file it under ``ElectricalSeries``, or
# drop it, whenever a converter mixes shapes and translation runs at all.
_ECEPHYS_PASSTHROUGH_BLOCKS = ("ElectrodesTable",)
# Keys the translator consumes or produces, so they are never mistaken for an ``es_key`` entry.
_ECEPHYS_STRUCTURAL_KEYS = ("Device", "ElectrodeGroup", "ElectrodeGroups", "ElectricalSeries")
# Ophys blocks whose names exist only in the old format, so their presence settles the shape.
_OLD_OPHYS_ONLY_BLOCKS = ("TwoPhotonSeries", "OnePhotonSeries", "ImageSegmentation", "Fluorescence", "DfOverF")
# The dict format's own names per trace role and per summary image, which are collision-free across roles
# by construction. Kept here rather than imported from ``tools.roiextractors`` to avoid the import cycle;
# they are only reached when the old format cannot be carried across as written.
_ROI_RESPONSE_NAMES_BY_ROLE = {
    "raw": "RoiResponseSeries",
    "deconvolved": "Deconvolved",
    "neuropil": "Neuropil",
    "denoised": "Denoised",
    "baseline": "Baseline",
    "background": "Background",
    "dff": "DfOverF",
}
_SUMMARY_IMAGE_NAMES_BY_ROLE = {"correlation": "correlation_image", "mean": "mean_image"}


def _is_old_style_entry(value) -> bool:
    """Whether a value is a flat mapping of fields rather than a mapping of keyed entries.

    A mapping with no dict-valued members is the old format's single entry. A mapping that holds any
    entry of its own is the new format, including the mixed case where a stray field was written beside
    real entries, which is left alone so the schema can reject it with a message about that mistake.
    """
    return isinstance(value, dict) and len(value) > 0 and not any(isinstance(item, dict) for item in value.values())


def _register_entry(entries: dict, entry_metadata: dict) -> str:
    """Add an entry to a keyed block under a key, and return the key it went under.

    Entries are matched by ``name``, which is the only identity the old format had: an electrode group
    named its device by name, a photon series named its imaging plane, and the writer looked those names
    up. An entry already registered under another key wins, so a dictionary carrying both shapes for one
    physical thing (which converters produce today) ends up with one entry rather than two that collide
    on name.
    """
    name = entry_metadata["name"]
    for key, registered in entries.items():
        if registered.get("name") == name:
            entries[key] = {**registered, **entry_metadata}
            return key

    entries[name] = dict(entry_metadata)
    return name


def _entries_already_in_the_dict_format(block) -> dict:
    """Copy the entries a block already holds in the dict format, so translation adds to them.

    One old-format key makes the whole block old, but it does not make the rest of the block stop
    existing: a converter hands one dictionary to interfaces that disagree about the format, and after
    the switch an old-format edit lands on dict-format metadata. Building the block out of the old keys
    alone would drop whatever was already there, silently in most cases.
    """
    if not isinstance(block, dict):
        return {}

    return {key: dict(entry) for key, entry in block.items() if isinstance(entry, dict)}


def _keys_by_name(entries: dict) -> dict:
    """Map each entry's ``name`` to the key it lives under, which is how the old format's links resolve."""
    return {entry["name"]: key for key, entry in entries.items() if "name" in entry}


def _role_keyed_entries_already_in_the_dict_format(block) -> dict:
    """As ``_entries_already_in_the_dict_format``, for the blocks whose entries are keyed by role.

    ``RoiResponses`` and ``SegmentationImages`` hold one dictionary per role, and those are rewritten in
    place when names collide, so they are copied too rather than shared with the caller's dictionary.
    """
    return {
        key: _entries_already_in_the_dict_format(entry)
        for key, entry in _entries_already_in_the_dict_format(block).items()
    }


def _ecephys_block_is_old(ecephys_metadata: dict) -> bool:
    """Whether an ``Ecephys`` block is written in the old list-based format."""
    if isinstance(ecephys_metadata.get("Device"), list) or isinstance(ecephys_metadata.get("ElectrodeGroup"), list):
        return True

    for key, value in ecephys_metadata.items():
        if key in _ECEPHYS_LIST_BLOCKS or key in _ECEPHYS_PASSTHROUGH_BLOCKS:
            continue
        if key == "ElectricalSeries" or key not in _ECEPHYS_STRUCTURAL_KEYS:
            # ``ElectricalSeries`` exists in both formats; any other key is an ``es_key``-addressed entry.
            if _is_old_style_entry(value):
                return True

    return False


def _translate_ecephys_block(
    ecephys_metadata: dict,
    devices: dict,
    es_key: str | None,
    metadata_key: str | None,
) -> dict:
    """Build the dict-format ``Ecephys`` block, registering devices into ``devices`` as it goes."""
    translated = {}

    for device_metadata in ecephys_metadata.get("Device", []):
        _register_entry(devices, device_metadata)

    electrode_groups = _entries_already_in_the_dict_format(ecephys_metadata.get("ElectrodeGroups"))
    for group_metadata in ecephys_metadata.get("ElectrodeGroup", []):
        entry = dict(group_metadata)
        device_name = entry.pop("device", None)
        if device_name is not None:
            # A group naming a device the metadata does not describe is legal in the old format, where
            # the writer generated one, so the name becomes an entry rather than a failure.
            entry["device_metadata_key"] = _register_entry(devices, {"name": device_name})
        _register_entry(electrode_groups, entry)
    if electrode_groups:
        translated["ElectrodeGroups"] = electrode_groups

    electrical_series = {}
    existing = ecephys_metadata.get("ElectricalSeries")
    if isinstance(existing, dict) and existing:
        if _is_old_style_entry(existing):
            electrical_series[metadata_key or es_key or "ElectricalSeries"] = dict(existing)
        else:
            electrical_series.update({key: dict(entry) for key, entry in existing.items()})

    for key, value in ecephys_metadata.items():
        if key in _ECEPHYS_STRUCTURAL_KEYS or key in _ECEPHYS_LIST_BLOCKS or key in _ECEPHYS_PASSTHROUGH_BLOCKS:
            continue
        if _is_old_style_entry(value):
            # An ``es_key``-addressed entry. Its label is ``metadata_key`` when this call knows which
            # entry it is writing, and otherwise the old key, which is all validation needs.
            label = metadata_key if (es_key is not None and key == es_key and metadata_key) else key
            electrical_series[label] = dict(value)

    if electrical_series:
        translated["ElectricalSeries"] = electrical_series

    for key in (*_ECEPHYS_LIST_BLOCKS, *_ECEPHYS_PASSTHROUGH_BLOCKS):
        if key in ecephys_metadata:
            translated[key] = ecephys_metadata[key]

    return translated


def _ophys_block_is_old(ophys_metadata: dict) -> bool:
    """Whether an ``Ophys`` block is written in the old list-based format."""
    if isinstance(ophys_metadata.get("Device"), list) or isinstance(ophys_metadata.get("ImagingPlane"), list):
        return True

    # These blocks exist only in the old format: their dict-format counterparts are named differently.
    if any(key in ophys_metadata for key in _OLD_OPHYS_ONLY_BLOCKS):
        return True

    # ``SegmentationImages`` exists in both. The old one carries the container's own ``name`` and
    # ``description`` beside the per-plane-segmentation entries, and the new one holds entries only.
    summary_images = ophys_metadata.get("SegmentationImages")
    if isinstance(summary_images, dict) and any(not isinstance(value, dict) for value in summary_images.values()):
        return True

    return False


def _translate_ophys_block(
    ophys_metadata: dict,
    devices: dict,
    metadata_key: str | None,
    photon_series_type: str | None,
    photon_series_index: int | None,
    plane_segmentation_name: str | None,
) -> dict:
    """Build the dict-format ``Ophys`` block, registering devices into ``devices`` as it goes.

    The old format links by name and the new one by key, so the name-to-key maps built here are what the
    photon series, plane segmentations, traces and summary images are rewritten against.
    """
    translated = {}

    for device_metadata in ophys_metadata.get("Device", []):
        _register_entry(devices, device_metadata)

    imaging_planes = _entries_already_in_the_dict_format(ophys_metadata.get("ImagingPlanes"))
    imaging_plane_keys_by_name = _keys_by_name(imaging_planes)
    for plane_metadata in ophys_metadata.get("ImagingPlane", []):
        entry = dict(plane_metadata)
        device_name = entry.pop("device", None)
        if device_name is not None:
            entry["device_metadata_key"] = _register_entry(devices, {"name": device_name})
        imaging_plane_keys_by_name[entry["name"]] = _register_entry(imaging_planes, entry)
    if imaging_planes:
        translated["ImagingPlanes"] = imaging_planes

    microscopy_series = _entries_already_in_the_dict_format(ophys_metadata.get("MicroscopySeries"))
    for series_type in ("TwoPhotonSeries", "OnePhotonSeries"):
        for index, series_metadata in enumerate(ophys_metadata.get(series_type, [])):
            entry = dict(series_metadata)
            plane_name = entry.pop("imaging_plane", None)
            if plane_name is not None:
                entry["imaging_plane_metadata_key"] = imaging_plane_keys_by_name.get(plane_name, plane_name)
            addressed = metadata_key is not None and series_type == photon_series_type and index == photon_series_index
            if addressed:
                microscopy_series[metadata_key] = entry
            else:
                _register_entry(microscopy_series, entry)
    if microscopy_series:
        translated["MicroscopySeries"] = microscopy_series

    plane_segmentations = _entries_already_in_the_dict_format(ophys_metadata.get("PlaneSegmentations"))
    plane_segmentation_keys_by_name = _keys_by_name(plane_segmentations)
    image_segmentation = ophys_metadata.get("ImageSegmentation", {})
    for segmentation_metadata in image_segmentation.get("plane_segmentations", []):
        entry = dict(segmentation_metadata)
        plane_name = entry.pop("imaging_plane", None)
        if plane_name is not None:
            entry["imaging_plane_metadata_key"] = imaging_plane_keys_by_name.get(plane_name, plane_name)
        addressed = metadata_key is not None and entry["name"] == plane_segmentation_name
        if addressed:
            key = metadata_key
            plane_segmentations[key] = entry
        else:
            key = _register_entry(plane_segmentations, entry)
        plane_segmentation_keys_by_name[entry["name"]] = key
    if plane_segmentations:
        translated["PlaneSegmentations"] = plane_segmentations

    # ``Fluorescence`` and ``DfOverF`` were two containers holding traces for the same plane
    # segmentations, distinguished by which roles they carried. The dict format has one block per plane
    # segmentation with the role as the key, so the two merge.
    roi_responses = _role_keyed_entries_already_in_the_dict_format(ophys_metadata.get("RoiResponses"))
    for container in ("Fluorescence", "DfOverF"):
        container_metadata = ophys_metadata.get(container, {})
        if not isinstance(container_metadata, dict):
            continue
        for segmentation_name, traces in container_metadata.items():
            if not isinstance(traces, dict):
                continue  # The container's own ``name``, which the dict format does not carry.
            key = plane_segmentation_keys_by_name.get(segmentation_name, segmentation_name)
            roi_responses.setdefault(key, {}).update({role: dict(trace) for role, trace in traces.items()})
    for traces in roi_responses.values():
        _resolve_name_collisions(traces, names_by_role=_ROI_RESPONSE_NAMES_BY_ROLE)
    if roi_responses:
        translated["RoiResponses"] = roi_responses

    # The old writer wrote whichever summary images the extractor had, whether or not the metadata named
    # them, so an entry declaring only one of them still produced the rest. The dict writer writes what is
    # declared, so the declared entries are merged over the dict format's own defaults rather than
    # replacing them, and an image the caller never mentioned is written under the dict format's name for
    # it instead of disappearing.
    summary_images = ophys_metadata.get("SegmentationImages", {})
    translated_summary_images = {}
    for segmentation_name, images in summary_images.items():
        if not isinstance(images, dict):
            continue  # The container's own ``name`` and ``description``.
        key = plane_segmentation_keys_by_name.get(segmentation_name, segmentation_name)
        entry = {role: {"name": name} for role, name in _SUMMARY_IMAGE_NAMES_BY_ROLE.items()}
        entry.update({role: dict(image) for role, image in images.items()})
        translated_summary_images[key] = entry
    if translated_summary_images:
        translated["SegmentationImages"] = translated_summary_images

    return translated


def _resolve_name_collisions(entries: dict, names_by_role: dict) -> None:
    """Rename entries that would collide on ``name`` once their two old containers become one.

    The old format could give a trace the same name in ``Fluorescence`` and in ``DfOverF``, because they
    were separate containers, and the defaults did exactly that (``RoiResponseSeries`` for both the raw
    and the df/F trace). The dict format writes one container, where the second one would be dropped, so
    the later role falls back to the dict format's own name, which cannot collide.
    """
    seen_names = set()
    for role, entry in entries.items():
        name = entry.get("name")
        if name is None:
            continue
        if name in seen_names and role in names_by_role:
            entry["name"] = names_by_role[role]
            name = entry["name"]
        seen_names.add(name)


@lru_cache(maxsize=1)
def _warn_that_the_old_format_is_deprecated() -> None:
    """Tell the caller their metadata is in the old format, once per process.

    The entry points nest and a converter translates once per interface, so a single conversion reaches
    the translator several times and a long-running script reaches it once per session. The message is
    the same every time and says nothing about which call produced it, so it is emitted once and cached.
    Tests that assert on it call ``cache_clear`` first.
    """
    warnings.warn(
        "The metadata passed to NeuroConv is in the old list-based format, which is deprecated and will "
        "be removed on or after August 2027. It was converted for this conversion, so the file written is "
        "unaffected. The dict-based format keys each entry by a name you choose instead of by its position "
        "in a list. Call get_metadata() and edit the dictionary it returns to see the shape your interface "
        "expects.",
        FutureWarning,
        stacklevel=2,
    )


def _translate_old_metadata(
    metadata: dict | None,
    *,
    es_key: str | None = None,
    metadata_key: str | None = None,
    photon_series_type: str | None = None,
    photon_series_index: int | None = None,
    plane_segmentation_name: str | None = None,
) -> dict | None:
    """Return metadata with any old-format block converted. The input is not modified.

    Parameters
    ----------
    metadata : dict, optional
        The metadata to convert. Returned unchanged when it is already in the dict-based format.
    es_key : str, optional
        Where the recording's entry lives in the old format, as a key under ``metadata["Ecephys"]``.
    metadata_key : str, optional
        Where it goes in the dict format, as a key under ``metadata["Ecephys"]["ElectricalSeries"]``.
        When omitted the old key is kept, which is what validation needs and what a direct caller who
        passed only ``es_key`` gets.

    Returns
    -------
    dict or None
        The converted metadata, or the input when there was nothing to convert.
    """
    if not isinstance(metadata, dict):
        return metadata

    registry = metadata.get("Devices")
    devices = {}
    if isinstance(registry, list):
        for device_metadata in registry:
            _register_entry(devices, device_metadata)
    elif isinstance(registry, dict):
        devices = {key: dict(entry) for key, entry in registry.items()}

    ecephys_metadata = metadata.get("Ecephys")
    ecephys_is_old = isinstance(ecephys_metadata, dict) and _ecephys_block_is_old(ecephys_metadata)

    ophys_metadata = metadata.get("Ophys")
    ophys_is_old = isinstance(ophys_metadata, dict) and _ophys_block_is_old(ophys_metadata)

    if not ecephys_is_old and not ophys_is_old and not isinstance(registry, list):
        return metadata

    _warn_that_the_old_format_is_deprecated()

    translated = {key: value for key, value in metadata.items()}
    if ecephys_is_old:
        translated["Ecephys"] = _translate_ecephys_block(
            ecephys_metadata=ecephys_metadata, devices=devices, es_key=es_key, metadata_key=metadata_key
        )
    if ophys_is_old:
        translated["Ophys"] = _translate_ophys_block(
            ophys_metadata=ophys_metadata,
            devices=devices,
            metadata_key=metadata_key,
            photon_series_type=photon_series_type,
            photon_series_index=photon_series_index,
            plane_segmentation_name=plane_segmentation_name,
        )
    if devices:
        translated["Devices"] = devices

    return DeepDict(translated) if isinstance(metadata, DeepDict) else translated
