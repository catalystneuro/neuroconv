"""Resolving GuPPy's ``storesList.csv`` acquisition ids against the NWB file the outputs are written into.

GuPPy names its acquisition stores as opaque ids, and when the session was processed out of an
existing NWB file those ids are derived from that file's own contents. So when
:class:`~.guppydatainterface.GuppyInterface` is handed an ``NWBFile`` that already holds the
acquisition, the ids address it directly and the recording sites registry can reference the
``FiberPhotometryTable`` that is already there through its ``fiber_photometry_table_region``.

The id spelling mirrors how GuPPy reads an NWB file: a 2-D ``FiberPhotometryResponseSeries``
contributes one store per column, ``<series>_<column>``, and a 1-D one contributes ``<series>``.
"""

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


def resolve_acquisition_store_rows(*, nwbfile, store_ids: list[str]) -> dict[str, int | None]:
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
        ``store_id -> FiberPhotometryTable row index``, holding one entry per store that names a
        series in the file. The row is ``None`` where that series carries no
        ``fiber_photometry_table_region``, which NWB leaves optional, so it states no row.
    """
    series_by_name = _series_by_name(nwbfile)
    store_id_to_row: dict[str, int | None] = {}
    for store_id in store_ids:
        parsed = _parse_acquisition_store_id(store_id, series_by_name)
        if parsed is None:
            continue
        series_name, column_index = parsed
        region = series_by_name[series_name].fiber_photometry_table_region
        store_id_to_row[store_id] = (
            None if region is None else int(region.data[0 if column_index is None else column_index])
        )
    return store_id_to_row
