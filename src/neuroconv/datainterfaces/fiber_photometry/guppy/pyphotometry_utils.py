"""Reading the raw side of a GuPPy session recorded on a pyPhotometry board.

GuPPy names a pyPhotometry store exactly as the interfaces name their streams and lines --
``detector_<n>_excitation_<m>`` for a photometry signal, ``digital_<n>`` for a digital line -- so
neither builder has to translate anything.
"""

from pydantic import DirectoryPath

from ..pyphotometry.pyphotometrydatainterface import PyPhotometryFiberPhotometryInterface
from ...events.pyphotometry_events.pyphotometryeventsdatainterface import (
    PyPhotometryEventsInterface,
)

ASSOCIATED_SUFFIXES = tuple(
    dict.fromkeys(
        PyPhotometryFiberPhotometryInterface.associated_suffixes + PyPhotometryEventsInterface.associated_suffixes
    )
)


def resolve_ppd_file(folder_path: DirectoryPath):
    """Return the one ``.ppd`` file in ``folder_path``.

    GuPPy requires a pyPhotometry session folder to hold exactly one recording and hard-errors
    otherwise.
    """
    candidates = sorted(folder_path.glob("*.ppd"))
    assert len(candidates) == 1, (
        f"Expected exactly one pyPhotometry '.ppd' file in '{folder_path}', found {len(candidates)}: "
        f"{[path.name for path in candidates]}. A GuPPy pyPhotometry session folder holds one recording."
    )
    return candidates[0]


def build_pyphotometry_acquisition_interface(
    *,
    folder_path: DirectoryPath,
    store_ids: list[str],
    metadata_key: str,
    verbose: bool,
) -> PyPhotometryFiberPhotometryInterface:
    """Build the interface writing one series from the ordered ``store_ids``.

    The board samples its analog inputs one after another rather than simultaneously, so no two of
    its signals share a timestamps vector and each is read by an interface of its own. A series can
    therefore hold a single store, which is one recording site per role.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the folder holding the single ``.ppd`` file.
    store_ids : list of str
        The ``storesList.csv`` ids of the stores to stack into this one series, one per recording
        site. Exactly one is supported.
    metadata_key : str
        The key the interface reads its block from under ``metadata["FiberPhotometry"]``.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    PyPhotometryFiberPhotometryInterface
        Reading the one store as a single-column ``FiberPhotometryResponseSeries``.

    Raises
    ------
    AssertionError
        If the folder does not hold exactly one ``.ppd`` file, or if ``store_ids`` names more than one
        store.
    """
    file_path = resolve_ppd_file(folder_path)
    assert len(store_ids) == 1, (
        f"The '{metadata_key}' stores {store_ids} come from {len(store_ids)} recording sites, but a "
        f"pyPhotometry board samples its signals at different instants, so they cannot be written as "
        f"one series. A pyPhotometry GuPPy session converts with one recording site."
    )
    (store_id,) = store_ids
    return PyPhotometryFiberPhotometryInterface(
        file_path=file_path,
        stream_name=store_id,
        metadata_key=metadata_key,
        verbose=verbose,
    )


def build_pyphotometry_events_interface(
    *,
    folder_path: DirectoryPath,
    event_store_ids: list[str],
    verbose: bool,
) -> PyPhotometryEventsInterface:
    """Build the interface reading the raw discrete events.

    pyPhotometry event stores are digital lines of the one ``.ppd`` file, so a single interface covers
    them all.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the folder holding the single ``.ppd`` file. GuPPy writes a session's traces and events
        into one folder, so this is the acquisition folder as well.
    event_store_ids : list of str
        The ``storesList.csv`` ids of the behavioral event stores GuPPy processed, each a digital line
        of the recording. Each becomes one detection spec named for its store id, which makes that id
        the seeded event type source id directly -- no renaming afterwards.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    PyPhotometryEventsInterface
        Reading every digital line ``event_store_ids`` names.

    Raises
    ------
    AssertionError
        If the folder does not hold exactly one ``.ppd`` file.
    """
    file_path = resolve_ppd_file(folder_path)
    # GuPPy keeps a pulse's onset alone, at each low-to-high transition, so the lines are read as
    # "rising" point events to write the onsets GuPPy analyzed. A line arrives 0/1 from the reader,
    # which 'midpoint' cuts between whatever its two levels are -- the identity conditioning for a line.
    detection_configuration = {
        store_id: [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising", "event_name": store_id}]
        for store_id in event_store_ids
    }
    return PyPhotometryEventsInterface(
        file_path=file_path,
        detection_configuration=detection_configuration,
        metadata_key="guppy_pyphotometry_events",
        verbose=verbose,
    )
