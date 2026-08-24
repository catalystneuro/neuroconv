from dataclasses import dataclass

import numpy as np
from pynwb import NWBFile, TimeSeries
from pynwb.epoch import TimeIntervals
from pynwb.icephys import (
    CurrentClampSeries,
    CurrentClampStimulusSeries,
    IZeroClampSeries,
    VoltageClampSeries,
    VoltageClampStimulusSeries,
)

from .nwb_helpers import _add_device_to_nwbfile
from ..utils import DeepDict, calculate_regular_series_rate

# The key under which the default (placeholder) entries are registered. An interface re-keys these to its own
# file-derived keys; mirrors the ophys ``default_metadata_key``.
DEFAULT_METADATA_KEY = "default_metadata_key"

# clamp mode -> NWB response / stimulus classes. Shared icephys knowledge (not Axon-specific): any icephys
# interface can map a clamp mode to the right pynwb series types.
_RESPONSE_CLASS = {
    "voltage_clamp": VoltageClampSeries,
    "current_clamp": CurrentClampSeries,
    "izero": IZeroClampSeries,
}
_STIMULUS_CLASS = {
    "voltage_clamp": VoltageClampStimulusSeries,
    "current_clamp": CurrentClampStimulusSeries,
}


@dataclass
class _IcephysSeriesData:
    """One patch-clamp series before it is materialized as an NWB object."""

    data: np.ndarray
    timestamps: np.ndarray
    conversion: float
    offset: float = 0.0


def _add_patch_clamp_series_to_nwbfile(
    nwbfile: NWBFile,
    metadata: dict,
    series_metadata_key: str,
    series_data: _IcephysSeriesData,
    electrode,
    mode: str,
    is_stimulus: bool,
):
    """Construct and add one response or stimulus series from an icephys data record."""
    metadata_registry = "PatchClampStimulusSeries" if is_stimulus else "PatchClampSeries"
    series_metadata = metadata["Icephys"][metadata_registry][series_metadata_key]
    series_class = _STIMULUS_CLASS[mode] if is_stimulus else _RESPONSE_CLASS[mode]
    series_kwargs = dict(
        name=series_metadata["name"],
        data=series_data.data,
        electrode=electrode,
        conversion=series_data.conversion,
        offset=series_data.offset,
        gain=np.nan,
        description=series_metadata["description"],
    )
    rate = calculate_regular_series_rate(series=series_data.timestamps)
    if rate is not None:
        series_kwargs.update(starting_time=float(series_data.timestamps[0]), rate=rate)
    else:
        series_kwargs.update(timestamps=series_data.timestamps)

    series = series_class(**series_kwargs)
    if is_stimulus:
        nwbfile.add_stimulus(series)
    else:
        nwbfile.add_acquisition(series)
    return series


# NWB requires a `stimulus_type` on every SequentialRecordings entry, so a source that describes none still has
# to put a string there. It is written only at that level: an interface with nothing to say omits the column from
# the recordings table entirely rather than filling every row with a placeholder.
_UNDESCRIBED_STIMULUS_TYPE = "not described"

# What a run-level column holds for a run that did not state a value, once a sibling run has forced the column
# to exist. Empty rather than `_UNDESCRIBED_STIMULUS_TYPE`, since the recordings table should carry only what a
# source or caller actually said; the readable placeholder is added once, at the sequential level.
_UNSTATED_RUN_LEVEL_VALUE = ""

# The run-level columns the interfaces denormalize onto every recordings row, and that
# `_build_icephys_hierarchical_tables` reads back to build the upper tables. Shared so the two halves of that
# contract cannot drift: one function writes these columns, the other consumes them.
_RUN_LEVEL_COLUMN_DESCRIPTIONS = {
    "sequence": "Run identity grouping rows into a sequential recording (shared by the run's sweeps).",
    "stimulus_type": "Stimulus type of the run, carried up to its sequential recording when aggregated.",
    "repetition": "Repetition label grouping sequential recordings into a repetition.",
    "condition": "Experimental condition label grouping repetitions.",
}


