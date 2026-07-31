"""The acquisition-format seam of :class:`~.guppyconverter.GuppyConverter`.

Everything in this module knows how a GuPPy session was recorded; nothing outside it does. The
converter discovers its stores from ``storesList.csv`` as opaque ids and then groups, links and
writes them without ever asking what produced them -- it only calls
:func:`build_acquisition_interface` and :func:`build_events_interfaces` to turn those ids into the
interfaces that can read them.

Supporting another GuPPy-readable format means, entirely within this module: adding its entry to
``_ACQUISITION_FORMAT_TO_INTERFACES`` (which is what advertises its suffixes), widening
:data:`AcquisitionFormat`, and adding a branch to each of the two ``build_*`` functions.
"""

import re
from typing import Literal

import numpy
from pydantic import DirectoryPath

from ..csv._demux import StrideDemux
from ..csv.csvfiberphotometrydatainterface import CSVFiberPhotometryInterface
from ..csv.multifilecsvfiberphotometrydatainterface import (
    MultiFileCSVFiberPhotometryInterface,
)
from ..doric.doricfiberphotometrydatainterface import DoricFiberPhotometryInterface
from ..npm.npmfiberphotometrydatainterface import NPMFiberPhotometryInterface
from ..tdt.tdtfiberphotometrydatainterface import TDTFiberPhotometryInterface
from ...events.csv_events.csveventsdatainterface import CSVEventsInterface
from ...events.doric_events.doriccsveventsdatainterface import DoricCSVEventsInterface
from ...events.doric_events.doriceventsdatainterface import DoricEventsInterface
from ...events.npm_events.npmeventsdatainterface import NPMEventsInterface
from ...events.tdt_events.tdteventsdatainterface import TDTEventsInterface

# The formats a GuPPy session can have been recorded in -- every format GuPPy itself supports.
AcquisitionFormat = Literal["tdt", "csv", "doric", "npm"]

