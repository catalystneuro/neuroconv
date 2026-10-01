"""Shared writer for pose estimation data (the ``ndx-pose`` extension)."""

import warnings

import numpy as np
from pynwb import NWBFile

from ..nwb_helpers import get_module
from ..nwb_helpers._metadata_and_file_helpers import _add_device_to_nwbfile
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


def _resolve_image_series(nwbfile: NWBFile, metadata: dict, metadata_key: str, field: str):
    """Find the ``ImageSeries`` a video interface wrote, by way of its metadata entry.

    Unlike the other cross-references the writer follows, this one cannot be created here: the
    ``ImageSeries`` belongs to a video interface, which also chooses whether it lands in ``acquisition``
    or in the behavior processing module, so both are searched and a missing one is a caller error about
    ordering rather than about metadata.
    """
    videos_metadata = metadata.get("Behavior", {}).get("ExternalVideos", {})
    if metadata_key not in videos_metadata:
        raise ValueError(
            f"{field} '{metadata_key}' was not found in metadata['Behavior']['ExternalVideos'] "
            f"(available keys: {list(videos_metadata)})."
        )

    image_series_name = videos_metadata[metadata_key]["name"]
    if image_series_name in nwbfile.acquisition:
        return nwbfile.acquisition[image_series_name]
    behavior_module = nwbfile.processing.get("behavior")
    if behavior_module is not None and image_series_name in behavior_module.data_interfaces:
        return behavior_module[image_series_name]

    raise ValueError(
        f"{field} '{metadata_key}' names the ImageSeries '{image_series_name}', which is not in the file. "
        "The video has to be written before the pose that links it, so add the video interface to the same "
        "conversion and let it run first."
    )


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
    ``metadata["Pose"]["Skeletons"]``, while ``source_video_metadata_key`` and
    ``labeled_video_metadata_key`` are followed into ``metadata["Behavior"]["ExternalVideos"]`` and linked
    as objects rather than as paths. Both cross-references are optional; an absent one means the
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
    from ndx_pose import PoseEstimation

    placeholders = _get_pose_metadata_placeholders(keypoint_names=keypoint_data)
    placeholder_container = placeholders["Pose"]["PoseEstimations"][DEFAULT_METADATA_KEY]
    if metadata is None:
        metadata = placeholders

    # Checked rather than indexed: ``metadata`` is often a ``DeepDict``, where a missing key auto-vivifies
    # into an empty entry instead of raising, and the write then succeeds against the placeholders with
    # names nobody asked for.
    pose_metadata = metadata.get("Pose", {})
    containers_metadata = pose_metadata.get("PoseEstimations", {})
    if metadata_key not in containers_metadata:
        raise ValueError(
            f"metadata_key '{metadata_key}' was not found in metadata['Pose']['PoseEstimations'] "
            f"(available keys: {list(containers_metadata)})."
        )
    container_entry = containers_metadata[metadata_key]
    container_name = container_entry.get("name", placeholder_container["name"])

    behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="processed behavioral data")
    if container_name in behavior_module.data_interfaces:
        raise ValueError(f"The nwbfile already contains a data interface with the name '{container_name}'.")

    device = None
    device_metadata_key = container_entry.get("device_metadata_key")
    if device_metadata_key is not None:
        device = _add_device_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key=device_metadata_key)

    skeleton = _get_or_build_skeleton(
        nwbfile=nwbfile,
        behavior_module=behavior_module,
        pose_metadata=pose_metadata,
        skeleton_metadata_key=container_entry.get("skeleton_metadata_key"),
    )

    pose_estimation_series = _build_pose_estimation_series(
        keypoint_data=keypoint_data,
        timestamps=timestamps,
        series_entries=container_entry.get("PoseEstimationSeries", {}),
        placeholder_series=placeholder_container["PoseEstimationSeries"],
    )

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

    # A link to the video object in the file, which ndx-pose prefers over the ``original_videos`` paths
    # "as it provides a formal reference rather than a file path string".
    for field, container_field in (
        ("source_video_metadata_key", "source_video"),
        ("labeled_video_metadata_key", "labeled_video"),
    ):
        video_metadata_key = container_entry.get(field)
        if video_metadata_key is not None:
            container_kwargs[container_field] = _resolve_image_series(
                nwbfile=nwbfile, metadata=metadata, metadata_key=video_metadata_key, field=field
            )

    dimensions = container_entry.get("dimensions")
    if dimensions is not None:
        container_kwargs["dimensions"] = np.asarray(dimensions, dtype="uint16")

    # TODO: remove with the next ndx-pose release. Released ndx-pose (0.3.0) warns when the frame dimensions
    # or the video paths are written without an equal number of camera devices, but writes them anyway, so a
    # camera would buy nothing but silence and no pose format records one. rly/ndx-pose#57 deprecates all
    # three fields in favour of the ``source_video`` link and drops the check, at which point this goes.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=".*must equal the number of camera devices.*", category=DeprecationWarning
        )
        pose_estimation = PoseEstimation(**container_kwargs)
    behavior_module.add(pose_estimation)

    _add_skeleton_to_behavior_module(behavior_module=behavior_module, skeleton=skeleton)


