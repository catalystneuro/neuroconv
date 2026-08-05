"""Reading the raw side of a GuPPy session recorded on a TDT tank.

GuPPy's store ids are the tank's stream and epoc names verbatim, so neither builder has to translate
anything.
"""

from pydantic import DirectoryPath

from ..tdt.tdtfiberphotometrydatainterface import TDTFiberPhotometryInterface
from ...events.tdt_events.tdteventsdatainterface import TDTEventsInterface

ASSOCIATED_SUFFIXES = tuple(
    dict.fromkeys(TDTFiberPhotometryInterface.associated_suffixes + TDTEventsInterface.associated_suffixes)
)


def build_tdt_acquisition_interface(
    *,
    folder_path: DirectoryPath,
    store_ids: list[str],
    metadata_key: str,
    verbose: bool,
) -> TDTFiberPhotometryInterface:
    """Build the interface writing one series from the ordered ``store_ids``.

    GuPPy's TDT store ids are the tank's stream names verbatim, so they pass straight through.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the TDT tank folder, holding the Tbk, Tdx, tev, tin and tsq files.
    store_ids : list of str
        The ``storesList.csv`` ids of the stores to stack into this one series, one per recording
        site. Column order of the resulting series, which must be preserved.
    metadata_key : str
        The key the interface reads its block from under ``metadata["FiberPhotometry"]``.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    TDTFiberPhotometryInterface
        Reading ``store_ids`` as the columns of a single ``FiberPhotometryResponseSeries``.
    """
    return TDTFiberPhotometryInterface(
        folder_path=folder_path,
        stream_names=store_ids,
        metadata_key=metadata_key,
        verbose=verbose,
    )


def build_tdt_events_interface(*, folder_path: DirectoryPath, verbose: bool) -> TDTEventsInterface:
    """Build the interface reading the raw discrete events.

    One interface reads every epoc in the tank and keys each by its epoc name, which is already the
    id ``storesList.csv`` records -- so the event stores need naming neither here nor afterwards.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the TDT tank folder. GuPPy writes a session's traces and events into one folder, so
        this is the acquisition folder as well.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    TDTEventsInterface
        Reading every epoc in the tank.
    """
    return TDTEventsInterface(folder_path=folder_path, verbose=verbose)
