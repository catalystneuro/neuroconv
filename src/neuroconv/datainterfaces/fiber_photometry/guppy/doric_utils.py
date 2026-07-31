"""Reading the raw side of a GuPPy session recorded on a Doric system.

Covers all three Doric layouts -- modern and legacy ``.doric`` HDF5 and DoricStudio ``.csv`` exports
-- resolved from the one acquisition file the session folder holds. This is the first format whose
GuPPy store ids are not the interface's stream names, which is why it needs real translation rather
than a pass-through.
"""

from pydantic import DirectoryPath

from ._session_files import is_event_csv
from ..doric.doricfiberphotometrydatainterface import DoricFiberPhotometryInterface
from ...events.doric_events.doriccsveventsdatainterface import DoricCSVEventsInterface
from ...events.doric_events.doriceventsdatainterface import DoricEventsInterface

ASSOCIATED_SUFFIXES = tuple(
    dict.fromkeys(DoricFiberPhotometryInterface.associated_suffixes + DoricEventsInterface.associated_suffixes)
)


def resolve_doric_file(folder_path: DirectoryPath):
    """Return the one Doric acquisition file in ``folder_path``.

    GuPPy requires a Doric session folder to hold exactly one acquisition file and hard-errors
    otherwise, so this mirrors that rule rather than guessing. Single-column ``timestamps`` CSVs are
    event files, not acquisition, and are excluded the way GuPPy excludes them.
    """
    candidates = sorted(folder_path.glob("*.doric")) + [
        path for path in sorted(folder_path.glob("*.csv")) if not is_event_csv(path)
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


def build_doric_acquisition_interface(
    *,
    folder_path: DirectoryPath,
    store_ids: list[str],
    metadata_key: str,
    verbose: bool,
) -> DoricFiberPhotometryInterface:
    """Build the interface writing one series from the ordered ``store_ids``.

    Doric store ids are abbreviated internal paths, so each is translated to the stream name the
    interface knows before being handed over.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the folder holding the single ``.doric`` or DoricStudio ``.csv`` export.
    store_ids : list of str
        The ``storesList.csv`` ids of the stores to stack into this one series, one per recording
        site. Column order of the resulting series, which must be preserved.
    metadata_key : str
        The key the interface reads its block from under ``metadata["FiberPhotometry"]``.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    DoricFiberPhotometryInterface
        Reading ``store_ids`` as the columns of a single ``FiberPhotometryResponseSeries``.

    Raises
    ------
    AssertionError
        If the folder does not hold exactly one acquisition file, or if a store id does not resolve
        to a stream the file provides.
    """
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


def build_doric_events_interface(
    *,
    folder_path: DirectoryPath,
    event_store_ids: list[str],
    verbose: bool,
):
    """Build the interface reading the raw discrete events.

    Doric event stores are digital lines of the one acquisition file, so a single interface covers
    them all -- which of the two events interfaces reads it depends on whether that file is an HDF5
    export or a DoricStudio CSV.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the folder holding the single ``.doric`` or DoricStudio ``.csv`` export. GuPPy writes
        a session's traces and events into one folder, so this is the acquisition folder as well.
    event_store_ids : list of str
        The ``storesList.csv`` ids of the behavioral event stores GuPPy processed, each a digital
        line of the acquisition file. Each becomes one detection spec named for its store id, which
        makes that id the seeded event type source id directly -- no renaming afterwards.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    DoricEventsInterface or DoricCSVEventsInterface
        Reading every digital line ``event_store_ids`` names, matched to the acquisition file's type.

    Raises
    ------
    AssertionError
        If the folder does not hold exactly one acquisition file.
    """
    file_path = resolve_doric_file(folder_path)
    is_csv_export = file_path.suffix.lower() == ".csv"
    # The interface's signal ids match GuPPy's store ids except in the modern HDF5 layout, where
    # GuPPy prefixes the containing group: 'DigitalIO/CAM1' against the interface's 'CAM1'. Only that
    # layout is stripped -- doing it blindly would turn the CSV store 'DI/O-1' into 'O-1'.
    store_id_to_signal_id = {
        store_id: (
            store_id[len("DigitalIO/") :] if not is_csv_export and store_id.startswith("DigitalIO/") else store_id
        )
        for store_id in event_store_ids
    }
    # Naming the GuPPy store id as the spec's event_name makes it the seeded event_type_source_id, so
    # the converter's select/rename/route blocks join on it exactly as they do for the other formats.
    # (The display name is overwritten with GuPPy's label there.)
    detection_configuration = {
        signal_id: [{"detection": "high_period", "event_name": store_id}]
        for store_id, signal_id in store_id_to_signal_id.items()
    }
    events_interface_class = DoricCSVEventsInterface if is_csv_export else DoricEventsInterface
    return events_interface_class(
        file_path=file_path,
        detection_configuration=detection_configuration,
        metadata_key="guppy_doric_events",
        verbose=verbose,
    )
