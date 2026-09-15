"""Reading the raw side of a GuPPy session recorded on a Neurophotometrics system.

Covers both NPM layouts, the state-column and the header-less one. NPM store names are synthetic:
GuPPy invents them while demultiplexing an interleaved recording, and no column of the raw file
carries one. A run folder records what each store was demultiplexed from, which is read as given;
one written before GuPPy recorded that leaves only the names, which have to be decoded by
reproducing its arithmetic. See :func:`npm_store_to_demux`.
"""

import re

from pydantic import DirectoryPath

from ._session_files import is_event_csv
from ..csv._demux import StrideDemux
from ..csv.csvfiberphotometrydatainterface import CSVFiberPhotometryInterface
from ..npm.npmfiberphotometrydatainterface import NPMFiberPhotometryInterface
from ...events.csv_events.csveventsdatainterface import CSVEventsInterface
from ...events.npm_events.npmeventsdatainterface import NPMEventsInterface

ASSOCIATED_SUFFIXES = tuple(
    dict.fromkeys(NPMFiberPhotometryInterface.associated_suffixes + NPMEventsInterface.associated_suffixes)
)

# How a GuPPy run that predates the "stores" record names its NPM stores: a file index, one of
# three ordinal channel slots, and a positional column index, every part of which has to be
# reproduced to resolve. See _npm_store_from_legacy_name.
_NPM_LEGACY_STORE_PATTERN = re.compile(r"^file(\d+)_ch(ev|od|pr)(\d+)$")
_NPM_SLOTS = ("ev", "od", "pr")
# The low three bits of an NPM state word are one flag per excitation LED; the higher bits are
# digital lines. A legacy run's slots are ordered by the whole word, so the wavelength a slot stands
# for is recovered from the bits.
_NPM_EXCITATION_CODE_TO_WAVELENGTH = {1: 415, 2: 470, 4: 560}
_NPM_EXCITATION_BITS = 0b111


def _npm_column_count(file_path) -> int:
    """Return how many columns a CSV has, which is how GuPPy tells an NPM event file from a data file."""
    import pandas

    return int(pandas.read_csv(file_path, header=None, nrows=1).shape[1])


def _parses_as_float(value) -> bool:
    """Return whether a column label is numeric, which is how GuPPy detects a header-less NPM file."""
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _npm_event_file(folder_path: DirectoryPath):
    """Return the one two-column event CSV a GuPPy NPM session holds.

    GuPPy writes NPM events to their own file, told apart from the acquisition CSVs by having exactly
    two columns (onset time and label).
    """
    event_files = [
        path for path in sorted(folder_path.glob("*.csv")) if not is_event_csv(path) and _npm_column_count(path) == 2
    ]
    assert len(event_files) == 1, (
        f"Expected exactly one NPM event file in '{folder_path}', found {len(event_files)}: "
        f"{[path.name for path in event_files]}."
    )
    return event_files[0]


def npm_run_parameters(guppy_folder_path: DirectoryPath) -> dict:
    """Read the NPM settings the GuPPy run used but ``storesList.csv`` does not record.

    Which clock a store was read on, what unit it was in, and -- for the header-less layout -- how
    many channels were interleaved are all choices made when GuPPy ran, and none leave a mark on the
    raw file. GuPPy records them in a ``.npm_params.json`` beside ``storesList.csv``; runs written
    before it recorded the channel count there carry it in ``GuPPyParamtersUsed.json`` instead.

    The unit is session-wide: GuPPy applies one to every stream it decomposes. ``timestamp_column_name``
    is the run's choice rather than the clock any particular store was read on.
    """
    import json

    npm_parameters_path = guppy_folder_path / ".npm_params.json"
    assert npm_parameters_path.is_file(), (
        f"Missing {npm_parameters_path}. A GuPPy NPM run records the timestamp column and time unit "
        f"it used there, and neither can be recovered from the raw files."
    )
    npm_parameters = json.loads(npm_parameters_path.read_text(encoding="utf-8"))
    assert "npm_time_unit" in npm_parameters, (
        f"'{npm_parameters_path}' records no 'npm_time_unit' and was written by a GuPPy version whose "
        f"recorded timestamp unit did not always match the one applied. Re-run Step 1 (Label Stores) "
        f"in GuPPy for '{guppy_folder_path}' to record the unit this session's timestamps are in."
    )
    number_of_channels = npm_parameters.get("noChannels")
    if number_of_channels is None:
        guppy_parameters = json.loads((guppy_folder_path / "GuPPyParamtersUsed.json").read_text(encoding="utf-8"))
        number_of_channels = guppy_parameters.get("noChannels")
    return dict(
        timestamp_column_name=npm_parameters["npm_timestamp_column_name"],
        time_unit=npm_parameters["npm_time_unit"],
        # Only the header-less layout needs this: a file carrying a state column derives its own
        # channel count, so a run that never read a header-less file need not have recorded one.
        number_of_channels=None if number_of_channels is None else int(number_of_channels),
        # What each store was demultiplexed from, as GuPPy recorded it. Empty for a run written
        # before GuPPy recorded it, whose store names are decoded instead -- see
        # :func:`npm_store_to_demux`.
        store_provenance=npm_parameters.get("stores") or dict(),
    )