def _get_icephys_metadata_placeholders() -> DeepDict:
    """
    Default intracellular-electrophysiology metadata, keyed by a single ``default_metadata_key``.

    Mirrors the ophys placeholder pattern (`_get_ophys_metadata_placeholders`): the icephys metadata shape is
    defined once here so it is not re-spelled at each call site, and only the fields the NWB schema strictly
    requires carry a placeholder value, so as little metadata as possible is made up. An interface's
    ``get_metadata`` seeds its entries from these defaults and overrides the data-derived fields (the
    channel-derived names, the file-derived keys); a field it leaves untouched falls back to the
    default here, and a future schema-required field added here propagates to every interface automatically.
    Each call returns an independent copy.

    Structure
    ---------
    - ``Devices[key]``: the device an electrode records through, for a file that names none. Only ``name``
      is here, the one field NWB requires of a ``Device``, and it names no instrument class: published
      files put an amplifier, a digitizer, a rig or the pipette itself behind this link, so a default
      cannot pick one. An electrode links its own device with ``device_metadata_key``; an electrode that
      names none gets this one.
    - ``Icephys.IntracellularElectrodes[key]``: the patch electrode. ``description`` is schema-required,
      so it carries a ``"no description"`` placeholder.
    - ``Icephys.PatchClampSeries[key]``: the response series, linked to its electrode by
      ``electrode_metadata_key``.
    - ``Icephys.PatchClampStimulusSeries[key]``: the optional paired stimulus, in a parallel registry at the
      SAME key as its response. It reuses the response's electrode, so it carries no ``electrode_metadata_key``.
    """
    metadata = DeepDict()
    metadata["Devices"] = {
        DEFAULT_METADATA_KEY: {
            "name": "PlaceholderIntracellularDevice",
        },
    }
    metadata["Icephys"] = {
        "IntracellularElectrodes": {
            DEFAULT_METADATA_KEY: {
                "name": "IntracellularElectrode",
                "description": "no description",
            }
        },
        "PatchClampSeries": {
            DEFAULT_METADATA_KEY: {
                "name": "PatchClampSeries",
                "electrode_metadata_key": DEFAULT_METADATA_KEY,
            }
        },
        "PatchClampStimulusSeries": {
            DEFAULT_METADATA_KEY: {
                "name": "PatchClampStimulusSeries",
            }
        },
    }
    return metadata


def _add_intracellular_electrode_to_nwbfile(nwbfile: NWBFile, metadata: dict, electrode_metadata_key: str):
    """Return the intracellular electrode named by the metadata entry ``electrode_metadata_key``, reusing an
    existing one by name or creating it (and its device) if absent.

    Resolves the electrode entry, follows its ``device_metadata_key`` link where it states one, and fills any
    schema-required field the entry omits from :func:`_get_icephys_metadata_placeholders` (defaults are applied
    here, at write time, so an interface's ``get_metadata`` only returns what the source provides). The electrode
    dedups by ``name``, and so does the device, so several interfaces pointing at one entry share a single object.
    """
    placeholders = _get_icephys_metadata_placeholders()
    electrode_metadata = {
        **placeholders["Icephys"]["IntracellularElectrodes"][DEFAULT_METADATA_KEY],
        **metadata["Icephys"]["IntracellularElectrodes"][electrode_metadata_key],
    }

    name = electrode_metadata["name"]
    if name in nwbfile.icephys_electrodes:
        return nwbfile.icephys_electrodes[name]

    # An electrode naming no device gets the placeholder: a plain Device carrying the one field NWB
    # requires, built here rather than through the registry writer, since there is no registry entry to
    # key it against. Reused by name, so several electrodes naming no device land on one device.
    device_metadata_key = electrode_metadata.get("device_metadata_key")
    if device_metadata_key is None:
        placeholder_device_metadata = placeholders["Devices"][DEFAULT_METADATA_KEY]
        placeholder_device_name = placeholder_device_metadata["name"]
        if placeholder_device_name not in nwbfile.devices:
            nwbfile.create_device(**placeholder_device_metadata)
        device = nwbfile.devices[placeholder_device_name]
    else:
        device = _add_device_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key=device_metadata_key)
    # Optional IntracellularElectrode fields passed through from metadata if present.
    electrode_fields = ("cell_id", "location", "slice", "resistance", "seal", "filtering", "initial_access_resistance")
    extra_fields = {field: electrode_metadata[field] for field in electrode_fields if field in electrode_metadata}
    return nwbfile.create_icephys_electrode(
        name=name,
        description=electrode_metadata["description"],
        device=device,
        **extra_fields,
    )