# Each format mapped to the (acquisition, events) interfaces built for it. Only read for the suffixes
# below; the dispatch itself is the if-chains in the two build_* functions.
_ACQUISITION_FORMAT_TO_INTERFACES = {
    "tdt": (TDTFiberPhotometryInterface, TDTEventsInterface),
    "csv": (MultiFileCSVFiberPhotometryInterface, CSVEventsInterface),
    "doric": (DoricFiberPhotometryInterface, DoricEventsInterface),
    "npm": (NPMFiberPhotometryInterface, NPMEventsInterface),
}
# Derived from the supported formats rather than hard-coded, so this stays accurate as formats land.
ACQUISITION_SUFFIXES: tuple[str, ...] = tuple(
    dict.fromkeys(
        suffix
        for interfaces in _ACQUISITION_FORMAT_TO_INTERFACES.values()
        for interface in interfaces
        for suffix in interface.associated_suffixes
    )
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


def _is_event_csv(file_path) -> bool:
    """Return whether a ``.csv`` holds GuPPy event onsets rather than acquisition traces.

    A GuPPy event CSV is a lone ``timestamps`` column. Doric exports are wide and lead with a device
    header row, so the two are told apart by the header alone -- the same distinction GuPPy draws when
    it decides which files in a session folder its Doric reader should look at.
    """
    import pandas

    columns = list(pandas.read_csv(file_path, nrows=0).columns)
    return len(columns) == 1 and str(columns[0]).strip().lower() == "timestamps"


def npm_run_parameters(guppy_folder_path: DirectoryPath) -> dict:
    """Read the NPM settings the GuPPy run used but ``storesList.csv`` does not record.

    Which clock a store was read on, what unit it was in, and -- for the header-less layout -- how
    many channels were interleaved are all choices made when GuPPy ran, and none leave a mark on the
    raw file. GuPPy records the first two in a ``.npm_params.json`` beside ``storesList.csv``, keyed
    by the same file index the store names use, and the channel count in ``GuPPyParamtersUsed.json``.
    Both are required rather than guessed: an inferred clock silently produces wrong timestamps.
    """
    import json

    npm_parameters_path = guppy_folder_path / ".npm_params.json"
    assert npm_parameters_path.is_file(), (
        f"Missing {npm_parameters_path}. A GuPPy NPM run records the timestamp column and time unit "
        f"it used there, and neither can be recovered from the raw files."
    )
    npm_parameters = json.loads(npm_parameters_path.read_text(encoding="utf-8"))
    guppy_parameters = json.loads((guppy_folder_path / "GuPPyParamtersUsed.json").read_text(encoding="utf-8"))
    number_of_channels = guppy_parameters.get("noChannels")
    return dict(
        timestamp_column_names=npm_parameters["npm_timestamp_column_names"],
        time_units=npm_parameters["npm_time_units"],
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
    return [path for path in candidates if not _is_event_csv(path)]


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


def resolve_doric_file(folder_path: DirectoryPath):
    """Return the one Doric acquisition file in ``folder_path``.

    GuPPy requires a Doric session folder to hold exactly one acquisition file and hard-errors
    otherwise, so this mirrors that rule rather than guessing. Single-column ``timestamps`` CSVs are
    event files, not acquisition, and are excluded the way GuPPy excludes them.
    """
    candidates = sorted(folder_path.glob("*.doric")) + [
        path for path in sorted(folder_path.glob("*.csv")) if not _is_event_csv(path)
    ]
    assert len(candidates) == 1, (
        f"Expected exactly one Doric acquisition file in '{folder_path}', found {len(candidates)}: "
        f"{[path.name for path in candidates]}. A GuPPy Doric session folder holds one .doric or one "
        f"DoricStudio .csv export."
    )
    return candidates[0]


def doric_store_id_to_stream_name(file_path) -> dict[str, str]:
    """Map each GuPPy Doric store id to the stream name the Doric interface knows it by.

    GuPPy names a Doric store by the tail of its path -- the last two components for the modern
    ``DataAcquisition`` layout (skipping a ``Values`` leaf), the group name alone for the legacy
    ``Traces`` layout -- while the interface names it by the whole path with ``/`` replaced by ``_``.
    That flattening is not invertible on its own, because group names contain underscores too
    (``CAM1_EXC1``), so the mapping is derived from each stream's real internal path instead. Doric
    CSV columns need no translation and map to themselves.
    """
    store_id_to_stream_name: dict[str, list[str]] = {}
    for stream_name, stream_info in DoricFiberPhotometryInterface._discover_streams(file_path).items():
        if stream_info["format"] == "csv":
            store_id = stream_info["data_column"]
        else:
            parts = stream_info["data_path"].split("/")
            if parts[0] == "Traces":
                store_id = parts[-1]
            elif parts[-1] == "Values":
                store_id = f"{parts[-3]}/{parts[-2]}"
            else:
                store_id = f"{parts[-2]}/{parts[-1]}"
        store_id_to_stream_name.setdefault(store_id, []).append(stream_name)

    ambiguous = {store: names for store, names in store_id_to_stream_name.items() if len(names) > 1}
    assert not ambiguous, (
        f"Doric file '{file_path}' contains streams that GuPPy would name identically: "
        f"{ambiguous}. GuPPy keeps only the tail of a stream's path, so these cannot be told apart "
        f"from a storesList.csv entry."
    )
    return {store: names[0] for store, names in store_id_to_stream_name.items()}


def build_acquisition_interface(
    *,
    acquisition_format: str,
    folder_path: DirectoryPath,
    guppy_folder_path: DirectoryPath,
    store_ids: list[str],
    metadata_key: str,
    verbose: bool,
):
    """Build the acquisition interface writing one series from the ordered ``store_ids``.

    The interface column-stacks the stores in the given order, which is the order
    ``GuppyConverter._derive_recording_site_to_table_rows`` zips against the declared region -- so
    every branch must preserve ``store_ids`` order.

    For TDT, GuPPy's store ids are the tank's stream names verbatim and pass straight through; for
    CSV they are filename stems, so each names one file. Doric store ids are abbreviated paths that
    need real translation, which is why this dispatch exists at all rather than every format sharing
    one call.

    Parameters
    ----------
    acquisition_format : {"tdt", "csv", "doric", "npm"}
        The format the session was recorded in, selecting which interface reads ``folder_path``.
    folder_path : DirectoryPath
        Path to the folder holding the raw acquisition traces: the tank folder for TDT, the folder
        holding one ``<store>.csv`` per store for CSV, the folder holding the single ``.doric`` or
        DoricStudio ``.csv`` export for Doric, and the GuPPy session folder itself for NPM, whose
        ``file<N>`` store names index that folder's CSVs in sorted order.
    guppy_folder_path : DirectoryPath
        Path to the GuPPy ``<session>_output_<N>`` folder. Read by the NPM branch alone, for the run
        settings that leave no mark on the raw files -- see :func:`npm_run_parameters`.
    store_ids : list of str
        The ``storesList.csv`` ids of the stores to stack into this one series, one per recording
        site. Column order of the resulting series, which every branch must preserve.
    metadata_key : str
        The key the interface reads its block from under ``metadata["FiberPhotometry"]``. The
        converter passes the role, ``"signal"`` or ``"control"``.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    BaseFiberPhotometryInterface
        The interface for ``acquisition_format``, reading ``store_ids`` as the columns of a single
        ``FiberPhotometryResponseSeries``.

    Raises
    ------
    NotImplementedError
        If ``acquisition_format`` names a format no branch builds an interface for.
    AssertionError
        If the stores cannot be written as one series: a Doric store id the file does not provide,
        or NPM stores spread over more than one file or channel, or demultiplexed from a strobed
        frame carrying more than one excitation wavelength.
    """
    if acquisition_format == "tdt":
        return TDTFiberPhotometryInterface(
            folder_path=folder_path,
            stream_names=store_ids,
            metadata_key=metadata_key,
            verbose=verbose,
        )
    if acquisition_format == "csv":
        # GuPPy writes one CSV per store, named for the store, with a fixed timestamps/data header.
        # The interface stacks them in file order and asserts they share a time axis.
        return MultiFileCSVFiberPhotometryInterface(
            file_paths=[folder_path / f"{store_id}.csv" for store_id in store_ids],
            data_columns="data",
            timestamps_column="timestamps",
            metadata_key=metadata_key,
            verbose=verbose,
        )
    if acquisition_format == "doric":
        file_path = resolve_doric_file(folder_path)
        store_id_to_stream_name = doric_store_id_to_stream_name(file_path)
        missing = [store_id for store_id in store_ids if store_id not in store_id_to_stream_name]
        # The Doric interface does not validate stream_names at construction, so an untranslated id
        # would surface much later as a bare KeyError; name the offending store here instead.
        assert not missing, (
            f"GuPPy's storesList.csv names acquisition store(s) {missing} that '{file_path}' does not "
            f"provide (available: {sorted(store_id_to_stream_name)})."
        )
        return DoricFiberPhotometryInterface(
            file_path=file_path,
            stream_names=[store_id_to_stream_name[store_id] for store_id in store_ids],
            metadata_key=metadata_key,
            verbose=verbose,
        )
    if acquisition_format == "npm":
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
        file_index = npm_source_files(folder_path).index(first["file_path"])
        time_unit = run_parameters["time_units"][file_index]

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
        timestamps_column = run_parameters["timestamp_column_names"][file_index] or first["timestamps_column"]
        return NPMFiberPhotometryInterface(
            file_path=first["file_path"],
            excitation_wavelength_in_nm=_NPM_EXCITATION_CODE_TO_WAVELENGTH[excitation_code],
            regions=[demux["data_column"] for demux in demuxes],
            timestamps_column=timestamps_column,
            time_unit=time_unit,
            metadata_key=metadata_key,
            verbose=verbose,
        )
    raise NotImplementedError(f"No acquisition interface is wired up for acquisition_format={acquisition_format!r}.")


def build_events_interfaces(
    *,
    acquisition_format: str,
    folder_path: DirectoryPath,
    guppy_folder_path: DirectoryPath,
    event_store_ids: list[str],
    verbose: bool,
) -> tuple[dict, dict]:
    """Build the interfaces reading the raw discrete events, keyed by converter interface name.

    Between them the returned interfaces must cover **every** behavioral event store GuPPy listed,
    and each type's ``event_type_source_id`` has to be the store id ``storesList.csv`` records --
    that id is the join key ``GuppyConverter.get_metadata`` uses to select and rename them. How many
    interfaces it takes is format-dependent, hence a dict rather than a single interface: one TDT
    interface reads every epoc in the tank and keys them by epoc name, while GuPPy's CSV format
    writes each store to its own file and ``CSVEventsInterface`` reads one file apiece.

    Parameters
    ----------
    acquisition_format : {"tdt", "csv", "doric", "npm"}
        The format the session was recorded in, selecting which interfaces read ``folder_path``.
    folder_path : DirectoryPath
        Path to the folder holding the raw discrete events. GuPPy writes a session's traces and its
        events into one folder, so this is frequently the acquisition folder as well.
    guppy_folder_path : DirectoryPath
        Path to the GuPPy ``<session>_output_<N>`` folder. Read by the NPM branch alone, for the time
        unit its event file was recorded in -- see :func:`npm_run_parameters`.
    event_store_ids : list of str
        The ``storesList.csv`` ids of the behavioral event stores GuPPy processed. The returned
        interfaces must cover every one of them between them.
    verbose : bool
        Whether the interfaces should print status messages.

    Returns
    -------
    interfaces : dict
        ``interface_name -> BaseEventsInterface``, keyed by the name to register each under.
    source_id_to_store_id : dict
        ``event_type_source_id -> storesList.csv id``, holding only the seeded event types whose
        source id is not already the store id. Empty when the two agree, which is the usual case.

    Raises
    ------
    NotImplementedError
        If ``acquisition_format`` names a format no branch builds interfaces for.
    AssertionError
        If the NPM session does not hold exactly one event file, or mixes the unsplit ``event0``
        store with stores split out of that same file.
    """
    if acquisition_format == "tdt":
        return {"Events": TDTEventsInterface(folder_path=folder_path, verbose=verbose)}, {}
    if acquisition_format == "csv":
        # A GuPPy event CSV is a single 'timestamps' column, so there is no event-type column to
        # split on; with event_type_column=None the lone type is keyed by the file stem, which is
        # the store id.
        return {
            f"Events_{store_id}": CSVEventsInterface(
                file_path=folder_path / f"{store_id}.csv",
                timestamps_column="timestamps",
                event_type_column=None,
                metadata_key=store_id,
                verbose=verbose,
            )
            for store_id in event_store_ids
        }, {}
    if acquisition_format == "doric":
        file_path = resolve_doric_file(folder_path)
        is_csv_export = file_path.suffix.lower() == ".csv"
        # Doric event stores are digital lines of the one acquisition file, so a single interface
        # covers them all. Its signal ids match GuPPy's store ids except in the modern HDF5 layout,
        # where GuPPy prefixes the containing group: 'DigitalIO/CAM1' against the interface's 'CAM1'.
        # Only that layout is stripped -- doing it blindly would turn the CSV store 'DI/O-1' into
        # 'O-1'.
        store_id_to_signal_id = {
            store_id: (
                store_id[len("DigitalIO/") :] if not is_csv_export and store_id.startswith("DigitalIO/") else store_id
            )
            for store_id in event_store_ids
        }
        # Naming the GuPPy store id as the spec's event_name makes it the seeded
        # event_type_source_id, so the select/rename/route blocks join on it exactly as they do for
        # the other formats. (The display name is overwritten with GuPPy's label there.)
        detection_configuration = {
            signal_id: [{"detection": "high_period", "event_name": store_id}]
            for store_id, signal_id in store_id_to_signal_id.items()
        }
        events_interface_class = DoricCSVEventsInterface if is_csv_export else DoricEventsInterface
        return {
            "Events": events_interface_class(
                file_path=file_path,
                detection_configuration=detection_configuration,
                metadata_key="guppy_doric_events",
                verbose=verbose,
            )
        }, {}
    if acquisition_format == "npm":
        run_parameters = npm_run_parameters(guppy_folder_path)
        # GuPPy writes NPM events to their own two-column file, and names each store by prefixing
        # "event" to the label it split on -- or calls the whole file "event0" when it split nothing.
        event_files = [
            path
            for path in sorted(folder_path.glob("*.csv"))
            if not _is_event_csv(path) and _npm_column_count(path) == 2
        ]
        assert len(event_files) == 1, (
            f"Expected exactly one NPM event file in '{folder_path}', found {len(event_files)}: "
            f"{[path.name for path in event_files]}."
        )
        event_file_path = event_files[0]
        file_index = sorted(folder_path.glob("*.csv")).index(event_file_path)
        time_unit = run_parameters["time_units"][file_index]

        if event_store_ids == ["event0"]:
            # The unsplit store: every row of the file as one event type. NPMEventsInterface always
            # splits by label, so this reads the same file through the generic CSV interface, which
            # keys its lone type by the file stem -- hence the translation back to 'event0'.
            return {
                "Events": CSVEventsInterface(
                    file_path=event_file_path,
                    timestamps_column=0,
                    event_type_column=None,
                    time_unit=time_unit,
                    metadata_key="guppy_npm_events",
                    verbose=verbose,
                )
            }, {event_file_path.stem: "event0"}

        unsplit = [store_id for store_id in event_store_ids if store_id == "event0"]
        assert not unsplit, (
            f"GuPPy's storesList.csv mixes the unsplit store 'event0' with split stores "
            f"{[store for store in event_store_ids if store != 'event0']}. 'event0' means the whole "
            f"event file as one type, which cannot coexist with types split out of that same file."
        )
        return {
            "Events": NPMEventsInterface(
                file_path=event_file_path,
                time_unit=time_unit,
                metadata_key="guppy_npm_events",
                verbose=verbose,
            )
        }, {store_id[len("event") :]: store_id for store_id in event_store_ids}
    raise NotImplementedError(f"No events interface is wired up for acquisition_format={acquisition_format!r}.")
