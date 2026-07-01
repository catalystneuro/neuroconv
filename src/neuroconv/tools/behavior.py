"""Tool-agnostic helpers for behavioral-segmentation output (the ``ndx-ethogram`` extension)."""

import numpy as np

from .signal_processing import run_length_encode_labels


def build_ethogram_from_labels(
    *,
    labels: np.ndarray,
    timestamps: np.ndarray,
    bouts_name: str,
    labeling_method: str,
    frame_period: float | None = None,
    bouts_description: str = "Behavioral segmentation output as run-length-encoded bouts.",
    source_software: str | None = None,
    annotator: str | None = None,
    parameters: str | None = None,
    source=None,
    source_pose=None,
    source_video=None,
    catalogue_name: str | None = None,
    catalogue_description: str = "Behavior catalogue (coding scheme): one row per behavior id.",
    class_ids=None,
    class_definition: str = "",
    category_labels: np.ndarray | None = None,
    exclusive: bool | None = None,
):
    """Build an ``EthogramBouts`` table (and optional ``Ethogram`` catalogue) from per-frame labels.

    Tool-agnostic: run-length-encodes any per-frame integer labeling (VAME motifs, keypoint-MoSeq
    syllables, B-SOiD clusters, DeepEthogram/SimBA behaviors) into one curated bout table. The
    faithful per-frame producer is referenced via ``source``; nothing here depends on a specific
    tool extension.

    Parameters
    ----------
    labels : np.ndarray
        1D per-frame integer labels.
    timestamps : np.ndarray
        Frame times in seconds, same length as ``labels``.
    bouts_name : str
        Name of the ``EthogramBouts`` container.
    labeling_method : str
        ``"manual"``, ``"automated"``, or ``"curated"``.
    frame_period : float, optional
        Frame duration in seconds; defaults to the median inter-frame interval.
    bouts_description, source_software, annotator, parameters : str, optional
        Provenance written onto the ``EthogramBouts`` group.
    source, source_pose, source_video : optional
        Objects the bouts were derived from (the faithful producer, an ``ndx-pose``
        ``PoseEstimation``, and an ``ImageSeries`` video), linked from the bout table.
    catalogue_name : str, optional
        If given, also build an ``Ethogram`` catalogue with this name (one row per behavior id) and
        link it from the bouts. If ``None``, no catalogue is built.
    catalogue_description, class_definition : str
        Catalogue table description and the per-row ``definition`` text.
    class_ids : iterable of int, optional
        Full label space to enumerate in the catalogue (e.g. ``range(n_clusters)`` to include ids
        absent this session). Defaults to the unique labels present.
    category_labels : np.ndarray, optional
        A second per-frame integer labeling (e.g. VAME communities). When given, the modal category
        per class is recorded in the catalogue's ``category`` column.
    exclusive : bool, optional
        Whether the scheme is a single-label partition (recorded on the catalogue).

    Returns
    -------
    tuple
        ``(EthogramBouts, Ethogram | None)``. Both must be added to the NWB file by the caller.
    """
    from ndx_ethogram import Ethogram, EthogramBouts

    labels = np.asarray(labels)

    catalogue = None
    if catalogue_name is not None:
        # Modal category per class, when a second per-frame labeling is supplied.
        class_to_category: dict[int, int] = {}
        if category_labels is not None:
            category_labels = np.asarray(category_labels)
            for class_id in np.unique(labels):
                values, counts = np.unique(category_labels[labels == class_id], return_counts=True)
                if values.size:
                    class_to_category[int(class_id)] = int(values[counts.argmax()])
        has_category = len(class_to_category) > 0

        catalogue = Ethogram(name=catalogue_name, description=catalogue_description, exclusive=exclusive)
        enumerated_ids = class_ids if class_ids is not None else [int(value) for value in np.unique(labels)]
        for class_id in enumerated_ids:
            row = dict(
                behavior=str(int(class_id)),
                definition=class_definition,
                native_code=int(class_id),
            )
            if has_category:
                category_value = class_to_category.get(int(class_id))
                row["category"] = "" if category_value is None else str(category_value)
            catalogue.add_row(**row)

    bouts = EthogramBouts(
        name=bouts_name,
        description=bouts_description,
        labeling_method=labeling_method,
        source_software=source_software,
        annotator=annotator,
        parameters=parameters,
        source=source,
        source_pose=source_pose,
        source_video=source_video,
        ethogram=catalogue,
    )
    for start_time, stop_time, label in run_length_encode_labels(labels, timestamps, frame_period):
        bouts.add_row(start_time=start_time, stop_time=stop_time, label=str(label))

    return bouts, catalogue
