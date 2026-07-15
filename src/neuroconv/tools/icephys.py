from pynwb import NWBFile
from pynwb.icephys import (
    CurrentClampSeries,
    CurrentClampStimulusSeries,
    IZeroClampSeries,
    VoltageClampSeries,
    VoltageClampStimulusSeries,
)

from ..utils import DeepDict

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


def _get_icephys_metadata_placeholders() -> DeepDict:
    """
    Default intracellular-electrophysiology metadata, keyed by a single ``default_metadata_key``.

    Mirrors the ophys placeholder pattern (`_get_ophys_metadata_placeholders`): the icephys metadata shape is
    defined once here so it is not re-spelled at each call site, and only the fields the NWB schema strictly
    requires carry a placeholder value, so as little metadata as possible is made up. An interface's
    ``get_metadata`` seeds its entries from these defaults and overrides the data-derived fields (the amplifier
    model, the channel-derived names, the file-derived keys); a field it leaves untouched falls back to the
    default here, and a future schema-required field added here propagates to every interface automatically.
    Each call returns an independent copy.

    Structure
    ---------
    - ``Devices[key]``: the amplifier. ``name`` only (``Device.description`` is optional, so none is invented).
    - ``Icephys.IntracellularElectrodes[key]``: the patch electrode, linked to its device by
      ``device_metadata_key``. ``description`` is schema-required, so it carries a ``"no description"``
      placeholder.
    - ``Icephys.PatchClampSeries[key]``: the response series, linked to its electrode by
      ``electrode_metadata_key``.
    - ``Icephys.PatchClampStimulusSeries[key]``: the optional paired stimulus, in a parallel registry at the
      SAME key as its response. It reuses the response's electrode, so it carries no ``electrode_metadata_key``.
    """
    metadata = DeepDict()
    metadata["Devices"] = {
        DEFAULT_METADATA_KEY: {
            "name": "Amplifier",
        }
    }
    metadata["Icephys"] = {
        "IntracellularElectrodes": {
            DEFAULT_METADATA_KEY: {
                "name": "IntracellularElectrode",
                "description": "no description",
                "device_metadata_key": DEFAULT_METADATA_KEY,
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

    Resolves the electrode entry, follows its ``device_metadata_key`` link to the device entry, and fills any
    schema-required field the entry omits from :func:`_get_icephys_metadata_placeholders` (defaults are applied
    here, at write time, so an interface's ``get_metadata`` only returns what the source provides). The electrode
    and its device dedup by ``name``, so several interfaces pointing at the same name share one object.
    """
    placeholders = _get_icephys_metadata_placeholders()
    electrode_metadata = {
        **placeholders["Icephys"]["IntracellularElectrodes"][DEFAULT_METADATA_KEY],
        **metadata["Icephys"]["IntracellularElectrodes"][electrode_metadata_key],
    }
    device_metadata_key = electrode_metadata["device_metadata_key"]
    device_metadata = {
        **placeholders["Devices"][DEFAULT_METADATA_KEY],
        **metadata["Devices"][device_metadata_key],
    }

    name = electrode_metadata["name"]
    if name in nwbfile.icephys_electrodes:
        return nwbfile.icephys_electrodes[name]

    device_name = device_metadata["name"]
    if device_name in nwbfile.devices:
        device = nwbfile.devices[device_name]
    else:
        device = nwbfile.create_device(name=device_name, description=device_metadata.get("description"))
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

    Reads, per row: the response ``(start_index, count)`` timing range, ``sequence``, ``stimulus_type``, and the
    optional ``repetition`` / ``condition`` columns, then groups upward:

    - rows of one ``sequence`` sharing a timing range -> one ``SimultaneousRecordings`` entry,
    - the simultaneous entries of one ``sequence`` -> one ``SequentialRecordings`` entry (with its stimulus type),
    - the sequentials of one ``repetition`` -> one ``Repetitions`` entry (present, or identity per sequence
      when a ``condition`` needs a repetitions rung beneath it),
    - the repetitions of one ``condition`` -> one ``ExperimentalConditions`` entry (only if the column is present).

    Each grouping value is constant within a sequence (a run), so the run-level attributes are read off any of
    its rows. When a ``repetition`` column is absent, each sequence is its own repetition (identity grouping,
    the same width-1 default ``SimultaneousRecordings`` uses for a single electrode), so a ``condition`` without
    a ``repetition`` still builds: it groups those identity repetitions.

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
    stimulus_types = intracellular_recordings["stimulus_type"]
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
                stimulus_type=stimulus_types[row_index],
                repetition=repetitions[row_index] if repetitions is not None else None,
                condition=conditions[row_index] if conditions is not None else None,
            )
        response_reference = responses[row_index]
        timing_key = (response_reference.idx_start, response_reference.count)
        timing_groups_by_sequence[sequence_value].setdefault(timing_key, []).append(row_index)

    # Simultaneous + sequential: one sequential per sequence.
    sequential_index_by_sequence: dict = {}
    for sequence_value in sequence_order:
        timing_groups = timing_groups_by_sequence[sequence_value]
        simultaneous_indices = [
            nwbfile.add_icephys_simultaneous_recording(recordings=timing_groups[timing_key])
            for timing_key in sorted(timing_groups)
        ]
        sequential_index_by_sequence[sequence_value] = nwbfile.add_icephys_sequential_recording(
            simultaneous_recordings=simultaneous_indices,
            stimulus_type=attributes_by_sequence[sequence_value]["stimulus_type"],
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