def _add_multi_camera_pose_estimation_to_nwbfile(
    nwbfile: NWBFile,
    *,
    keypoint_data: dict[str, tuple[np.ndarray, np.ndarray | None]],
    timestamps: np.ndarray,
    metadata: dict,
    metadata_key: str,
) -> None:
    """Add one ``MultiCameraPoseEstimation`` container to an NWBFile from the dict-based metadata shape.

    The multi-camera counterpart of :func:`_add_pose_estimation_to_nwbfile`, for keypoints triangulated
    from several calibrated cameras into one 3D coordinate system. The container entry is read from
    ``metadata["Pose"]["MultiCameraPoseEstimations"][metadata_key]`` and carries the triangulated series
    the same way a ``PoseEstimations`` entry does. Its ``pose_estimation_metadata_keys`` list the
    per-camera ``PoseEstimation`` children in ``metadata["Pose"]["PoseEstimations"]``; each child is
    written with its camera (``device_metadata_key``, into ``metadata["Devices"]``) and its source video
    (``source_video_metadata_key``, into ``metadata["Behavior"]["ExternalVideos"]``) and no series of its
    own, since the keypoints belong to the container rather than to any one camera. A camera ``Device``
    whose name is already in the file is reused, so several animals filmed by the same rig share one.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        The file to add the container to. It is written to its "behavior" processing module.
    keypoint_data : dict
        Maps keypoint name to ``(positions, confidence)``, as for :func:`_add_pose_estimation_to_nwbfile`.
    timestamps : numpy.ndarray
        One time in seconds per frame, shared by every series.
    metadata : dict
        Metadata in the dict-based shape, carrying the top-level ``"Pose"`` and ``"Devices"`` registries.
    metadata_key : str
        The key of the container entry to write, within ``metadata["Pose"]["MultiCameraPoseEstimations"]``.
    """
    from ndx_pose import MultiCameraPoseEstimation, PoseEstimation

    pose_metadata = metadata.get("Pose", {})
    containers_metadata = pose_metadata.get("MultiCameraPoseEstimations", {})
    if metadata_key not in containers_metadata:
        raise ValueError(
            f"metadata_key '{metadata_key}' was not found in metadata['Pose']['MultiCameraPoseEstimations'] "
            f"(available keys: {list(containers_metadata)})."
        )
    container_entry = containers_metadata[metadata_key]
    container_name = container_entry.get("name", "MultiCameraPoseEstimation")

    behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="processed behavioral data")
    if container_name in behavior_module.data_interfaces:
        raise ValueError(f"The nwbfile already contains a data interface with the name '{container_name}'.")

    skeleton = _get_or_build_skeleton(
        nwbfile=nwbfile,
        behavior_module=behavior_module,
        pose_metadata=pose_metadata,
        skeleton_metadata_key=container_entry.get("skeleton_metadata_key"),
    )

    placeholders = _get_pose_metadata_placeholders(keypoint_names=keypoint_data)
    pose_estimation_series = _build_pose_estimation_series(
        keypoint_data=keypoint_data,
        timestamps=timestamps,
        series_entries=container_entry.get("PoseEstimationSeries", {}),
        placeholder_series=placeholders["Pose"]["PoseEstimations"][DEFAULT_METADATA_KEY]["PoseEstimationSeries"],
    )

    camera_entries = pose_metadata.get("PoseEstimations", {})
    camera_pose_estimations = []
    for camera_metadata_key in container_entry.get("pose_estimation_metadata_keys") or []:
        if camera_metadata_key not in camera_entries:
            raise ValueError(
                f"pose_estimation_metadata_keys entry '{camera_metadata_key}' was not found in "
                f"metadata['Pose']['PoseEstimations'] (available keys: {list(camera_entries)})."
            )
        camera_entry = camera_entries[camera_metadata_key]
        camera_kwargs = dict(name=camera_entry.get("name", "PoseEstimation"))
        device_metadata_key = camera_entry.get("device_metadata_key")
        if device_metadata_key is not None:
            camera_kwargs["device"] = _add_device_to_nwbfile(
                nwbfile=nwbfile, metadata=metadata, metadata_key=device_metadata_key
            )
        source_video_metadata_key = camera_entry.get("source_video_metadata_key")
        if source_video_metadata_key is not None:
            camera_kwargs["source_video"] = _resolve_image_series(
                nwbfile=nwbfile,
                metadata=metadata,
                metadata_key=source_video_metadata_key,
                field="source_video_metadata_key",
            )
        camera_pose_estimations.append(PoseEstimation(**camera_kwargs))

    container_kwargs = dict(
        name=container_name,
        pose_estimation_series=pose_estimation_series,
        pose_estimations=camera_pose_estimations,
        skeleton=skeleton,
    )
    for field in ("description", "source_software", "source_software_version", "scorer"):
        if container_entry.get(field) is not None:
            container_kwargs[field] = container_entry[field]
    behavior_module.add(MultiCameraPoseEstimation(**container_kwargs))

    _add_skeleton_to_behavior_module(behavior_module=behavior_module, skeleton=skeleton)


