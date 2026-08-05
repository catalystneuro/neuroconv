"""Reading the raw side of a GuPPy session that was itself recorded in NWB.

The other four formats read a binary layout off disk. This one reads an NWB file, which GuPPy also
accepts as an input format, and writes what it finds into the fresh file the converter builds --
alongside the GuPPy outputs, exactly as for a tank or a set of CSVs.

Unlike its four siblings, this module defines the interfaces it returns. Nothing else in NeuroConv
reads an NWB file as a *source*, so there is no public interface to wrap; both classes are private to
this format.

GuPPy derives its ``storesList.csv`` ids from the file's own contents, so the ids are self-describing
and the translation runs both ways here:

* a 2-D ``FiberPhotometryResponseSeries`` contributes one store per column, ``<series>_<column>``,
  and a 1-D one contributes ``<series>``;
* a core ``EventsTable`` contributes ``<table>_<value>`` per distinct value of its one value column,
  or ``<table>`` when it has none;
* the ndx-events v0.2 types (``AnnotatedEventsTable``, ``LabeledEvents``, ``Events``) contribute one
  store per label.

Reading them back needs no ndx-events install: NWB files cache their extension namespaces and
``read_nwb`` loads them, so pynwb builds the classes from the file's own cached spec when the package
is absent. Dispatch is therefore on the ``neurodata_type`` string rather than on imported classes,
which also makes it independent of which ndx-events version wrote the file. The one attribute whose
name depends on that -- ``LabeledEvents``' labels -- is read whichever way it is present.
"""

from pathlib import Path

import numpy as np
from pydantic import DirectoryPath, FilePath
from pynwb import read_nwb

from ..basefiberphotometryinterface import BaseFiberPhotometryInterface
from ...events.baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools.fiber_photometry import (
    _ROW_DEVICE_KEY_FIELDS,
    _get_fiber_photometry_lab_metadata,
)
from ....utils import DeepDict, dict_deep_update

ASSOCIATED_SUFFIXES = ("nwb",)

_RESPONSE_SERIES_TYPE = "FiberPhotometryResponseSeries"
# The two columns a core EventsTable carries by role rather than as data; anything else is the value
# column GuPPy splits the table on.
_RESERVED_EVENT_COLUMNS = ("timestamp", "duration")
# Row keys for the reverse-mapped FiberPhotometryTable. The write side resolves a region's row keys to
# indices by their position in this dict (``get_fiber_photometry_table_region``), so numbering them by
# source row index keeps row *i* of the source at row *i* of the fresh file.
_ROW_KEY_TEMPLATE = "row{index}"


def resolve_nwb_file(folder_path: DirectoryPath) -> Path:
    """Return the single ``.nwb`` file in ``folder_path``.

    GuPPy locates a session's NWB file by globbing its folder, so a session folder holding two of them
    is ambiguous to GuPPy and to the converter alike.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the folder holding the source NWB file.

    Returns
    -------
    Path
        The one ``.nwb`` file in the folder.

    Raises
    ------
    AssertionError
        If the folder holds no ``.nwb`` file, or more than one.
    """
    file_paths = sorted(Path(folder_path).glob("*.nwb"))
    assert len(file_paths) == 1, (
        f"Expected exactly one '.nwb' file in '{folder_path}' but found {len(file_paths)} "
        f"({[path.name for path in file_paths]}). A GuPPy session folder holds one NWB file."
    )
    return file_paths[0]


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


def _parse_acquisition_store_id(store_id: str, series_by_name: dict) -> tuple[str, int | None]:
    """Resolve an acquisition store id to its series name and column index.

    An exact series name wins over the ``<series>_<column>`` reading, which is what keeps a series
    literally named ``Signal_0`` distinguishable from column 0 of a series named ``Signal``.

    Returns
    -------
    tuple of (str, int or None)
        The series name and the column to take, or ``None`` for a 1-D series.
    """
    if store_id in series_by_name:
        return store_id, None

    series_name, _, suffix = store_id.rpartition("_")
    assert suffix.isdigit() and series_name in series_by_name, (
        f"GuPPy store '{store_id}' does not name any FiberPhotometryResponseSeries in the source NWB "
        f"file (available: {sorted(series_by_name)}). A multi-channel series is addressed as "
        f"'<series_name>_<column_index>'."
    )
    return series_name, int(suffix)


