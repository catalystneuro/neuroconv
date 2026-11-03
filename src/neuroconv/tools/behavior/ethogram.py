"""Shared writer for behavioral bouts and the behavior catalogue they draw from (the ``ndx-ethogram`` extension)."""

import numpy as np
from hdmf.common import MeaningsTable
from pynwb import NWBFile

from ..nwb_helpers import get_module
from ..signal_processing import _run_length_encode_labels


def _add_ethogram_to_nwbfile(
    nwbfile: NWBFile,
    *,
    start_times,
    stop_times,
    labels,
    behaviors: list[dict],
    ethogram_metadata: dict,
    labeling_method: str,
    exclusive: bool | None = None,
    source_software: str | None = None,
    annotator: str | None = None,
    parameters: str | None = None,
    source=None,
    source_pose=None,
    source_video=None,
    behavior_columns: dict[str, dict] | None = None,
    bout_columns: dict[str, dict] | None = None,
    column_meanings: dict[str, dict] | None = None,
    extend_bouts: bool = False,
) -> None:
    """Add an ``Ethogram`` catalogue and the ``EthogramBouts`` scored against it to the behavior module.

    The bouts arrive already formed, so a producer that scored intervals (BORIS, EthoVision manual scoring)
    and one that labelled every frame (VAME, keypoint-MoSeq, after run-length encoding) write through the
    same call. The catalogue holds one row per behavior and the bouts table one row per bout, linked to it.

    The catalogue is looked up by name and extended where the file already holds it, which is how several
    interfaces share one: the observations of one BORIS project, or the subjects scored in one EthoVision
    arena. A behavior already catalogued is not added again and must keep its ``behavior_type``. The bouts
    table is new unless ``extend_bouts`` is set.

    Parameters
    ----------
    nwbfile : NWBFile
        The NWB file to add the ethogram to.
    start_times, stop_times : array-like of float
        The start and stop time of each bout, in seconds.
    labels : array-like of str
        The behavior of each bout, matching the ``behavior`` of a catalogue row.
    behaviors : list of dict
        The catalogue rows, one per behavior: ``behavior`` and ``definition``, optionally ``behavior_type``,
        ``native_code`` and ``category``, and a value for each column in ``behavior_columns``.
    ethogram_metadata : dict
        The ``name`` and ``description`` of each object, as ``{"Ethogram": {...}, "EthogramBouts": {...}}``,
        the shape of an entry in ``metadata["Behavior"]["Ethograms"]``.
    labeling_method : str
        ``"manual"``, ``"automated"``, or ``"curated"``.
    exclusive : bool, optional
        Whether the scheme is a single-label partition (recorded on the catalogue).
    source_software, annotator, parameters : str, optional
        Provenance written onto the ``EthogramBouts`` group.
    source, source_pose, source_video : optional
        Objects the bouts were derived from (the faithful producer, an ``ndx-pose``
        ``PoseEstimation``, and an ``ImageSeries`` video), linked from the bout table.
    behavior_columns : dict, optional
        Extra catalogue columns, as ``{name: {"description": str, "index": bool | int}}``. ``index`` makes
        the column ragged, as in ``DynamicTable.add_column``.
    bout_columns : dict, optional
        Extra per-bout columns, as ``{name: {"description": str, "data": array-like, "index": bool}}``, with
        one value per bout in ``data``.
    column_meanings : dict, optional
        A ``MeaningsTable`` for a bouts column, ``label`` included, as
        ``{name: {"description": str, "meanings": {value: meaning}}}``. A column with no meanings gets none.
    extend_bouts : bool, default: False
        Whether to append to an ``EthogramBouts`` of the same name already in the file, which is how the
        subjects scored in one EthoVision arena share one table. Otherwise that name already in the file
        raises.
    """
    from ndx_ethogram import Ethogram, EthogramBouts

    behavior_columns = behavior_columns or {}
    bout_columns = bout_columns or {}
    column_meanings = column_meanings or {}
    behavior_module = get_module(nwbfile=nwbfile, name="behavior")

    catalogue_metadata = ethogram_metadata["Ethogram"]
    catalogue = behavior_module.data_interfaces.get(catalogue_metadata["name"])
    if catalogue is None:
        catalogue = Ethogram(
            name=catalogue_metadata["name"], description=catalogue_metadata["description"], exclusive=exclusive
        )
        for name, column in behavior_columns.items():
            catalogue.add_column(name=name, description=column["description"], index=column.get("index", False))
        behavior_module.add(catalogue)
    elif not isinstance(catalogue, Ethogram):
        raise TypeError(f"Behavior object '{catalogue.name}' exists but is not an Ethogram.")

    catalogued_behaviors = list(catalogue["behavior"].data)
    catalogued_types = (
        list(catalogue["behavior_type"].data)
        if "behavior_type" in catalogue.colnames
        else [None] * len(catalogued_behaviors)
    )
    behavior_types = dict(zip(catalogued_behaviors, catalogued_types))
    for row in behaviors:
        behavior = row["behavior"]
        if behavior in behavior_types:
            if behavior_types[behavior] != row.get("behavior_type"):
                raise ValueError(
                    f"Behavior '{behavior}' is already catalogued in '{catalogue.name}' as "
                    f"'{behavior_types[behavior]}', not '{row.get('behavior_type')}'."
                )
            continue
        catalogue.add_row(**row)
        behavior_types[behavior] = row.get("behavior_type")

    # A producer can hold no bout at all, a scheme of point behaviors or a session nobody finished. The
    # catalogue still says what could have been scored; an empty interval table would say nothing more.
    if len(start_times) == 0:
        return

    bouts_metadata = ethogram_metadata["EthogramBouts"]
    bouts = behavior_module.data_interfaces.get(bouts_metadata["name"]) if extend_bouts else None
    if bouts is None:
        bouts = EthogramBouts(
            name=bouts_metadata["name"],
            description=bouts_metadata["description"],
            labeling_method=labeling_method,
            source_software=source_software,
            annotator=annotator,
            parameters=parameters,
            source=source,
            source_pose=source_pose,
            source_video=source_video,
            ethogram=catalogue,
        )
        for name, column in bout_columns.items():
            bouts.add_column(name=name, description=column["description"], index=column.get("index", False))
        behavior_module.add(bouts)
    elif not isinstance(bouts, EthogramBouts):
        raise TypeError(f"Behavior object '{bouts.name}' exists but is not an EthogramBouts table.")

    for index in range(len(start_times)):
        bouts.add_interval(
            start_time=start_times[index],
            stop_time=stop_times[index],
            label=labels[index],
            **{name: column["data"][index] for name, column in bout_columns.items()},
        )

    for name, meanings_specification in column_meanings.items():
        if not meanings_specification["meanings"]:
            continue
        meanings_table = MeaningsTable(target=bouts[name], description=meanings_specification["description"])
        for value, meaning in meanings_specification["meanings"].items():
            meanings_table.add_row(value=value, meaning=meaning)
        bouts.add_meanings_table(meanings_table)