def npm_source_files(folder_path: DirectoryPath) -> list:
    """Return the folder's CSVs in the order GuPPy indexes them as ``file{N}``.

    GuPPy sorts the folder's CSVs by path and drops the files it derived itself, then indexes what
    remains. Event files are **not** dropped, so they occupy an index too and ``file{N}`` means "the
    Nth surviving CSV" rather than "the Nth data file" -- an event file that sorts early shifts every
    data file after it.
    """
    derived = set()
    for pattern in ("*chev*", "*chod*", "*chpr*", "event*"):
        derived.update(folder_path.glob(pattern))
    candidates = [path for path in sorted(folder_path.glob("*.csv")) if path not in derived]
    return [path for path in candidates if not is_event_csv(path)]


def _npm_channel_label(demux: dict) -> str:
    """Describe the file and channel a resolved store came from, for a failure message."""
    channel = (
        f"cycle position {demux['slot_index']}"
        if demux["excitation_wavelength_in_nm"] is None
        else f"{demux['excitation_wavelength_in_nm']} nm"
    )
    return f"{demux['file_path'].name} {channel}"


def _npm_store_from_provenance(folder_path: DirectoryPath, store_id: str, record: dict, number_of_channels) -> dict:
    """Resolve a store from the record GuPPy wrote of what it demultiplexed."""
    file_path = folder_path / record["file"]
    assert file_path.is_file(), (
        f"The run folder records store '{store_id}' as read from '{record['file']}', which is not in "
        f"'{folder_path}'. The raw session folder and the GuPPy output folder have to belong together."
    )
    wavelength = record["excitation_wavelength_in_nm"]
    if wavelength is None:
        assert number_of_channels is not None, (
            f"Store '{store_id}' was demultiplexed by row position, whose cycle length has no on-disk "
            f"signature, but the GuPPy run recorded no 'noChannels'."
        )
    return dict(
        file_path=file_path,
        excitation_wavelength_in_nm=wavelength,
        slot_index=record.get("interleave_position"),
        num_channels=None if wavelength is not None else number_of_channels,
        data_column=record["data_column"],
        timestamps_column=record["timestamp_column"],
    )