def _get_or_build_skeleton(*, nwbfile: NWBFile, behavior_module, pose_metadata: dict, skeleton_metadata_key):
    """Return the ``Skeleton`` a container entry points at, reusing one already in the file by name.

    ``None`` when the entry names no skeleton. A newly built skeleton is not added to the file here; that
    happens after the container, through :func:`_add_skeleton_to_behavior_module`.
    """
    from ndx_pose import Skeleton

    if skeleton_metadata_key is None:
        return None

    skeletons_metadata = pose_metadata.get("Skeletons", {})
    if skeleton_metadata_key not in skeletons_metadata:
        raise ValueError(
            f"skeleton_metadata_key '{skeleton_metadata_key}' was not found in "
            f"metadata['Pose']['Skeletons'] (available keys: {list(skeletons_metadata)})."
        )
    skeleton_entry = skeletons_metadata[skeleton_metadata_key]
    skeleton_name = skeleton_entry["name"]
    existing_skeletons = (
        behavior_module["Skeletons"].skeletons if "Skeletons" in behavior_module.data_interfaces else {}
    )
    if skeleton_name in existing_skeletons:
        existing_skeleton = existing_skeletons[skeleton_name]
        # Reuse by name is how containers share a skeleton, which only holds if it is the same skeleton.
        if list(existing_skeleton.nodes[:]) != list(skeleton_entry["nodes"]):
            raise ValueError(
                f"The file already has a skeleton named '{skeleton_name}' with different nodes. Give the "
                f"skeleton at metadata['Pose']['Skeletons']['{skeleton_metadata_key}'] a distinct 'name'."
            )
        return existing_skeleton

    # ndx-pose stores one subject per file, so the file's subject is the pose subject. The entry's
    # optional "subject" names an individual within the source, and a mismatch means these keypoints
    # belong to someone other than the file's subject, so no link is made.
    subject = None
    if nwbfile.subject is not None:
        skeleton_subject = skeleton_entry.get("subject")
        if skeleton_subject is None or skeleton_subject == nwbfile.subject.subject_id:
            subject = nwbfile.subject
    edges = skeleton_entry.get("edges")
    return Skeleton(
        name=skeleton_name,
        nodes=skeleton_entry["nodes"],
        # Node indices and video dimensions are small and non-negative, and ndx-pose specifies
        # both as uint8. Writing them as an unsigned type avoids an hdmf conversion warning.
        edges=np.asarray(edges, dtype="uint16") if edges is not None and len(edges) else None,
        subject=subject,
    )


