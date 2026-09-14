"""Reading the raw side of a GuPPy session recorded on a Neurophotometrics system.

Covers both NPM layouts, the state-column and the header-less one. NPM store names are synthetic:
GuPPy invents them while demultiplexing an interleaved recording. They are, however, descriptive --
a name carries the source file, and then either the excitation wavelength and the region column it
was read from, or the position in the interleave cycle and the data column when the file names no
LED. See :func:`npm_store_to_demux`.
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

# What GuPPy appends to the source file's stem, having demultiplexed it. A file carrying a
# Flags/LedState column names the excitation that lit each frame and the region column the trace was
# read from; one that does not can only say where in the interleave cycle the channel sat, and which
# data column it came from.
_NPM_WAVELENGTH_SUFFIX_PATTERN = re.compile(r"^(?P<wavelength>415|470|560)nm_(?P<region>.+)$")
_NPM_SLOT_SUFFIX_PATTERN = re.compile(r"^ch(?P<slot>ev|od|pr)(?P<column>\d+)$")
_NPM_SLOTS = ("ev", "od", "pr")


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

    The clock and the unit are session-wide: GuPPy applies one unit to every stream it decomposes.
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
    """Decode a GuPPy NPM store name into the file, channel and column it was demultiplexed from.

    A name like ``signals_470nm_G2`` is synthetic -- GuPPy invented it while splitting an
    interleaved NPM recording -- but descriptive: ``signals`` is the stem of the source CSV,
    ``470nm`` the excitation that lit those frames, and ``G2`` the region column the trace came
    from. A file that names no LED yields ``PagCeAVgatFear_1512_1_chod1`` instead, where ``chod``
    is the second position in the interleave cycle and ``1`` the first data column.

    The stem is resolved against the folder's actual files rather than parsed out, since both a
    stem and a region name may contain underscores; the longest matching stem wins, so
    ``signals_extra_470nm_G0`` resolves to ``signals_extra.csv`` even alongside ``signals.csv``.

    ``number_of_channels`` is used only for the slot form, whose cycle length has no on-disk
    signature; a file naming its LEDs needs no such argument.
    """
    import pandas

    source_files = npm_source_files(folder_path)
    # Longest stem first, so a stem that is a prefix of another does not claim its stores.
    matching_files = sorted(
        (path for path in source_files if store_id.startswith(f"{path.stem}_")),
        key=lambda path: len(path.stem),
        reverse=True,
    )
    assert matching_files, (
        f"Store '{store_id}' names no source file of '{folder_path}'. GuPPy prefixes an NPM store "
        f"with the stem of the file it was demultiplexed from; this folder holds "
        f"{[path.name for path in source_files]}."
    )
    file_path = matching_files[0]
    suffix = store_id[len(file_path.stem) + 1 :]

    dataframe = pandas.read_csv(file_path, index_col=False, nrows=1)
    headerless = any(_parses_as_float(column) for column in dataframe.columns)
    timestamp_columns = [column for column in dataframe.columns if "timestamp" in str(column).lower()]
    timestamps_column = 0 if headerless else (timestamp_columns[0] if timestamp_columns else None)

    wavelength_match = _NPM_WAVELENGTH_SUFFIX_PATTERN.match(suffix)
    if wavelength_match is not None:
        return dict(
            file_path=file_path,
            headerless=headerless,
            excitation_wavelength_in_nm=int(wavelength_match.group("wavelength")),
            slot_index=None,
            num_channels=None,
            data_column=wavelength_match.group("region"),
            timestamps_column=timestamps_column,
        )

    slot_match = _NPM_SLOT_SUFFIX_PATTERN.match(suffix)
    assert slot_match is not None, (
        f"'{store_id}' is not a GuPPy NPM store name; expected the source file's stem followed by "
        f"either '<415|470|560>nm_<region>' or 'ch<ev|od|pr><column>', but '{file_path.stem}' is "
        f"followed by '{suffix}'."
    )
    assert number_of_channels is not None, (
        f"'{file_path}' names no LED, so GuPPy demultiplexed it by row position and the cycle length "
        f"has no on-disk signature, but the GuPPy run recorded no 'noChannels'. Store '{store_id}' "
        f"cannot be demultiplexed."
    )
    slot_index = _NPM_SLOTS.index(slot_match.group("slot"))
    assert slot_index < number_of_channels, (
        f"Store '{store_id}' names channel slot 'ch{slot_match.group('slot')}' (index {slot_index}), "
        f"but the GuPPy run interleaved only {number_of_channels} channel(s)."
    )
    # A slot name means GuPPy found no Flags/LedState column. In every such recording seen so far
    # that file has no header either -- the vendor writer always emits one, so a header-less file is
    # the generic Bonsai writer with the state field left out. A headered file with no state column
    # would number its data columns over the regions GuPPy picked out, which is a rule this bridge
    # would have to duplicate and could silently disagree with, so it is refused rather than guessed.
    assert headerless, (
        f"'{file_path}' has a header but no 'Flags' or 'LedState' column, so GuPPy demultiplexed it "
        f"by row position into '{store_id}'. Reading that back would mean re-deriving which of its "
        f"columns GuPPy counted as data, which this bridge does not do."
    )
    # GuPPy numbers the data columns from 1, the timestamps being column 0.
    data_column = int(slot_match.group("column"))
    return dict(
        file_path=file_path,
        headerless=headerless,
        excitation_wavelength_in_nm=None,
        slot_index=slot_index,
        num_channels=number_of_channels,
        data_column=data_column,
        timestamps_column=timestamps_column,
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
    Which interface reads them follows from the name: a store naming an excitation wavelength is
    read by selecting that LED's frames, while one naming a cycle position came from a file with no
    state column to select on, so GuPPy's blind stride is reproduced through the generic CSV
    interface instead.

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
        If the stores do not all come from one file and one channel.
    """
    run_parameters = npm_run_parameters(guppy_folder_path)
    demuxes = [
        npm_store_to_demux(folder_path, store_id, number_of_channels=run_parameters["number_of_channels"])
        for store_id in store_ids
    ]
    # A role becomes one interface, so its stores must all be the same channel of the same file;
    # only the column may differ between recording sites.
    distinct = {(demux["file_path"], demux["excitation_wavelength_in_nm"], demux["slot_index"]) for demux in demuxes}
    assert len(distinct) == 1, (
        f"The '{metadata_key}' stores {store_ids} do not share one NPM file and channel "
        f"({sorted(distinct)}), so they cannot be written as one series."
    )
    first = demuxes[0]
    time_unit = run_parameters["time_unit"]
    timestamps_column = run_parameters["timestamp_column_name"] or first["timestamps_column"]

    if first["excitation_wavelength_in_nm"] is None:
        # The file names no LED, so reproduce GuPPy's blind stride. skip_rows carries the cycle
        # position rather than index, which the demux validates against the channel count.
        return CSVFiberPhotometryInterface(
            file_path=first["file_path"],
            data_columns=[demux["data_column"] for demux in demuxes],
            timestamps_column=timestamps_column,
            demux_configuration=StrideDemux(channels=first["num_channels"], index=0, skip_rows=first["slot_index"]),
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