def _series_timestamps(series) -> np.ndarray:
    """Return the timestamps of a response series, reconstructing them from the rate when implicit."""
    if series.timestamps is not None:
        return np.asarray(series.timestamps[:], dtype="float64")
    starting_time = series.starting_time or 0.0
    return starting_time + np.arange(series.data.shape[0], dtype="float64") / series.rate


def _events_table_value_column(table) -> str | None:
    """Return the column a core ``EventsTable`` is split on, or ``None`` when it has none.

    Raises
    ------
    NotImplementedError
        If the table carries more than one value column, which GuPPy also refuses to split.
    """
    value_columns = [column for column in table.colnames if column not in _RESERVED_EVENT_COLUMNS]
    if not value_columns:
        return None
    if len(value_columns) > 1:
        raise NotImplementedError(
            f"EventsTable '{table.name}' has multiple value columns {value_columns}, so GuPPy cannot "
            "split it into event stores and neither can this interface."
        )
    return value_columns[0]


def _labeled_events_labels(neurodata_object) -> list:
    """Return a ``LabeledEvents`` object's labels.

    The attribute name depends on which class pynwb instantiated: the hand-written
    ``ndx_events.LabeledEvents`` (registered once ``ndx_events`` is imported) exposes ``labels``, while
    the class generated from the file's own cached spec exposes ``data__labels``.
    """
    if hasattr(neurodata_object, "labels"):
        return list(neurodata_object.labels)
    return list(neurodata_object.data__labels)


def _event_sources(nwbfile) -> dict[str, _EventsData]:
    """Map every event store id the file offers to its occurrences.

    Covers the same sources GuPPy's NWB reader does: core ``EventsTable`` objects in ``nwbfile.events``
    and the ndx-events v0.2 types anywhere in the file. Because the converter re-normalizes everything
    into one merged ``EventsTable``, the source's layout constrains nothing downstream -- only the
    timestamps (and durations, where the source records them) are carried across.
    """
    event_sources: dict[str, _EventsData] = {}

    for table_name, table in (nwbfile.events or {}).items():
        timestamps = np.asarray(table["timestamp"][:], dtype="float64")
        durations = np.asarray(table["duration"][:], dtype="float64") if "duration" in table.colnames else None
        value_column = _events_table_value_column(table)
        if value_column is None:
            event_sources[table_name] = _EventsData(
                event_type_source_id=table_name, timestamps=timestamps, durations=durations
            )
            continue
        values = np.asarray(table[value_column][:])
        for value in np.unique(values):
            selection = values == value
            event_sources[f"{table_name}_{value}"] = _EventsData(
                event_type_source_id=f"{table_name}_{value}",
                timestamps=timestamps[selection],
                durations=None if durations is None else durations[selection],
            )

    for neurodata_object in nwbfile.objects.values():
        neurodata_type = getattr(neurodata_object, "neurodata_type", None)
        name = getattr(neurodata_object, "name", None)
        if neurodata_type == "AnnotatedEventsTable":
            for row_index, label in enumerate(neurodata_object["label"].data):
                store_id = f"{name}_{label}"
                event_sources[store_id] = _EventsData(
                    event_type_source_id=store_id,
                    timestamps=np.asarray(neurodata_object["event_times"][row_index], dtype="float64"),
                )
        elif neurodata_type == "LabeledEvents":
            all_timestamps = np.asarray(neurodata_object.timestamps[:], dtype="float64")
            all_data = np.asarray(neurodata_object.data[:])
            for label_index, label in enumerate(_labeled_events_labels(neurodata_object)):
                store_id = f"{name}_{label}"
                event_sources[store_id] = _EventsData(
                    event_type_source_id=store_id, timestamps=all_timestamps[all_data == label_index]
                )
        elif neurodata_type == "Events":
            event_sources[name] = _EventsData(
                event_type_source_id=name,
                timestamps=np.asarray(neurodata_object.timestamps[:], dtype="float64"),
            )

    return event_sources