def _build_pose_estimation_series(
    *,
    keypoint_data: dict[str, tuple[np.ndarray, np.ndarray | None]],
    timestamps: np.ndarray,
    series_entries: dict,
    placeholder_series: dict,
) -> list:
    """Build one ``PoseEstimationSeries`` per keypoint, all sharing ``timestamps``."""
    from ndx_pose import PoseEstimationSeries

    timestamps = np.asarray(timestamps).astype("float64", copy=False)
    if timestamps.ndim != 1:
        raise ValueError("Pose timestamps must be a one-dimensional array with one time per sample.")
    for keypoint_name, (positions, _) in keypoint_data.items():
        if len(positions) != len(timestamps):
            raise ValueError(
                f"Keypoint '{keypoint_name}' has {len(positions)} samples but {len(timestamps)} timestamps. "
                "Every keypoint in a pose container must have one sample per timestamp."
            )
    rate = calculate_regular_series_rate(timestamps)
    if rate is None:
        timing_kwargs = dict(timestamps=timestamps)
    else:
        timing_kwargs = dict(rate=rate, starting_time=timestamps[0])

    pose_estimation_series = []
    for keypoint_name, (positions, confidence) in keypoint_data.items():
        series_entry = series_entries.get(keypoint_name, {})
        series_kwargs = dict(
            timing_kwargs,
            name=series_entry.get("name", placeholder_series[keypoint_name]["name"]),
            description=series_entry.get("description", f"Pose estimation series for {keypoint_name}."),
            data=positions,
            reference_frame=series_entry.get("reference_frame", "unknown"),
        )
        if confidence is not None:
            series_kwargs["confidence"] = confidence
        for field in ("unit", "confidence_definition"):
            if series_entry.get(field) is not None:
                series_kwargs[field] = series_entry[field]

        pose_estimation_series.append(PoseEstimationSeries(**series_kwargs))
        # Every series in a container is a keypoint of the same animal on the same frames, so the times
        # are identical by construction. Handing the first series as the ``timestamps`` of the rest is
        # pynwb's idiom for that and writes a link instead of another copy of the vector.
        if rate is None:
            timing_kwargs = dict(timestamps=pose_estimation_series[0])

    return pose_estimation_series


def _add_skeleton_to_behavior_module(*, behavior_module, skeleton) -> None:
    """File ``skeleton`` under the behavior module's ``Skeletons``, unless it is ``None`` or already there."""
    from ndx_pose import Skeletons

    if skeleton is None:
        return
    if "Skeletons" not in behavior_module.data_interfaces:
        behavior_module.add(Skeletons(skeletons=[skeleton]))
    elif skeleton.name not in behavior_module["Skeletons"].skeletons:
        behavior_module["Skeletons"].add_skeletons(skeleton)