def _npm_store_from_legacy_name(
    folder_path: DirectoryPath, store_id: str, number_of_channels, timestamp_column_name
) -> dict:
    """Resolve a store written before GuPPy recorded what it demultiplexed.

    Such a run names its stores ``file<N>_ch<ev|od|pr><column>``, where every part is positional:
    ``file<N>`` indexes :func:`npm_source_files`, ``ch<slot>`` is an ordinal into the LED states
    sorted ascending and sampled from rows 2-11 so the startup frame is skipped, and the trailing
    number indexes the columns left after GuPPy canonicalized the timestamps and dropped
    ``FrameCounter`` and the state column. The clock is positional too: the session-wide
    ``npm_timestamp_column_name`` where the run recorded one, and the file's first timestamp column
    otherwise.
    """
    import numpy
    import pandas

    match = _NPM_LEGACY_STORE_PATTERN.match(store_id)
    assert match is not None, (
        f"'{store_id}' is not a GuPPy NPM store name. The run folder records no 'stores' mapping, so "
        f"its stores are expected in the older positional form 'file<N>_ch<ev|od|pr><column>'."
    )
    file_index, slot, column_position = int(match.group(1)), match.group(2), int(match.group(3))
    slot_ordinal = _NPM_SLOTS.index(slot)

    source_files = npm_source_files(folder_path)
    assert file_index < len(source_files), (
        f"Store '{store_id}' names file index {file_index}, but '{folder_path}' holds only "
        f"{len(source_files)} NPM source file(s): {[path.name for path in source_files]}."
    )
    file_path = source_files[file_index]

    dataframe = pandas.read_csv(file_path, index_col=False, nrows=12)
    headerless = any(_parses_as_float(column) for column in dataframe.columns)
    if headerless:
        assert number_of_channels is not None, (
            f"'{file_path}' is a header-less NPM file, whose interleave has no on-disk signature, but "
            f"the GuPPy run recorded no 'noChannels'. Store '{store_id}' cannot be demultiplexed."
        )
        return dict(
            file_path=file_path,
            excitation_wavelength_in_nm=None,
            slot_index=slot_ordinal,
            num_channels=number_of_channels,
            data_column=column_position,
            # Nothing names these columns, so the timestamps are the leading one.
            timestamps_column=0,
        )

    column_by_lowercase_name = {str(column).lower(): column for column in dataframe.columns}
    state_column = column_by_lowercase_name.get("flags") or column_by_lowercase_name.get("ledstate")
    assert state_column is not None, (
        f"'{file_path}' has a header but no 'Flags' or 'LedState' column, so GuPPy could not have "
        f"demultiplexed it into '{store_id}'."
    )
    state = pandas.read_csv(file_path, index_col=False)[state_column].to_numpy().astype(int)
    unique_states = numpy.unique(state[2:12])
    assert slot_ordinal < len(unique_states), (
        f"Store '{store_id}' names channel slot '{slot}' (index {slot_ordinal}), but '{file_path}' "
        f"interleaves only {len(unique_states)} channel(s) (states {unique_states.tolist()})."
    )
    state_value = int(unique_states[slot_ordinal])
    excitation_code = state_value & _NPM_EXCITATION_BITS
    assert excitation_code in _NPM_EXCITATION_CODE_TO_WAVELENGTH, (
        f"Store '{store_id}' was demultiplexed from NPM state {state_value}, whose excitation bits "
        f"({excitation_code:#05b}) are not a single wavelength. GuPPy treated such a frame as its own "
        f"channel, but a fiber photometry series is written per excitation."
    )

    # Reproduce GuPPy's column trimming: the canonical timestamps column replaced the several it
    # found (only when there were several), then FrameCounter and the state column went.
    timestamp_columns = [column for column in dataframe.columns if "timestamp" in str(column).lower()]
    remaining = list(dataframe.columns)
    if len(timestamp_columns) > 1:
        remaining.insert(1, "Timestamp")
        remaining = [column for column in remaining if column not in timestamp_columns]
    remaining = [
        column for column in remaining if column not in (column_by_lowercase_name.get("framecounter"), state_column)
    ]
    assert column_position < len(remaining), (
        f"Store '{store_id}' names column position {column_position}, but '{file_path}' leaves only "
        f"{len(remaining)} column(s) after GuPPy's trimming: {remaining}."
    )
    return dict(
        file_path=file_path,
        excitation_wavelength_in_nm=_NPM_EXCITATION_CODE_TO_WAVELENGTH[excitation_code],
        slot_index=None,
        num_channels=None,
        data_column=remaining[column_position],
        timestamps_column=timestamp_column_name or (timestamp_columns[0] if timestamp_columns else None),
    )