def _container_to_metadata(container, *, include_type: bool = False, reference_fields: dict | None = None) -> dict:
    """Reverse-map an NWB container into the metadata dict its ``add_*`` helper builds it from.

    The write side constructs each container from a dict of constructor arguments, so the reverse is
    the container's own field map. A field naming another registry entry (a device's ``model``, an
    indicator's ``viral_vector_injection``) becomes the corresponding ``*_metadata_key``; a nested
    inline container (an optical fiber's ``fiber_insertion``) becomes a nested dict.

    Parameters
    ----------
    container : pynwb container
        The object to describe.
    include_type : bool, default: False
        Whether to record the concrete class under ``"type"``. The device helpers resolve the class
        from that key; the virus, injection and indicator helpers instead pass the entry straight to a
        fixed class, so a ``"type"`` key would reach the constructor as an unrecognized argument.
    reference_fields : dict, optional
        ``{field_name: metadata_key_field}`` for fields that must become a key reference rather than
        an inline dict.

    Returns
    -------
    dict
        The metadata entry, keyed the way the corresponding ``add_*`` helper expects.
    """
    reference_fields = reference_fields or {}
    # ``name`` identifies the container but is not always one of its ``fields``, so it is restored
    # explicitly; every registry entry is required to carry one.
    metadata = {"name": container.name}
    if include_type:
        metadata["type"] = type(container).__name__
    for field_name, value in container.fields.items():
        if value is None:
            continue
        if field_name in reference_fields:
            metadata[reference_fields[field_name]] = value.name
        elif hasattr(value, "fields"):
            metadata[field_name] = {
                nested_name: nested_value
                for nested_name, nested_value in value.fields.items()
                if nested_value is not None
            }
        else:
            metadata[field_name] = value
    return metadata


