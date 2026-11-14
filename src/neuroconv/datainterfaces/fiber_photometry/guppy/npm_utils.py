"""Reading the raw side of a GuPPy session recorded on a Neurophotometrics system.

A file carrying a ``Flags``/``LedState`` column names the LED that lit each frame, so GuPPy selects a
store's rows by testing that wavelength's bit. A header-less one names no LED, so GuPPy takes every
``noChannels``-th row from the position the store falls on in the cycle instead.

NPM store names are synthetic: GuPPy invents them while demultiplexing an interleaved recording, and
no column of the raw file carries one. A run folder records what each store was demultiplexed from,
which is read as given; one written before GuPPy recorded that leaves only the names, which
:mod:`._legacy_store_names` decodes into the same record. See :func:`npm_store_provenance`.
"""

from pydantic import DirectoryPath

from ._legacy_store_names import decode_legacy_store_name
from ._session_files import is_event_csv
from ..csv._demux import StrideDemux
from ..csv.csvfiberphotometrydatainterface import CSVFiberPhotometryInterface
from ..npm.npmfiberphotometrydatainterface import NPMFiberPhotometryInterface
from ...events.csv_events.csveventsdatainterface import CSVEventsInterface
from ...events.npm_events.npmeventsdatainterface import NPMEventsInterface

ASSOCIATED_SUFFIXES = tuple(
    dict.fromkeys(NPMFiberPhotometryInterface.associated_suffixes + NPMEventsInterface.associated_suffixes)
)


def _npm_column_count(file_path) -> int:
    """Return how many columns a CSV has, which is how GuPPy tells an NPM event file from a data file."""
    import pandas

    return int(pandas.read_csv(file_path, header=None, nrows=1).shape[1])


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
    """Read the session-wide NPM settings the GuPPy run used but ``storesList.csv`` does not record.

    Which clock the stores were read on, what unit they were in, and -- for the header-less layout --
    how many channels were interleaved are all choices made when GuPPy ran, and none leave a mark on
    the raw file. GuPPy records them in a ``.npm_params.json`` beside ``storesList.csv``; runs written
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
    )


def _npm_channel_label(demux: dict) -> str:
    """Describe the file and channel a resolved store came from, for a failure message."""
    channel = (
        f"cycle position {demux['slot_index']}"
        if demux["demultiplex_by"] == "stride"
        else f"{demux['excitation_wavelength_in_nm']} nm"
    )
    return f"{demux['file_path'].name} {channel}"


def npm_store_provenance(
    *,
    folder_path: DirectoryPath,
    guppy_folder_path: DirectoryPath,
    store_ids: list[str],
    timestamp_column_name: str | None = None,
) -> dict[str, dict]:
    """Return what each of ``store_ids`` was demultiplexed from, one record per store.

    An NPM store name is invented: GuPPy makes it up while splitting an interleaved recording, and no
    column of the raw file carries it. A run folder written by a GuPPy that records what it
    demultiplexed says so directly, under ``stores`` in ``.npm_params.json``, and that record is read
    as given. One written before that records only the names, and a record is decoded from each by
    reproducing GuPPy's arithmetic -- see :func:`decode_legacy_store_name`. Either way every
    requested store comes back described the same way.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the raw session folder holding the acquisition CSVs, read only where the records have
        to be decoded.
    guppy_folder_path : DirectoryPath
        Path to the GuPPy ``<session>_output_<N>`` folder holding ``.npm_params.json``.
    store_ids : list of str
        The ``storesList.csv`` ids of the acquisition stores to describe. Behavioral event stores are
        not demultiplexed and are not recorded here.
    timestamp_column_name : str, optional
        The run's ``npm_timestamp_column_name`` from :func:`npm_run_parameters`, used only where the
        records have to be decoded.

    Returns
    -------
    dict
        ``store_id -> {file, excitation_wavelength_in_nm, interleave_position, data_column,
        timestamp_column}``, one entry per requested store.
    """
    import json

    npm_parameters = json.loads((guppy_folder_path / ".npm_params.json").read_text(encoding="utf-8"))
    recorded = npm_parameters.get("stores")
    if not recorded:
        return {
            store_id: decode_legacy_store_name(folder_path, store_id, timestamp_column_name) for store_id in store_ids
        }
    missing = [store_id for store_id in store_ids if store_id not in recorded]
    assert not missing, (
        f"The run folder records what its stores were demultiplexed from but says nothing about "
        f"{missing}, naming {sorted(recorded)} instead. Its 'storesList.csv' and its "
        f"'.npm_params.json' describe different stores, so they were not written by one run."
    )
    return {store_id: recorded[store_id] for store_id in store_ids}


def npm_store_to_demux(folder_path: DirectoryPath, store_id: str, record: dict, *, number_of_channels: int) -> dict:
    """Resolve a store's record to the file, channel and column it is read from.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the raw session folder holding the acquisition CSVs, which ``record`` names by file
        name.
    store_id : str
        The ``storesList.csv`` id the record belongs to, named in the failure messages.
    record : dict
        What the store was demultiplexed from, from :func:`npm_store_provenance`.
    number_of_channels : int
        The run's ``noChannels``, needed only by a store demultiplexed by stride.

    Returns
    -------
    dict
        ``demultiplex_by``, either ``"excitation"`` with the wavelength to select on or ``"stride"``
        with the cycle position to count from, plus the file, the data column and the timestamps
        column, ready to read as they are.
    """
    file_path = folder_path / record["file"]
    assert file_path.is_file(), (
        f"Store '{store_id}' was demultiplexed from '{record['file']}', which is not in "
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
        demultiplex_by="excitation" if wavelength is not None else "stride",
        excitation_wavelength_in_nm=wavelength,
        slot_index=record.get("interleave_position"),
        data_column=record["data_column"],
        timestamps_column=record["timestamp_column"],
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

    Each store is resolved to the file, channel and column GuPPy demultiplexed it from -- see
    :func:`npm_store_provenance`. Which interface reads them follows from what that resolves to: a
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
    provenance = npm_store_provenance(
        folder_path=folder_path,
        guppy_folder_path=guppy_folder_path,
        store_ids=store_ids,
        timestamp_column_name=run_parameters["timestamp_column_name"],
    )
    demuxes = [
        npm_store_to_demux(
            folder_path,
            store_id,
            provenance[store_id],
            number_of_channels=run_parameters["number_of_channels"],
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

    if first["demultiplex_by"] == "stride":
        return CSVFiberPhotometryInterface(
            file_path=first["file_path"],
            data_columns=[demux["data_column"] for demux in demuxes],
            timestamps_column=timestamps_column,
            demux_configuration=StrideDemux(channels=run_parameters["number_of_channels"], index=first["slot_index"]),
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
