"""Resolving GuPPy's ``storesList.csv`` ids against the NWB file the outputs are written into.

GuPPy names its acquisition and event stores as opaque ids, and when the session was processed out
of an existing NWB file those ids are derived from that file's own contents. So when
:class:`~.guppydatainterface.GuppyInterface` is handed an ``NWBFile`` that already holds the
acquisition, the ids address it directly and the two GuPPy registries can reference the tables that
are already there -- the recording sites' ``fiber_photometry_table_region`` into the existing
``FiberPhotometryTable``, and the events' ``events`` region into the existing ``EventsTable``.

The two id spellings, which mirror how GuPPy reads an NWB file:

* a 2-D ``FiberPhotometryResponseSeries`` contributes one store per column, ``<series>_<column>``,
  and a 1-D one contributes ``<series>``;
* a core ``EventsTable`` contributes ``<table>_<value>`` per distinct value of its one value column,
  or ``<table>`` when it has none.

Only those two are addressable by row, which is what a ``DynamicTableRegion`` needs. Events held as
ndx-events v0.2 objects, or spread over several tables, resolve to nothing here; the interface then
writes GuPPy's own analyzed onsets as an ``EventsTable`` and references those instead.
"""

import numpy as np

# The two columns a core EventsTable carries by role rather than as data; anything else is the value
# column GuPPy splits the table on.
_RESERVED_EVENT_COLUMNS = ("timestamp", "duration")
_RESPONSE_SERIES_TYPE = "FiberPhotometryResponseSeries"


def _series_by_name(nwbfile) -> dict:
    """Return every ``FiberPhotometryResponseSeries`` in the file, keyed by name.

    Searches ``nwbfile.objects`` rather than ``nwbfile.acquisition`` because GuPPy accepts a series
    anywhere in the file, including inside a processing module.
    """
    return {
        neurodata_object.name: neurodata_object
        for neurodata_object in nwbfile.objects.values()
        if getattr(neurodata_object, "neurodata_type", None) == _RESPONSE_SERIES_TYPE
    }


def _parse_acquisition_store_id(store_id: str, series_by_name: dict) -> tuple[str, int | None] | None:
    """Resolve an acquisition store id to its series name and column index, or ``None`` if it names none.

    An exact series name wins over the ``<series>_<column>`` reading, which is what keeps a series
    literally named ``Signal_0`` distinguishable from column 0 of a series named ``Signal``.
    """
    if store_id in series_by_name:
        return store_id, None

    series_name, _, suffix = store_id.rpartition("_")
    if not suffix.isdigit() or series_name not in series_by_name:
        return None
    return series_name, int(suffix)


def _events_table_value_column(table) -> str | None:
    """Return the column a core ``EventsTable`` is split on, or ``None`` when it has none.

    A table carrying several value columns is one GuPPy cannot split into stores either, so it
    contributes nothing rather than being guessed at.
    """
    value_columns = [column for column in table.colnames if column not in _RESERVED_EVENT_COLUMNS]
    if len(value_columns) != 1:
        return None
    return value_columns[0]


def resolve_acquisition_store_rows(*, nwbfile, store_ids: list[str]) -> dict[str, int]:
    """Map each acquisition store to the ``FiberPhotometryTable`` row its fiber occupies.

    A series states which table rows its columns were recorded on, so the row belonging to a store is
    that series' region entry at the store's column -- the file answers by itself what a raw-format
    conversion needs the user to declare.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        The file being written into, already holding the acquisition.
    store_ids : list of str
        The ``storesList.csv`` acquisition store ids to resolve.

    Returns
    -------
    dict
        ``store_id -> FiberPhotometryTable row index``, holding only the stores the file answers for.
    """
    series_by_name = _series_by_name(nwbfile)
    store_id_to_row: dict[str, int] = {}
    for store_id in store_ids:
        parsed = _parse_acquisition_store_id(store_id, series_by_name)
        if parsed is None:
            continue
        series_name, column_index = parsed
        region = series_by_name[series_name].fiber_photometry_table_region
        if region is None:
            continue
        store_id_to_row[store_id] = int(region.data[0 if column_index is None else column_index])
    return store_id_to_row


def resolve_event_store_rows(*, nwbfile, event_store_ids: list[str]) -> tuple[object, dict[str, list[int]]] | None:
    """Find the one ``EventsTable`` holding every listed event store, and the rows each occupies.

    All of them must live in a single table: the registry references them through one
    ``DynamicTableRegion``, which has one target. A store the file does not offer, or stores spread
    over several tables, means the events cannot be referenced where they lie.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        The file being written into.
    event_store_ids : list of str
        The ``storesList.csv`` ids of the behavioral event stores GuPPy listed.

    Returns
    -------
    tuple or None
        ``(events_table, {store_id: row indices})``, or ``None`` when the stores cannot all be
        referenced in one table.
    """
    if not event_store_ids:
        return None

    store_rows: dict[str, tuple[str, list[int]]] = {}
    for table_name, table in (nwbfile.events or {}).items():
        value_column = _events_table_value_column(table)
        if value_column is None:
            store_rows[table_name] = (table_name, list(range(len(table))))
            continue
        values = np.asarray(table[value_column][:])
        for value in np.unique(values):
            rows = [int(row) for row in np.flatnonzero(values == value)]
            store_rows[f"{table_name}_{value}"] = (table_name, rows)

    if any(store_id not in store_rows for store_id in event_store_ids):
        return None
    table_names = {store_rows[store_id][0] for store_id in event_store_ids}
    if len(table_names) > 1:
        return None
    return nwbfile.events[table_names.pop()], {store_id: store_rows[store_id][1] for store_id in event_store_ids}


def select_analyzed_rows(
    *,
    event_name: str,
    candidate_rows: list[int],
    candidate_timestamps: np.ndarray,
    analyzed_onsets: np.ndarray,
) -> list[int]:
    """Pick the events-table rows whose timestamps are the ones GuPPy kept for this event.

    GuPPy drops onsets it cannot build a trial around, so the table legitimately holds occurrences
    that no GuPPy product covers. Matching is by timestamp rather than by position because GuPPy
    applies its own time correction on the way to writing them -- which also means a store id that
    resolved to the wrong rows fails here rather than linking to unrelated occurrences.

    Raises
    ------
    AssertionError
        If any GuPPy onset does not correspond to exactly one row.
    """
    analyzed_rows = []
    for onset in analyzed_onsets:
        matches = np.flatnonzero(np.isclose(candidate_timestamps, onset, rtol=0.0, atol=1e-6))
        assert matches.size == 1, (
            f"GuPPy analyzed an onset of {onset} s for event '{event_name}', which matches "
            f"{matches.size} of its occurrences in the events table. Every GuPPy onset must "
            f"correspond to exactly one occurrence; none means the two disagree about the event's "
            f"time base (GuPPy counts seconds from recording start, so an acquisition clock carrying "
            f"any other origin will not line up), several means the occurrences are ambiguous."
        )
        analyzed_rows.append(candidate_rows[int(matches[0])])
    return analyzed_rows