def _validate_grouping_levels(repetitions: list, conditions: list) -> None:
    """Require the optional grouping levels to be consistent across the runs before any rows are written.

    A `condition` without a `repetition` is allowed (the aggregator defaults each run to its own repetition,
    identity grouping). Only cross-run consistency is enforced: a level set on some runs but not others would
    write its column inconsistently across rows, which the intracellular-recordings table can't represent. Run
    before writing so a bad combination fails clearly here, rather than mid-write with a cryptic pynwb error.
    """
    if any(value is not None for value in repetitions) and not all(value is not None for value in repetitions):
        raise ValueError("`repetition` must be provided on all interfaces or none of them.")
    if any(value is not None for value in conditions) and not all(value is not None for value in conditions):
        raise ValueError("`condition` must be provided on all interfaces or none of them.")


def _add_intracellular_recordings_to_nwbfile(
    nwbfile: NWBFile,
    *,
    electrode,
    response_series,
    sweep_sample_ranges: list,
    sequence: str,
    stimulus_series=None,
    stimulus_type: str | None = None,
    repetition: str | None = None,
    condition: str | None = None,
) -> None:
    """
    Write one ``IntracellularRecordings`` row per sweep, tagged with this run's run-level columns.

    Each row addresses the run's continuous response series by the sweep's ``(start_index, count)`` range, and
    carries the run-level values denormalized onto it, so the file stays information-complete even before the
    upper tables exist. The columns are the ones :func:`_build_icephys_hierarchical_tables` reads back:
    ``sequence`` always, and ``stimulus_type`` / ``repetition`` / ``condition`` when the source or caller stated
    them.

    A run-level column belongs to the table, not to the interface that introduced it, so an optional value has
    to stay representable when runs disagree about whether they have one:

    - the column already exists and this run has no value -> write ``_UNSTATED_RUN_LEVEL_VALUE`` on these rows,
    - the column is introduced here and rows already exist -> backfill those rows with the same,
    - the column does not exist and no run has a value -> it is never created.

    Without both of the first two, a converter combining a run that stated a ``stimulus_type`` with one that did
    not dies inside hdmf mid-write, with an error that names neither the argument nor the run it came from and
    that changes with declaration order. ``repetition`` and ``condition`` cannot reach that state, since
    :func:`_validate_grouping_levels` requires them on all runs or none (they are grouping keys, so a partial
    one has no meaning); ``stimulus_type`` is purely descriptive, so a run that did not state one is a real
    state rather than a mistake.

    Parameters
    ----------
    nwbfile : NWBFile
        The file to write the rows into.
    electrode : IntracellularElectrode
        The electrode every sweep of this run was recorded through.
    response_series : PatchClampSeries
        The run's continuous response, which the rows address by index range.
    sweep_sample_ranges : list of tuple of int
        One ``(start_index, count)`` per sweep, into ``response_series``.
    sequence : str
        The run identity shared by these sweeps, grouped on to build a ``SequentialRecordings`` entry.
    stimulus_series : PatchClampStimulusSeries, optional
        The run's stimulus, addressed by the same ranges, when the source carries one.
    stimulus_type : str, optional
        What kind of run this was. Omitted rather than given a placeholder when the source stated none.
    repetition : str, optional
        Label grouping this run's sequential recording into a repetition.
    condition : str, optional
        Label grouping this run's repetition into an experimental condition.
    """
    columns = {"sequence": sequence}
    for name, value in (("stimulus_type", stimulus_type), ("repetition", repetition), ("condition", condition)):
        if value is not None:
            columns[name] = value

    table = nwbfile.get_intracellular_recordings()
    for name in _RUN_LEVEL_COLUMN_DESCRIPTIONS:
        if name in table.colnames:
            columns.setdefault(name, _UNSTATED_RUN_LEVEL_VALUE)
    for name in columns:
        if name not in table.colnames:
            # `data` covers the rows written before this column existed; empty, so a no-op, for the first run.
            table.add_column(
                name=name,
                description=_RUN_LEVEL_COLUMN_DESCRIPTIONS[name],
                data=[_UNSTATED_RUN_LEVEL_VALUE] * len(table),
            )

    for start_index, count in sweep_sample_ranges:
        keyword_arguments = dict(
            electrode=electrode,
            response=response_series,
            response_start_index=start_index,
            response_index_count=count,
        )
        if stimulus_series is not None:
            keyword_arguments.update(
                stimulus=stimulus_series, stimulus_start_index=start_index, stimulus_index_count=count
            )
        keyword_arguments.update(columns)
        nwbfile.add_intracellular_recording(**keyword_arguments)


