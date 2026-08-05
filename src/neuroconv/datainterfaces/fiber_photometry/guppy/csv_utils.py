"""Reading the raw side of a GuPPy session recorded in GuPPy's own CSV layout.

One file per store, named for the store, with a fixed header: ``timestamps``/``data`` for a trace and
a lone ``timestamps`` column for an event. Store ids are therefore filename stems, and each names
exactly one file.
"""

from pydantic import DirectoryPath

from ..csv.multifilecsvfiberphotometrydatainterface import (
    MultiFileCSVFiberPhotometryInterface,
)
from ...events.csv_events.csveventsdatainterface import CSVEventsInterface

ASSOCIATED_SUFFIXES = tuple(
    dict.fromkeys(MultiFileCSVFiberPhotometryInterface.associated_suffixes + CSVEventsInterface.associated_suffixes)
)


def build_csv_acquisition_interface(
    *,
    folder_path: DirectoryPath,
    store_ids: list[str],
    metadata_key: str,
    verbose: bool,
) -> MultiFileCSVFiberPhotometryInterface:
    """Build the interface writing one series from the ordered ``store_ids``.

    GuPPy writes one CSV per store, named for the store, with a fixed timestamps/data header. The
    interface stacks them in file order and asserts they share a time axis.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the folder holding one ``<store>.csv`` per store.
    store_ids : list of str
        The ``storesList.csv`` ids of the stores to stack into this one series, one per recording
        site. Column order of the resulting series, which must be preserved.
    metadata_key : str
        The key the interface reads its block from under ``metadata["FiberPhotometry"]``.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    MultiFileCSVFiberPhotometryInterface
        Reading ``store_ids`` as the columns of a single ``FiberPhotometryResponseSeries``.
    """
    return MultiFileCSVFiberPhotometryInterface(
        file_paths=[folder_path / f"{store_id}.csv" for store_id in store_ids],
        data_columns="data",
        timestamps_column="timestamps",
        metadata_key=metadata_key,
        verbose=verbose,
    )


def build_csv_events_interface(
    *,
    folder_path: DirectoryPath,
    store_id: str,
    verbose: bool,
) -> CSVEventsInterface:
    """Build the interface reading one event store's file.

    This is the format whose stores do not share a source: each is its own file, and
    ``CSVEventsInterface`` reads one file apiece, so a session needs as many of these as it has event
    stores. A GuPPy event CSV is a single ``timestamps`` column, so there is no event-type column to
    split on; with ``event_type_column=None`` the lone type is keyed by the file stem, which is
    already the store id.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the folder holding one ``<store>.csv`` per event store.
    store_id : str
        The ``storesList.csv`` id of the store to read, which names its file.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    CSVEventsInterface
        Reading ``<store_id>.csv`` as a single event type.
    """
    return CSVEventsInterface(
        file_path=folder_path / f"{store_id}.csv",
        timestamps_column="timestamps",
        event_type_column=None,
        metadata_key=store_id,
        verbose=verbose,
    )