def npm_store_to_demux(
    folder_path: DirectoryPath,
    store_id: str,
    *,
    number_of_channels: int,
    store_provenance: dict | None = None,
    timestamp_column_name: str | None = None,
) -> dict:
    """Resolve a GuPPy NPM store to the file, channel and column it was demultiplexed from.

    An NPM store name is invented: GuPPy makes it up while splitting an interleaved recording, and
    no column of the raw file carries it. A run folder written by a GuPPy that records what it
    demultiplexed says so directly, under ``stores`` in ``.npm_params.json``, and that record is
    read as given. One written before that records only the names, and they have to be decoded by
    reproducing GuPPy's arithmetic -- see :func:`_npm_store_from_legacy_name`.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the raw session folder holding the acquisition CSVs.
    store_id : str
        The ``storesList.csv`` id to resolve.
    number_of_channels : int
        The run's ``noChannels``, needed only where the channels cycle by row position.
    store_provenance : dict, optional
        What the run folder records about its stores, from :func:`npm_run_parameters`. Empty or
        ``None`` for a run predating that record, which takes the decoding path; where it is
        present it has to name every store, since a run that recorded its stores recorded all of
        them.
    timestamp_column_name : str, optional
        The run's ``npm_timestamp_column_name``, used only on the decoding path.

    Returns
    -------
    dict
        The file, the excitation wavelength (``None`` where the channels cycle by row position, with
        ``slot_index`` and ``num_channels`` instead), the data column, and the timestamps column,
        ready to read as they are.
    """
    if not store_provenance:
        return _npm_store_from_legacy_name(folder_path, store_id, number_of_channels, timestamp_column_name)
    record = store_provenance.get(store_id)
    assert record is not None, (
        f"The run folder records what its stores were demultiplexed from but says nothing about "
        f"'{store_id}', naming {sorted(store_provenance)} instead. Its 'storesList.csv' and its "
        f"'.npm_params.json' describe different stores, so they were not written by one run."
    )
    return _npm_store_from_provenance(folder_path, store_id, record, number_of_channels)


def build_npm_acquisition_interface(
    *,
    folder_path: DirectoryPath,
    guppy_folder_path: DirectoryPath,
    store_ids: list[str],
    metadata_key: str,
    verbose: bool,
):
    """Build the interface writing one series from the ordered ``store_ids``.

    Each store is resolved to the file, channel and column GuPPy demultiplexed it from -- see
    :func:`npm_store_to_demux`. Which interface reads them follows from what that resolves to: a
    store lit by a named excitation wavelength is read by selecting that LED's frames, while one
    carrying a cycle position came from a file with no state column to select on, so GuPPy's blind
    stride is reproduced through the generic CSV interface instead.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the raw session folder holding the acquisition CSVs, which a recorded store names by
        file name and a legacy ``file<N>`` name indexes in sorted order.
    guppy_folder_path : DirectoryPath
        Path to the GuPPy ``<session>_output_<N>`` folder, for the run settings that leave no mark on
        the raw files -- see :func:`npm_run_parameters`.
    store_ids : list of str
        The ``storesList.csv`` ids of the stores to stack into this one series, one per recording
        site. Column order of the resulting series, which must be preserved.
    metadata_key : str
        The key the interface reads its block from under ``metadata["FiberPhotometry"]``.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    NPMFiberPhotometryInterface or CSVFiberPhotometryInterface
        Reading ``store_ids`` as the columns of a single ``FiberPhotometryResponseSeries``; the
        latter, carrying a ``StrideDemux``, for the header-less layout.

    Raises
    ------
    AssertionError
        If the stores do not all come from one file and one channel.
    """
    run_parameters = npm_run_parameters(guppy_folder_path)
    demuxes = [
        npm_store_to_demux(
            folder_path,
            store_id,
            number_of_channels=run_parameters["number_of_channels"],
            store_provenance=run_parameters["store_provenance"],
            timestamp_column_name=run_parameters["timestamp_column_name"],
        )
        for store_id in store_ids
    ]
    # A role becomes one interface, so its stores must all be the same channel of the same file;
    # only the column may differ between recording sites.
    distinct = {(demux["file_path"], demux["excitation_wavelength_in_nm"], demux["slot_index"]) for demux in demuxes}
    assert len(distinct) == 1, (
        f"The '{metadata_key}' stores do not share one NPM file and channel "
        f"({[f'{store_id}: {_npm_channel_label(demux)}' for store_id, demux in zip(store_ids, demuxes)]}), "
        f"so they cannot be written as one series."
    )
    first = demuxes[0]
    time_unit = run_parameters["time_unit"]
    timestamps_column = first["timestamps_column"]

    if first["excitation_wavelength_in_nm"] is None:
        # The file names no LED, so reproduce GuPPy's blind stride, whose index is the position in
        # the cycle.
        return CSVFiberPhotometryInterface(
            file_path=first["file_path"],
            data_columns=[demux["data_column"] for demux in demuxes],
            timestamps_column=timestamps_column,
            demux_configuration=StrideDemux(channels=first["num_channels"], index=first["slot_index"]),
            time_unit=time_unit,
            metadata_key=metadata_key,
            verbose=verbose,
        )

    return NPMFiberPhotometryInterface(
        file_path=first["file_path"],
        excitation_wavelength_in_nm=first["excitation_wavelength_in_nm"],
        regions=[demux["data_column"] for demux in demuxes],
        timestamps_column=timestamps_column,
        time_unit=time_unit,
        metadata_key=metadata_key,
        verbose=verbose,
    )