class _NwbFiberPhotometryInterface(BaseFiberPhotometryInterface):
    """Read ``FiberPhotometryResponseSeries`` columns out of a source NWB file.

    Private to :mod:`~.nwb_utils`: it exists so a GuPPy session recorded in NWB reaches the converter
    through the same seam as one recorded on a tank, and it addresses its streams by the store ids
    GuPPy derived from the very same file.

    Unlike every other fiber photometry interface, it supplies its own ``FiberPhotometry`` provenance:
    the source file already states that chain -- device models, devices, indicators, viruses,
    injections, the ``FiberPhotometryTable``, and this series' region -- so :meth:`get_metadata`
    returns it read back out of the source. It is ordinary metadata and can still be overridden.
    """

    display_name = "NWB Fiber Photometry"
    associated_suffixes = ASSOCIATED_SUFFIXES
    info = "Interface for reading fiber photometry response series out of an existing NWB file."

    @classmethod
    def get_available_streams(cls, file_path: FilePath) -> list[str]:
        """Return the acquisition store ids GuPPy derives from ``file_path``.

        One id per column of each multi-channel ``FiberPhotometryResponseSeries``, and one per
        single-channel series, in the order the file lists them.
        """
        nwbfile = read_nwb(path=str(file_path))
        store_ids = []
        for series_name, series in _series_by_name(nwbfile).items():
            data_shape = series.data.shape
            if len(data_shape) == 2:
                store_ids.extend(f"{series_name}_{column_index}" for column_index in range(data_shape[1]))
            else:
                store_ids.append(series_name)
        return store_ids

    def __init__(
        self,
        *,
        file_path: FilePath,
        stream_names: list[str],
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the source-NWB fiber photometry interface.

        Parameters
        ----------
        file_path : FilePath
            Path to the source NWB file.
        stream_names : list of str
            The ``storesList.csv`` ids to stack into this one series, in column order.
        metadata_key : str, optional
            The key the interface reads its block from under ``metadata["FiberPhotometry"]``.
        verbose : bool, default: False
            Whether to print status messages.
        """
        super().__init__(stream_names=stream_names, metadata_key=metadata_key, verbose=verbose, file_path=file_path)
        # Held for the interface's lifetime: read_nwb retains the IO on the returned file, and the
        # series data is sliced lazily during add_to_nwbfile, long after construction.
        self._source_nwbfile = read_nwb(path=str(file_path))
        self._series_by_name = _series_by_name(self._source_nwbfile)
        for stream_name in self.stream_names:
            _parse_acquisition_store_id(stream_name, self._series_by_name)

    def _get_stream_data(self, *, stream_name: str) -> np.ndarray:
        series_name, column_index = _parse_acquisition_store_id(stream_name, self._series_by_name)
        data = self._series_by_name[series_name].data
        return np.asarray(data[:] if column_index is None else data[:, column_index])

    def _get_stream_timestamps(self, *, stream_name: str) -> np.ndarray:
        series_name, _ = _parse_acquisition_store_id(stream_name, self._series_by_name)
        return _series_timestamps(self._series_by_name[series_name])

    def _table_row_key_for(self, stream_name: str) -> str:
        """Return the ``FiberPhotometryTable`` row key of the store's own fiber.

        A series states which table rows its columns were recorded on, so the row belonging to a store
        is the region entry at that store's column -- the source answers by itself what the other
        formats need the user to declare.
        """
        series_name, column_index = _parse_acquisition_store_id(stream_name, self._series_by_name)
        region = self._series_by_name[series_name].fiber_photometry_table_region
        return _ROW_KEY_TEMPLATE.format(index=int(region.data[0 if column_index is None else column_index]))

    def get_metadata(self) -> DeepDict:
        """Return the base metadata enriched with the source file's fiber photometry provenance.

        A source carrying no ``FiberPhotometryTable`` (a bare response series is a legal NWB write)
        contributes no chain, and the metadata is left as the base class seeds it.
        """
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = self._source_nwbfile.session_start_time
        lab_metadata = _get_fiber_photometry_lab_metadata(self._source_nwbfile)
        if lab_metadata is None:
            return metadata

        table = lab_metadata.fiber_photometry_table
        ndx_field_to_key_field = {ndx_field: key_field for key_field, ndx_field in _ROW_DEVICE_KEY_FIELDS.items()}

        device_models_metadata: dict = {}
        devices_metadata: dict = {}
        rows_metadata: dict = {}
        for row_index in range(len(table)):
            row_metadata: dict = {}
            for column_name in table.colnames:
                value = table[column_name][row_index]
                if column_name in ndx_field_to_key_field:
                    row_metadata[ndx_field_to_key_field[column_name]] = value.name
                    devices_metadata[value.name] = _container_to_metadata(
                        value, include_type=True, reference_fields={"model": "device_model_metadata_key"}
                    )
                    if value.model is not None:
                        device_models_metadata[value.model.name] = _container_to_metadata(
                            value.model, include_type=True
                        )
                elif column_name == "indicator":
                    row_metadata["indicator_metadata_key"] = value.name
                elif column_name == "commanded_voltage_series":
                    row_metadata["commanded_voltage_series_metadata_key"] = value.name
                else:
                    row_metadata[column_name] = value
            rows_metadata[_ROW_KEY_TEMPLATE.format(index=row_index)] = row_metadata

        fiber_photometry_metadata: dict = {
            "FiberPhotometryTable": dict(name=table.name, description=table.description, rows=rows_metadata),
            self.metadata_key: dict(
                fiber_photometry_table_region=[
                    self._table_row_key_for(stream_name) for stream_name in self.stream_names
                ]
            ),
        }

        viruses = lab_metadata.fiber_photometry_viruses
        if viruses is not None:
            fiber_photometry_metadata["FiberPhotometryViruses"] = {
                viral_vector.name: _container_to_metadata(viral_vector)
                for viral_vector in viruses.viral_vectors.values()
            }
        injections = lab_metadata.fiber_photometry_virus_injections
        if injections is not None:
            fiber_photometry_metadata["FiberPhotometryVirusInjections"] = {
                injection.name: _container_to_metadata(
                    injection, reference_fields={"viral_vector": "viral_vector_metadata_key"}
                )
                for injection in injections.viral_vector_injections.values()
            }
        fiber_photometry_metadata["FiberPhotometryIndicators"] = {
            indicator.name: _container_to_metadata(
                indicator, reference_fields={"viral_vector_injection": "viral_vector_injection_metadata_key"}
            )
            for indicator in lab_metadata.fiber_photometry_indicators.indicators.values()
        }

        return dict_deep_update(
            metadata,
            dict(
                DeviceModels=device_models_metadata,
                Devices=devices_metadata,
                FiberPhotometry=fiber_photometry_metadata,
            ),
        )


class _NwbEventsInterface(BaseEventsInterface):
    """Read behavioral event occurrences out of a source NWB file.

    Private to :mod:`~.nwb_utils`. Reads only the stores GuPPy listed, keyed by the ids GuPPy derived
    from this same file, so the converter's join against ``storesList.csv`` runs on identity.
    """

    display_name = "NWB Events"
    associated_suffixes = ASSOCIATED_SUFFIXES
    info = "Interface for reading discrete events out of an existing NWB file."

    @classmethod
    def get_available_streams(cls, file_path: FilePath) -> list[str]:
        """Return the event store ids GuPPy derives from ``file_path``."""
        return list(_event_sources(read_nwb(path=str(file_path))))

    def __init__(
        self,
        *,
        file_path: FilePath,
        event_store_ids: list[str],
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the source-NWB events interface.

        Parameters
        ----------
        file_path : FilePath
            Path to the source NWB file.
        event_store_ids : list of str
            The ``storesList.csv`` ids of the behavioral event stores to read.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` namespacing this interface's events metadata.
            If None (default), ``"guppy_nwb_events"`` is used.
        verbose : bool, default: False
            Whether to print status messages.
        """
        super().__init__(file_path=file_path, event_store_ids=event_store_ids, verbose=verbose)
        self.metadata_key = metadata_key or "guppy_nwb_events"
        self._source_nwbfile = read_nwb(path=str(file_path))
        self._get_events_data_dict()

    def get_metadata(self) -> DeepDict:
        """Seed one event type per requested store, named by the store id.

        The source's own names for its event types are GuPPy's store ids, so the join is the identity
        and the converter renames each type afterwards from ``storesList.csv``.
        """
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = self._source_nwbfile.session_start_time
        for event_type_source_id in self._get_events_data_dict():
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = {
                "event_name": event_type_source_id
            }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation from the source file, cached after the first call."""
        if self._events_data_dict is not None:
            return self._events_data_dict

        event_sources = _event_sources(self._source_nwbfile)
        event_store_ids = self.source_data["event_store_ids"]
        missing = [store_id for store_id in event_store_ids if store_id not in event_sources]
        assert not missing, (
            f"GuPPy's storesList.csv lists behavioral event store(s) {missing} that the source NWB file "
            f"does not provide (available: {sorted(event_sources)})."
        )
        self._events_data_dict = {store_id: event_sources[store_id] for store_id in event_store_ids}
        return self._events_data_dict


def build_nwb_acquisition_interface(
    *,
    folder_path: DirectoryPath,
    store_ids: list[str],
    metadata_key: str,
    verbose: bool,
) -> _NwbFiberPhotometryInterface:
    """Build the interface writing one series from the ordered ``store_ids``.

    GuPPy's NWB store ids name a response series and, for a multi-channel one, a column of it, so they
    address the source file directly and need no translation.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the folder holding the source NWB file.
    store_ids : list of str
        The ``storesList.csv`` ids of the stores to stack into this one series, one per recording
        site. Column order of the resulting series, which must be preserved.
    metadata_key : str
        The key the interface reads its block from under ``metadata["FiberPhotometry"]``.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    _NwbFiberPhotometryInterface
        Reading ``store_ids`` as the columns of a single ``FiberPhotometryResponseSeries``.
    """
    return _NwbFiberPhotometryInterface(
        file_path=resolve_nwb_file(folder_path),
        stream_names=store_ids,
        metadata_key=metadata_key,
        verbose=verbose,
    )


def build_nwb_events_interface(
    *,
    folder_path: DirectoryPath,
    event_store_ids: list[str],
    verbose: bool,
) -> _NwbEventsInterface:
    """Build the interface reading the raw discrete events.

    One interface reads every store GuPPy listed, whichever object in the file holds it, and keys each
    by the id ``storesList.csv`` records -- so the event stores need naming neither here nor
    afterwards.

    Parameters
    ----------
    folder_path : DirectoryPath
        Path to the folder holding the source NWB file. GuPPy reads a session's traces and events from
        one file, so this is the acquisition folder as well.
    event_store_ids : list of str
        The ``storesList.csv`` ids of the behavioral event stores to read.
    verbose : bool
        Whether the interface should print status messages.

    Returns
    -------
    _NwbEventsInterface
        Reading every listed event store out of the source file.
    """
    return _NwbEventsInterface(
        file_path=resolve_nwb_file(folder_path),
        event_store_ids=event_store_ids,
        verbose=verbose,
    )
