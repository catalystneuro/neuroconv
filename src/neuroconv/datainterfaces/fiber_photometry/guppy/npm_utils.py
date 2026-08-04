"""Reading the raw side of a GuPPy session recorded on a Neurophotometrics system.

Covers both NPM layouts, the state-column and the header-less one. NPM store names are entirely
synthetic: GuPPy invents them while demultiplexing an interleaved recording, and none of their parts
appear on disk. Recovering what a name refers to means reproducing GuPPy's own demultiplexing
arithmetic -- see :func:`npm_store_to_demux`.
"""

import re

import numpy
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

# GuPPy invents these names while demultiplexing an interleaved NPM recording: a file index, one of
# three ordinal channel slots, and a positional column index. See npm_store_to_demux.
_NPM_STORE_PATTERN = re.compile(r"^file(\d+)_ch(ev|od|pr)(\d+)$")
_NPM_SLOTS = ("ev", "od", "pr")
# The low three bits of an NPM state word are one flag per excitation LED; the higher bits are digital
# lines. GuPPy orders its channel slots by the whole word, so the wavelength is recovered from the bits.
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
    raw file. GuPPy records the first two in a ``.npm_params.json`` beside ``storesList.csv`` and the
    channel count in ``GuPPyParamtersUsed.json``.

    The clock and the unit are session-wide: GuPPy applies one unit to every stream it decomposes,
    so there is nothing to key by file here.
    """
    import json

    npm_parameters_path = guppy_folder_path / ".npm_params.json"
    assert npm_parameters_path.is_file(), (
        f"Missing {npm_parameters_path}. A GuPPy NPM run records the timestamp column and time unit "
        f"it used there, and neither can be recovered from the raw files."
    )
    npm_parameters = json.loads(npm_parameters_path.read_text(encoding="utf-8"))
    # Older GuPPy versions recorded a unit per file, which could disagree with the one they actually
    # applied, so a file predating the session-wide unit cannot be trusted to describe its own data.
    assert "npm_time_unit" in npm_parameters, (
        f"'{npm_parameters_path}' records no 'npm_time_unit' and was written by a GuPPy version whose "
        f"recorded timestamp unit did not always match the one applied. Re-run Step 1 (Label Stores) "
        f"in GuPPy for '{guppy_folder_path}' to record the unit this session's timestamps are in."
    )
    guppy_parameters = json.loads((guppy_folder_path / "GuPPyParamtersUsed.json").read_text(encoding="utf-8"))
    number_of_channels = guppy_parameters.get("noChannels")
    return dict(
        timestamp_column_name=npm_parameters["npm_timestamp_column_name"],
        time_unit=npm_parameters["npm_time_unit"],
        # Only the header-less layout needs this: a file carrying a state column derives its own
        # channel count, so a run that never read a header-less file need not have recorded one.
        number_of_channels=None if number_of_channels is None else int(number_of_channels),
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


def npm_store_to_demux(folder_path: DirectoryPath, store_id: str, *, number_of_channels: int) -> dict:
    """Decode a GuPPy NPM store name into the file, slot and column it was demultiplexed from.

    A name like ``file0_chod3`` is entirely synthetic: GuPPy invented it while splitting an
    interleaved NPM recording, and none of its three parts appear on disk. ``file0`` indexes
    :func:`npm_source_files`; ``chod`` is an ordinal into the LED states sorted ascending, sampled
    from rows 2-11 so the startup frame is skipped; ``3`` is a positional index into the columns left
    after GuPPy canonicalizes the timestamps and drops ``FrameCounter`` and the state column, with
    position 0 being the timestamps themselves.

    ``number_of_channels`` is used only for the legacy headerless layout, whose channel count has no
    on-disk signature; a file carrying a state column derives its own and ignores the argument, just
    as GuPPy does.
    """
    import pandas

    match = _NPM_STORE_PATTERN.match(store_id)
    assert (
        match is not None
    ), f"'{store_id}' is not a GuPPy NPM store name; expected the form 'file<N>_ch<ev|od|pr><column>'."
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
        # The legacy layout has no state column at all: channels cycle by row parity alone, and the
        # cycle length is whatever the GuPPy run was told it was.
        assert number_of_channels is not None, (
            f"'{file_path}' is a header-less NPM file, whose interleave has no on-disk signature, but "
            f"the GuPPy run recorded no 'noChannels'. Store '{store_id}' cannot be demultiplexed."
        )
        return dict(
            file_path=file_path,
            headerless=True,
            num_channels=number_of_channels,
            first_row=slot_ordinal,
            data_column=column_position,
            timestamps_column=0,
            state_value=None,
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

    # Reproduce GuPPy's column trimming: the canonical timestamps column replaces the several it
    # found (only when there are several), then FrameCounter and the state column go.
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
        headerless=False,
        num_channels=len(unique_states),
        first_row=int(numpy.where(state == state_value)[0][0]),
        data_column=remaining[column_position],
        timestamps_column=timestamp_columns[0] if timestamp_columns else None,
        state_value=state_value,
    )


def build_npm_acquisition_interface(
    *,
    folder_path: DirectoryPath,
    guppy_folder_path: DirectoryPath,
    store_ids: list[str],
    metadata_key: str,
    verbose: bool,
):
    """Build the interface writing one series from the ordered ``store_ids``.

    Each store name is decoded back into the file, channel and column GuPPy demultiplexed it from.
    Which interface reads them depends on the layout: the header-less one has no state column to
    select on, so GuPPy's blind stride is reproduced through the generic CSV interface instead.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the GuPPy session folder itself, since ``file<N>`` store names index that folder's
        CSVs in sorted order.
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
        If the stores do not all come from one file and one channel, or were demultiplexed from a
        strobed frame carrying more than one excitation wavelength.
    """
    run_parameters = npm_run_parameters(guppy_folder_path)
    demuxes = [
        npm_store_to_demux(folder_path, store_id, number_of_channels=run_parameters["number_of_channels"])
        for store_id in store_ids
    ]
    # A role becomes one interface, so its stores must all be the same channel of the same file;
    # only the column may differ between recording sites.
    distinct = {(demux["file_path"], demux["first_row"], demux["num_channels"]) for demux in demuxes}
    assert len(distinct) == 1, (
        f"The '{metadata_key}' stores {store_ids} do not share one NPM file and channel "
        f"({[(demux['file_path'].name, demux['first_row']) for demux in demuxes]}), so they cannot "
        f"be written as one series."
    )
    first = demuxes[0]
    time_unit = run_parameters["time_unit"]

    if first["headerless"]:
        # No state column to select on, so reproduce GuPPy's blind stride. skip_rows carries the
        # phase rather than index, which is capped below the channel count.
        return CSVFiberPhotometryInterface(
            file_path=first["file_path"],
            data_columns=[demux["data_column"] for demux in demuxes],
            timestamps_column=0,
            demux_configuration=StrideDemux(channels=first["num_channels"], index=0, skip_rows=first["first_row"]),
            time_unit=time_unit,
            metadata_key=metadata_key,
            verbose=verbose,
        )

    excitation_code = first["state_value"] & _NPM_EXCITATION_BITS
    assert excitation_code in _NPM_EXCITATION_CODE_TO_WAVELENGTH, (
        f"The '{metadata_key}' stores were demultiplexed from NPM state {first['state_value']}, whose "
        f"excitation bits ({excitation_code:#05b}) are not a single wavelength. GuPPy treats such a "
        f"frame as its own channel, but a fiber photometry series is written per excitation."
    )
    timestamps_column = run_parameters["timestamp_column_name"] or first["timestamps_column"]
    return NPMFiberPhotometryInterface(
        file_path=first["file_path"],
        excitation_wavelength_in_nm=_NPM_EXCITATION_CODE_TO_WAVELENGTH[excitation_code],
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