def _disambiguate_run_labels(paths: list) -> dict:
    """Map each path to the shortest trailing path-suffix that is unique among ``paths``.

    A bare stem when it's unique (``0000.abf`` -> ``"0000"``), parent-folder-prefixed only on a clash
    (``cellA/0000.abf`` / ``cellB/0000.abf`` -> ``"cellA_0000"`` / ``"cellB_0000"``), walking further up only as
    needed. Used to give each distinct ABF file a unique, human-readable run label when combining several whose
    Clampex-assigned filenames (``0000.abf`` per folder) collide. ``paths`` must be distinct.
    """
    parts_per_path = [path.with_suffix("").parts for path in paths]
    labels = {}
    for index, path in enumerate(paths):
        parts = parts_per_path[index]
        depth = 1
        while True:
            label = "_".join(parts[-depth:])
            clashes = any(
                other != index and "_".join(parts_per_path[other][-depth:]) == label for other in range(len(paths))
            )
            if not clashes or depth == len(parts):
                labels[path] = label
                break
            depth += 1
    return labels


def _build_icephys_hierarchical_tables(nwbfile: NWBFile) -> None:
    """
    Build the icephys hierarchy tables from the grouping columns on the intracellular-recordings table.

    Reads, per row: the response's sweep timing, ``sequence``, and the optional ``stimulus_type`` /
    ``repetition`` / ``condition`` columns, then groups upward:

    - rows of one ``sequence`` covering the same span of time -> one ``SimultaneousRecordings`` entry,
    - the simultaneous entries of one ``sequence`` -> one ``SequentialRecordings`` entry (with its stimulus type),
    - the sequentials of one ``repetition`` -> one ``Repetitions`` entry (present, or identity per sequence
      when a ``condition`` needs a repetitions rung beneath it),
    - the repetitions of one ``condition`` -> one ``ExperimentalConditions`` entry (only if the column is present).

    Simultaneity is decided on the sweep's resolved start and stop time rather than on its ``(start_index,
    count)`` range, because an index is only a proxy for time while every series shares one clock origin. Two
    electrodes of a dual patch write two series that both start at index 0 and are genuinely simultaneous; an
    interface writing one series per sweep also produces rows that all start at index 0, and those are not. Only
    the resolved time separates the two cases, and it groups the dual patch correctly either way. This is the same
    notion of sweep identity :func:`_add_sweep_time_intervals_to_nwbfile` keys on, so the two projections of these
    rows cannot disagree.

    Each grouping value is constant within a sequence (a run), so the run-level attributes are read off any of
    its rows. When a ``repetition`` column is absent, each sequence is its own repetition (identity grouping,
    the same width-1 default ``SimultaneousRecordings`` uses for a single electrode), so a ``condition`` without
    a ``repetition`` still builds: it groups those identity repetitions. A ``stimulus_type`` column is likewise
    optional: NWB requires the field on the sequential recording, so a placeholder is supplied there when the
    source described none, but the recordings table is left without a column of repeated placeholders.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose ``intracellular_recordings`` rows (already written, carrying the columns above) are
        aggregated in place into the simultaneous / sequential / repetitions / experimental-conditions tables.
    """
    intracellular_recordings = nwbfile.intracellular_recordings
    if intracellular_recordings is None or len(intracellular_recordings) == 0:
        return

    column_names = intracellular_recordings.colnames
    responses = intracellular_recordings["responses"]["response"]
    sequences = intracellular_recordings["sequence"]
    stimulus_types = intracellular_recordings["stimulus_type"] if "stimulus_type" in column_names else None
    repetitions = intracellular_recordings["repetition"] if "repetition" in column_names else None
    conditions = intracellular_recordings["condition"] if "condition" in column_names else None

    # First pass: per sequence (in first-seen order), its timing groups and its run-level attributes.
    sequence_order: list = []
    timing_groups_by_sequence: dict = {}
    attributes_by_sequence: dict = {}
    for row_index in range(len(intracellular_recordings)):
        sequence_value = sequences[row_index]
        if sequence_value not in timing_groups_by_sequence:
            sequence_order.append(sequence_value)
            timing_groups_by_sequence[sequence_value] = {}
            attributes_by_sequence[sequence_value] = dict(
                stimulus_type=stimulus_types[row_index] if stimulus_types is not None else None,
                repetition=repetitions[row_index] if repetitions is not None else None,
                condition=conditions[row_index] if conditions is not None else None,
            )
        response_reference = responses[row_index]
        timing_key = _get_sweep_start_and_stop_time(
            series=response_reference.timeseries,
            start_index=response_reference.idx_start,
            count=response_reference.count,
        )
        timing_groups_by_sequence[sequence_value].setdefault(timing_key, []).append(row_index)

    # Simultaneous + sequential: one sequential per sequence.
    sequential_index_by_sequence: dict = {}
    for sequence_value in sequence_order:
        timing_groups = timing_groups_by_sequence[sequence_value]
        simultaneous_indices = [
            nwbfile.add_icephys_simultaneous_recording(recordings=timing_groups[timing_key])
            for timing_key in sorted(timing_groups)
        ]
        stimulus_type = attributes_by_sequence[sequence_value]["stimulus_type"]
        sequential_index_by_sequence[sequence_value] = nwbfile.add_icephys_sequential_recording(
            simultaneous_recordings=simultaneous_indices,
            # A run that stated none reaches here as `None` (no column at all) or as the unstated value (a
            # sibling run forced the column); both mean the same thing and get the one readable placeholder.
            stimulus_type=stimulus_type if stimulus_type else _UNDESCRIBED_STIMULUS_TYPE,
        )

    # The repetitions level is built when it was requested (a `repetition` column) or when `condition` needs a
    # rung beneath it. Absent both, the hierarchy terminates at SequentialRecordings.
    if repetitions is None and conditions is None:
        return

    # Repetitions group sequentials. With a `repetition` column, group by its label (keyed also by condition so
    # a label reused across conditions stays distinct). Without one, default to identity: each sequence is its
    # own repetition (the width-1 default Simultaneous uses for a single electrode).
    repetition_order: list = []
    sequentials_by_repetition: dict = {}
    condition_by_repetition: dict = {}
    for sequence_value in sequence_order:
        attributes = attributes_by_sequence[sequence_value]
        repetition_label = attributes["repetition"] if repetitions is not None else sequence_value
        repetition_key = (attributes["condition"], repetition_label)
        if repetition_key not in sequentials_by_repetition:
            repetition_order.append(repetition_key)
            sequentials_by_repetition[repetition_key] = []
            condition_by_repetition[repetition_key] = attributes["condition"]
        sequentials_by_repetition[repetition_key].append(sequential_index_by_sequence[sequence_value])

    repetition_index_by_key: dict = {}
    for repetition_key in repetition_order:
        repetition_index_by_key[repetition_key] = nwbfile.add_icephys_repetition(
            sequential_recordings=sequentials_by_repetition[repetition_key]
        )

    if conditions is None:
        return

    # Experimental conditions group repetitions.
    condition_order: list = []
    repetitions_by_condition: dict = {}
    for repetition_key in repetition_order:
        condition_value = condition_by_repetition[repetition_key]
        if condition_value not in repetitions_by_condition:
            condition_order.append(condition_value)
            repetitions_by_condition[condition_value] = []
        repetitions_by_condition[condition_value].append(repetition_index_by_key[repetition_key])

    for condition_value in condition_order:
        nwbfile.add_icephys_experimental_condition(repetitions=repetitions_by_condition[condition_value])