def _get_bouts_and_behaviors_from_labels(
    *,
    labels: np.ndarray,
    timestamps: np.ndarray,
    frame_period: float | None = None,
    class_ids=None,
    class_definition: str = "",
    category_labels: np.ndarray | None = None,
) -> dict:
    """Run-length-encode per-frame labels into the bouts and catalogue rows ``_add_ethogram_to_nwbfile`` takes.

    Tool-agnostic: any per-frame integer labeling (VAME motifs, keypoint-MoSeq syllables, B-SOiD clusters,
    DeepEthogram/SimBA behaviors) becomes one bout per maximal run of a label, and one catalogue row per
    behavior id, with the id as text in ``behavior`` and as an integer in ``native_code``.

    Parameters
    ----------
    labels : np.ndarray
        1D per-frame integer labels.
    timestamps : np.ndarray
        Frame times in seconds, same length as ``labels``.
    frame_period : float, optional
        Frame duration in seconds; defaults to the median inter-frame interval.
    class_ids : iterable of int, optional
        Full label space to enumerate in the catalogue (e.g. ``range(n_clusters)`` to include ids
        absent this session). Defaults to the unique labels present.
    class_definition : str
        The per-row ``definition`` text.
    category_labels : np.ndarray, optional
        A second per-frame integer labeling (e.g. VAME communities). When given, the modal category
        per class is recorded in the catalogue's ``category`` column.

    Returns
    -------
    dict
        ``start_times``, ``stop_times``, ``labels`` and ``behaviors``, to pass on to ``_add_ethogram_to_nwbfile``.
    """
    labels = np.asarray(labels)

    # Modal category per class, when a second per-frame labeling is supplied.
    class_to_category: dict[int, int] = {}
    if category_labels is not None:
        category_labels = np.asarray(category_labels)
        for class_id in np.unique(labels):
            values, counts = np.unique(category_labels[labels == class_id], return_counts=True)
            if values.size:
                class_to_category[int(class_id)] = int(values[counts.argmax()])
    has_category = len(class_to_category) > 0

    behaviors = []
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
        behaviors.append(row)

    runs = _run_length_encode_labels(labels, timestamps, frame_period)
    return dict(
        start_times=[start_time for start_time, _, _ in runs],
        stop_times=[stop_time for _, stop_time, _ in runs],
        labels=[str(label) for _, _, label in runs],
        behaviors=behaviors,
    )