def build_npm_events_interface(
    *,
    folder_path: DirectoryPath,
    guppy_folder_path: DirectoryPath,
    event_store_ids: list[str],
    verbose: bool,
):
    """Build the interface reading the raw discrete events.

    GuPPy writes NPM events to their own two-column file, and splits it by the label in the second
    column -- or reads the whole file as one type when it split nothing. Which of the two interfaces
    reads it follows from that. What the interface then *calls* those types is a separate question,
    answered by :func:`npm_event_source_id_to_store_id`.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the GuPPy session folder, holding the two-column event CSV alongside the traces.
    guppy_folder_path : DirectoryPath
        Path to the GuPPy ``<session>_output_<N>`` folder, for the time unit the event file was
        recorded in -- see :func:`npm_run_parameters`.
    event_store_ids : list of str
        The ``storesList.csv`` ids of the behavioral event stores GuPPy processed, either the lone
        unsplit ``event0`` or one ``event<label>`` per label GuPPy split out.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    NPMEventsInterface or CSVEventsInterface
        Reading the session's one event file; the latter for the unsplit ``event0`` store, which is
        the whole file as a single type.

    Raises
    ------
    AssertionError
        If the session does not hold exactly one NPM event file, or mixes the unsplit ``event0``
        store with stores split out of that same file.
    """
    run_parameters = npm_run_parameters(guppy_folder_path)
    event_file_path = _npm_event_file(folder_path)
    time_unit = run_parameters["time_unit"]

    if event_store_ids == ["event0"]:
        # The unsplit store: every row of the file as one event type. NPMEventsInterface always
        # splits by label, so this reads the same file through the generic CSV interface.
        return CSVEventsInterface(
            file_path=event_file_path,
            timestamps_column=0,
            event_type_column=None,
            time_unit=time_unit,
            metadata_key="guppy_npm_events",
            verbose=verbose,
        )

    unsplit = [store_id for store_id in event_store_ids if store_id == "event0"]
    assert not unsplit, (
        f"GuPPy's storesList.csv mixes the unsplit store 'event0' with split stores "
        f"{[store for store in event_store_ids if store != 'event0']}. 'event0' means the whole "
        f"event file as one type, which cannot coexist with types split out of that same file."
    )
    return NPMEventsInterface(
        file_path=event_file_path,
        time_unit=time_unit,
        metadata_key="guppy_npm_events",
        verbose=verbose,
    )


def npm_event_source_id_to_store_id(*, folder_path: DirectoryPath, event_store_ids: list[str]) -> dict[str, str]:
    """Map each event type the interface seeds back to the ``storesList.csv`` id it belongs to.

    GuPPy and the events interfaces disagree on what an NPM event store is called, and this is the
    translation between the two. GuPPy names a store by prefixing ``event`` to the label it split on,
    so label ``1`` becomes the store ``event1``, and calls the whole file ``event0`` when it split
    nothing. The interface reading that file has no such convention: it seeds the bare label, or --
    for the unsplit file, read through ``CSVEventsInterface`` -- the file's stem. Every other
    acquisition format already agrees with GuPPy and needs no translation.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the GuPPy session folder. Read only for the unsplit store, whose seeded id is the
        event file's stem and so cannot be derived from ``event_store_ids`` alone.
    event_store_ids : list of str
        The ``storesList.csv`` ids of the behavioral event stores GuPPy processed. Assumed to be one
        consistent shape, which :func:`build_npm_events_interface` is what actually enforces.

    Returns
    -------
    dict
        ``event_type_source_id -> storesList.csv id``, one entry per store.
    """
    if event_store_ids == ["event0"]:
        return {_npm_event_file(folder_path).stem: "event0"}
    return {store_id[len("event") :]: store_id for store_id in event_store_ids}
