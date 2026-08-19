"""Shared writer for pose estimation data (the ``ndx-pose`` extension)."""

import numpy as np
from pynwb import NWBFile

from ..nwb_helpers import get_module
from ...utils.checks import calculate_regular_series_rate

# Key the placeholder registry entries are filed under when the caller supplies no metadata; mirrors the
# ophys and icephys ``default_metadata_key``.
DEFAULT_METADATA_KEY = "default_metadata_key"


def _get_pose_metadata_placeholders(keypoint_names) -> dict:
    """Fresh pose metadata holding only what writing a container requires, keyed by ``DEFAULT_METADATA_KEY``.

    Placeholders live in one place so they are easy to identify downstream and we make up as little
    metadata as possible: only the object names, which NWB requires and nothing can derive. No device and
    no skeleton, both of which ``ndx-pose`` makes optional, and no free text, which it defaults itself.
    Each call returns an independent copy.
    """
    return {
        "Pose": {
            "PoseEstimations": {
                DEFAULT_METADATA_KEY: {
                    "name": "PoseEstimation",
                    "PoseEstimationSeries": {
                        keypoint_name: {"name": f"PoseEstimationSeries{keypoint_name}"}
                        for keypoint_name in keypoint_names
                    },
                },
            },
        },
    }


def _add_pose_estimation_to_nwbfile(
    nwbfile: NWBFile,
    *,
    keypoint_data: dict[str, tuple[np.ndarray, np.ndarray | None]],
    timestamps: np.ndarray,
    metadata: dict | None = None,
    metadata_key: str = DEFAULT_METADATA_KEY,
) -> None:
    """Add one ``PoseEstimation`` container to an NWBFile from the dict-based metadata shape.

    The data comes from ``keypoint_data`` and everything else from ``metadata``: the container entry is
    read from ``metadata["Pose"]["PoseEstimations"][metadata_key]``, and its ``device_metadata_key`` and
    ``skeleton_metadata_key`` are followed into ``metadata["Devices"]`` and
    ``metadata["Pose"]["Skeletons"]``. Both cross-references are optional; an absent one means the
    container has no device or no skeleton rather than a fabricated placeholder. A ``Device`` or
    ``Skeleton`` whose name is already in the file is reused, so several containers can share one by
    pointing at the same key.

    Fields that ``ndx-pose`` gives a default (``unit``, ``confidence_definition``, and the container's
    own ``description``) are passed only when the metadata carries them, so the extension's defaults
    apply otherwise rather than a value invented here. ``metadata`` itself is optional: what NWB requires
    and nothing can derive, which is the object names, falls back to ``_get_pose_metadata_placeholders``,
    so the keypoint arrays alone are enough to write a file.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        The file to add the container to. It is written to its "behavior" processing module.
    keypoint_data : dict
        Maps keypoint name to ``(positions, confidence)``, where positions is a ``(num_frames, 2)`` or
        ``(num_frames, 3)`` array and confidence is a ``(num_frames,)`` array or None. Its keys index the
        container entry's ``PoseEstimationSeries`` registry, and its order is the order of the series.
    timestamps : numpy.ndarray
        One time in seconds per frame, shared by every series. A regularly sampled vector is written as a
        rate and a starting time instead.
    metadata : dict, optional
        Metadata in the dict-based shape, carrying the top-level ``"Pose"`` and ``"Devices"`` registries.
        When it is not given, the placeholders are used, which name the objects and nothing else. An
        entry that omits a name is filled from them field by field, so partial metadata is enough.
    metadata_key : str, optional
        The key of the container entry to write, within ``metadata["Pose"]["PoseEstimations"]``. A key
        naming no entry raises, since it is a caller mistake rather than absent metadata.
    """
    from ndx_pose import PoseEstimation, PoseEstimationSeries, Skeleton, Skeletons

    placeholders = _get_pose_metadata_placeholders(keypoint_names=keypoint_data)
    placeholder_container = placeholders["Pose"]["PoseEstimations"][DEFAULT_METADATA_KEY]
    if metadata is None:
        metadata = placeholders

    pose_metadata = metadata["Pose"]
    container_entry = pose_metadata["PoseEstimations"][metadata_key]
    container_name = container_entry.get("name", placeholder_container["name"])

    behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="processed behavioral data")
    if container_name in behavior_module.data_interfaces:
        raise ValueError(f"The nwbfile already contains a data interface with the name '{container_name}'.")

    device = None
    device_metadata_key = container_entry.get("device_metadata_key")
    if device_metadata_key is not None:
        device_entry = metadata["Devices"][device_metadata_key]
        device_name = device_entry["name"]
        if device_name in nwbfile.devices:
            device = nwbfile.devices[device_name]
        else:
            device = nwbfile.create_device(name=device_name, description=device_entry.get("description", ""))

    skeleton = None
    skeleton_metadata_key = container_entry.get("skeleton_metadata_key")
    if skeleton_metadata_key is not None:
        skeleton_entry = pose_metadata["Skeletons"][skeleton_metadata_key]
        skeleton_name = skeleton_entry["name"]
        existing_skeletons = (
            behavior_module["Skeletons"].skeletons if "Skeletons" in behavior_module.data_interfaces else {}
        )
        if skeleton_name in existing_skeletons:
            skeleton = existing_skeletons[skeleton_name]
        else:
            # ndx-pose stores one subject per file, so the file's subject is the pose subject. The entry's
            # optional "subject" names an individual within the source, and a mismatch means these keypoints
            # belong to someone other than the file's subject, so no link is made.
            subject = None
            if nwbfile.subject is not None:
                skeleton_subject = skeleton_entry.get("subject")
                if skeleton_subject is None or skeleton_subject == nwbfile.subject.subject_id:
                    subject = nwbfile.subject
            edges = skeleton_entry.get("edges")
            skeleton = Skeleton(
                name=skeleton_name,
                nodes=skeleton_entry["nodes"],
                # Node indices and video dimensions are small and non-negative, and ndx-pose specifies
                # both as uint8. Writing them as an unsigned type avoids an hdmf conversion warning.
                edges=np.asarray(edges, dtype="uint16") if edges is not None and len(edges) else None,
                subject=subject,
            )

    timestamps = np.asarray(timestamps).astype("float64", copy=False)
    rate = calculate_regular_series_rate(timestamps)
    if rate is None:
        timing_kwargs = dict(timestamps=timestamps)
    else:
        timing_kwargs = dict(rate=rate, starting_time=timestamps[0])

    series_entries = container_entry.get("PoseEstimationSeries", {})
    placeholder_series = placeholder_container["PoseEstimationSeries"]
    pose_estimation_series = []
    for keypoint_name, (positions, confidence) in keypoint_data.items():
        series_entry = series_entries.get(keypoint_name, {})
        series_kwargs = dict(
            timing_kwargs,
            name=series_entry.get("name", placeholder_series[keypoint_name]["name"]),
            description=series_entry.get("description", f"Pose estimation series for {keypoint_name}."),
            data=positions,
            reference_frame=series_entry.get("reference_frame", "(0,0) is unknown."),
        )
        if confidence is not None:
            series_kwargs["confidence"] = confidence
        for field in ("unit", "confidence_definition"):
            if series_entry.get(field) is not None:
                series_kwargs[field] = series_entry[field]

        pose_estimation_series.append(PoseEstimationSeries(**series_kwargs))

    container_kwargs = dict(
        name=container_name,
        pose_estimation_series=pose_estimation_series,
        skeleton=skeleton,
        devices=[device] if device is not None else None,
    )
    optional_container_fields = (
        "description",
        "source_software",
        "source_software_version",
        "scorer",
        "original_videos",
        "labeled_videos",
    )
    for field in optional_container_fields:
        if container_entry.get(field) is not None:
            container_kwargs[field] = container_entry[field]

    dimensions = container_entry.get("dimensions")
    if dimensions is not None:
        container_kwargs["dimensions"] = np.asarray(dimensions, dtype="uint16")

    behavior_module.add(PoseEstimation(**container_kwargs))

    if skeleton is not None:
        if "Skeletons" not in behavior_module.data_interfaces:
            behavior_module.add(Skeletons(skeletons=[skeleton]))
        elif skeleton.name not in behavior_module["Skeletons"].skeletons:
            behavior_module["Skeletons"].add_skeletons(skeleton)