def _get_sweep_start_and_stop_time(series: TimeSeries, start_index: int, count: int) -> tuple[float, float]:
    """Return ``(start_time, stop_time)`` of the ``(start_index, count)`` sample range of ``series``.

    The stop time is the time of the range's LAST sample rather than one sample period past it, so consecutive
    sweeps of a gap-free recording never share an endpoint (which reads as an overlap to a consumer treating the
    intervals as closed). The cost is that a sweep's reported duration is short by one sample period.

    Both timing representations are handled because an icephys interface writes whichever fits its data: a
    uniform ``rate`` when the sweeps are contiguous, explicit ``timestamps`` when inter-sweep gaps make them
    irregular. The two endpoints are computed directly instead of through ``series.get_timestamps()``, which
    would materialize the whole timestamp array to read two values from it.
    """
    first_index = start_index
    last_index = start_index + count - 1
    if series.timestamps is not None:
        return float(series.timestamps[first_index]), float(series.timestamps[last_index])
    return (
        float(series.starting_time + first_index / series.rate),
        float(series.starting_time + last_index / series.rate),
    )


def _add_sweep_time_intervals_to_nwbfile(nwbfile: NWBFile, name: str = "sweeps") -> None:
    """
    Add a ``TimeIntervals`` table holding the start and stop time of every sweep in the file.

    The sweeps are already in the file, as ``(start_index, count)`` ranges into the response series on the
    intracellular-recordings table; this writes the same information in the form the rest of the NWB ecosystem
    reads intervals in, so a tool that knows nothing about the icephys tables (pynapple, for instance, which
    surfaces any ``TimeIntervals`` as an ``IntervalSet``) gets the sweeps for free. The index-based ranges stay
    the canonical representation, and this table is a projection of them written at conversion time.

    One row per distinct interval: the channels of a simultaneous recording (a dual patch, say) address the same
    sample range of their own series and so describe one sweep, not two. Rows are written in time order, since
    the recordings table is ordered by contributing interface rather than by time. When the recordings table
    carries the ``sequence`` column, it is copied over so each sweep still names the run it belongs to.

    Called once the intracellular-recordings table is complete, for the same reason the hierarchy tables are
    (see :func:`_build_icephys_hierarchical_tables`): each interface appends only its own rows.

    Parameters
    ----------
    nwbfile : NWBFile
        The file whose ``intracellular_recordings`` rows are read; the table is added to its ``intervals``.
    name : str, default: "sweeps"
        Name of the added ``TimeIntervals`` table, which is the handle downstream tools address it by.
    """
    intracellular_recordings = nwbfile.intracellular_recordings
    if intracellular_recordings is None or len(intracellular_recordings) == 0:
        return

    responses = intracellular_recordings["responses"]["response"]
    has_sequence_column = "sequence" in intracellular_recordings.colnames
    sequences = intracellular_recordings["sequence"] if has_sequence_column else None

    sequence_by_interval: dict = {}
    for row_index in range(len(intracellular_recordings)):
        response_reference = responses[row_index]
        interval = _get_sweep_start_and_stop_time(
            series=response_reference.timeseries,
            start_index=response_reference.idx_start,
            count=response_reference.count,
        )
        if interval not in sequence_by_interval:
            sequence_by_interval[interval] = sequences[row_index] if has_sequence_column else None

    sweeps = TimeIntervals(
        name=name,
        description="Start and stop time of each sweep, derived from the intracellular recordings table.",
    )
    if has_sequence_column:
        sweeps.add_column(name="sequence", description="Run the sweep belongs to (from the recordings table).")
    for start_time, stop_time in sorted(sequence_by_interval):
        row = dict(start_time=start_time, stop_time=stop_time)
        if has_sequence_column:
            row["sequence"] = sequence_by_interval[(start_time, stop_time)]
        # check_ragged=False: hdmf rescans the whole column on every add_row, making this quadratic in the
        # number of sweeps. Every cell here is a scalar, so the check can only ever return False.
        sweeps.add_row(**row, check_ragged=False)

    nwbfile.add_time_intervals(sweeps)
