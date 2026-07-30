from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from .guppydatainterface import (
    _EVENTS_TABLE_DESCRIPTION,
    _EVENTS_TABLE_NAME,
    _RECORDING_SITES_TABLE_DESCRIPTION,
    _RECORDING_SITES_TABLE_NAME,
    _GuppyInterface,
)
from ..tdt.tdtfiberphotometrydatainterface import TDTFiberPhotometryInterface
from ...events.tdt_events.tdteventsdatainterface import TDTEventsInterface
from ....nwbconverter import ConverterPipe
from ....tools import get_package
from ....tools.fiber_photometry import get_fiber_photometry_table
from ....tools.nwb_helpers import get_module

# GuPPy stores are labeled by role in storesList.csv; each becomes one single-series acquisition
# interface (and one FiberPhotometryTable row). The order here fixes the per-recording-site row order.
_STORE_ROLES = ("signal", "control")
# The single merged EventsTable every behavioral event type is written into (one DynamicTableRegion
# from the GuppyEventsTable then references its occurrence rows).
_MERGED_EVENTS_TABLE_KEY = "guppy_behavioral_events"
_MERGED_EVENTS_TABLE_NAME = "BehavioralEvents"


class TDTFiberPhotometryGuppyConverter(ConverterPipe):
    """Bundle raw TDT fiber photometry acquisition, raw events, and GuPPy-derived processing outputs.

    Combines the three parts of a GuPPy session: the raw TDT acquisition (added to
    ``nwbfile.acquisition`` via the ``ndx-fiber-photometry`` extension), :class:`TDTEventsInterface`
    (raw discrete events/epocs added to ``nwbfile.events`` as ``pynwb.event.EventsTable`` objects), and
    the private GuPPy interface (derived traces, transient tables, and cross-correlations added to a
    ``guppy`` ProcessingModule). GuPPy outputs have no standalone public interface -- this
    converter is their entry point.

    The acquisition side follows the single-series ``TDTFiberPhotometryInterface`` design: one interface
    (and one ``FiberPhotometryTable`` row) per GuPPy store. The stores are discovered from the GuPPy
    ``storesList.csv`` -- each recording site contributes its ``signal`` and (optional) ``control`` store -- so
    the converter builds exactly the acquisition channels GuPPy processed.

    As with every fiber photometry interface, the ``FiberPhotometry`` metadata chain (devices,
    indicators, the ``FiberPhotometryTable`` and its rows, and each series'
    ``fiber_photometry_table_region``) is **supplied by the user**; the converter does not invent it.
    Each acquisition series reads its own block at ``metadata["FiberPhotometry"][metadata_key]``, where
    ``metadata_key`` is ``"<recording_site>_<role>"`` (e.g. ``"dms_signal"``). The converter reads the
    regions declared there to work out which table rows belong to which GuPPy recording site.

    That cross-interface knowledge makes the converter the author of the two GuPPy registries
    (``GuppyRecordingSitesTable``, ``GuppyEventsTable``): it is the only side that can link each recording
    site to its acquisition fiber rows and each event to its occurrence rows in the merged
    ``EventsTable``, so it builds both registries complete and the GuPPy interface reuses them.

    GuPPy and TDT share a single origin (recording start = ``session_start_time``): GuPPy emits
    timestamps in seconds since recording start, the same clock the raw TDT streams use. No
    cross-system re-alignment is therefore needed -- both interfaces write on the shared clock,
    rooted at ``nwbfile.session_start_time`` (taken from the TDT tank).
    """

    display_name = "TDT Fiber Photometry + GuPPy"
    keywords = TDTFiberPhotometryInterface.keywords + TDTEventsInterface.keywords + _GuppyInterface.keywords
    associated_suffixes = TDTFiberPhotometryInterface.associated_suffixes + _GuppyInterface.associated_suffixes
    info = "Converter that bundles raw TDT fiber photometry acquisition with GuPPy-derived processing outputs."

    @validate_call
    def __init__(
        self,
        tdt_folder_path: DirectoryPath,
        guppy_folder_path: DirectoryPath,
        *,
        verbose: bool = False,
    ):
        """Initialize the TDT + GuPPy converter.

        Parameters
        ----------
        tdt_folder_path : DirectoryPath
            Path to the TDT tank folder containing the raw acquisition files (Tbk, Tdx, tev,
            tin, tsq).
        guppy_folder_path : DirectoryPath
            Path to the GuPPy ``<session>_output_<N>`` folder containing ``storesList.csv``,
            the per-recording-site derived ``.hdf5`` files, and the ``GuPPyParamtersUsed.json``
            provenance file (discovered automatically by the GuPPy interface).
        verbose : bool, optional
            Whether to print status messages, default = False.

        Notes
        -----
        The raw TDT events stored are exactly the behavioral event stores GuPPy listed in
        ``storesList.csv`` -- i.e. only the epocs GuPPy actually processed -- each given the
        human-readable name from that file (e.g. the ``PrtR`` store becomes the ``port_entries``
        ``EventsTable``). Stores present in the tank but absent from ``storesList.csv`` (and the
        fiber signal/control stores) are excluded by ``get_metadata``.
        """
        guppy_interface = _GuppyInterface(folder_path=guppy_folder_path, verbose=verbose)
        # Store only the behavioral event stores GuPPy listed in storesList.csv, named with the
        # human-readable semantic names from that file (the selection and renaming happen in
        # get_metadata, since add_to_nwbfile only writes the epocs left in event_types).
        self._event_store_to_event_name = guppy_interface.event_store_to_event_name

        # One single-series TDT acquisition interface per GuPPy signal/control store. The GuPPy side
        # already discovered these stores from storesList.csv.
        data_interfaces: dict = {}
        self._series_specs: list[dict] = []
        self._tdt_interface_names: list[str] = []
        for recording_site in guppy_interface.recording_sites:
            store_ids = guppy_interface.recording_site_to_store_ids[recording_site]
            for role in _STORE_ROLES:
                if role not in store_ids:
                    continue
                store_id = store_ids[role]
                metadata_key = f"{recording_site}_{role}"
                interface_name = f"TDTFiberPhotometry_{recording_site}_{role}"
                data_interfaces[interface_name] = TDTFiberPhotometryInterface(
                    folder_path=tdt_folder_path,
                    stream_names=store_id,
                    metadata_key=metadata_key,
                    verbose=verbose,
                )
                self._series_specs.append(
                    dict(
                        interface_name=interface_name,
                        metadata_key=metadata_key,
                        recording_site=recording_site,
                        role=role,
                        store_id=store_id,
                        series_name=f"{recording_site}_{role}",
                    )
                )
                self._tdt_interface_names.append(interface_name)

        events_interface = TDTEventsInterface(folder_path=tdt_folder_path, verbose=verbose)
        data_interfaces["TDTEvents"] = events_interface
        data_interfaces["Guppy"] = guppy_interface
        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

    def get_metadata(self):
        """Merge sub-interface metadata into a single coherent fiber photometry conversion.

        Takes the TDT tank as the authoritative session start time, gives each acquisition series a
        distinct default name, and keeps only the behavioral event stores GuPPy listed.

        The ``FiberPhotometry`` chain itself (devices, indicators, table rows, per-series regions) is
        the user's to supply, exactly as for a bare ``TDTFiberPhotometryInterface``.
        """
        metadata = super().get_metadata()

        # The TDT tank is the authoritative session start time (shared clock origin for GuPPy).
        first_tdt_interface = self.data_interface_objects[self._tdt_interface_names[0]]
        tdt_metadata = first_tdt_interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = tdt_metadata["NWBFile"]["session_start_time"]

        # Every single-series scaffold defaults to the same "FiberPhotometryResponseSeries" name; give
        # each one the store it came from so the four series do not collide in nwbfile.acquisition.
        fiber_photometry_metadata = metadata["FiberPhotometry"]
        for series_spec in self._series_specs:
            fiber_photometry_metadata[series_spec["metadata_key"]]["name"] = series_spec["series_name"]

        # Select: the TDT interface seeds one event type per epoc in the tank, and its write is driven by
        # this dict rather than by the tank, so dropping the epocs GuPPy did not list is what keeps them
        # out of the NWB file.
        events_metadata_key = self.data_interface_objects["TDTEvents"].metadata_key
        seeded_event_types = metadata["Events"][events_metadata_key]["event_types"]
        missing_stores = [store for store in self._event_store_to_event_name if store not in seeded_event_types]
        assert not missing_stores, (
            f"GuPPy's storesList.csv lists behavioral event store(s) {missing_stores} that the TDT tank does "
            f"not provide as a non-empty epoc (available: {sorted(seeded_event_types)}). The GuPPy output and "
            f"the TDT tank do not describe the same session."
        )
        event_types = {store: seeded_event_types[store] for store in self._event_store_to_event_name}
        metadata["Events"][events_metadata_key]["event_types"] = event_types

        # Rename: each surviving store takes the human-readable name GuPPy recorded for it in
        # storesList.csv (e.g. the "PrtR" store becomes the "port_entries" event type).
        for store, event_name in self._event_store_to_event_name.items():
            event_types[store]["event_name"] = event_name
            event_types[store][
                "event_description"
            ] = f"Onset times of the '{event_name}' behavioral events (from TDT store '{store}')."

        # Route: send every surviving type into one merged EventsTable (shared table_metadata_key + a
        # declared EventTables entry naming it), so a single DynamicTableRegion from the GuppyEventsTable
        # can reference each type's occurrence rows.
        for entry in event_types.values():
            entry["table_metadata_key"] = _MERGED_EVENTS_TABLE_KEY
        metadata["Events"].setdefault("EventTables", {})[_MERGED_EVENTS_TABLE_KEY] = dict(
            table_name=_MERGED_EVENTS_TABLE_NAME,
            description="All behavioral events GuPPy aligned to, merged into one table with an event_type discriminator.",
        )
        return metadata

    def get_metadata_schema(self) -> dict:
        """Allow the ``FiberPhotometry`` block to carry the ``Guppy`` sub-schema alongside the base schemas."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["FiberPhotometry"]["additionalProperties"] = True
        return metadata_schema

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        conversion_options: dict | None = None,
    ) -> None:
        """Add raw TDT and GuPPy-derived data to the provided NWBFile.

        The GuPPy registries carry links that only this converter can compute (it owns the acquisition
        ``FiberPhotometryTable`` and forced the merged ``EventsTable``), so it authors them itself. Each
        step below therefore depends on the one above it, and the sequence is spelled out by name rather
        than looped over ``data_interface_objects``: the TDT acquisition interfaces build the shared
        ``FiberPhotometryTable``, ``TDTEvents`` writes the merged ``EventsTable``, the registries link
        into both, and the GuPPy interface reuses them for the products that reference their rows.
        """
        if metadata is None:
            metadata = self.get_metadata()
        conversion_options = conversion_options or {}

        for interface_name in self._tdt_interface_names:
            self.data_interface_objects[interface_name].add_to_nwbfile(
                nwbfile=nwbfile, metadata=metadata, **conversion_options.get(interface_name, {})
            )
        self.data_interface_objects["TDTEvents"].add_to_nwbfile(
            nwbfile=nwbfile, metadata=metadata, **conversion_options.get("TDTEvents", {})
        )
        self._build_guppy_registries(nwbfile=nwbfile, metadata=metadata)
        self.data_interface_objects["Guppy"].add_to_nwbfile(
            nwbfile=nwbfile, metadata=metadata, **conversion_options.get("Guppy", {})
        )

    def _build_guppy_registries(self, *, nwbfile: NWBFile, metadata: dict) -> None:
        """Author the two GuPPy registries, with their outward links, before the GuPPy interface runs.

        Only the converter can wire these links -- it built the acquisition ``FiberPhotometryTable`` and
        forced every event type into one merged ``EventsTable`` -- so it is the sole author of both
        registries, constructing them with ``target_tables`` and filling each row's ragged
        ``DynamicTableRegion`` here. Rows are built in the GuPPy interface's canonical recording-site /
        event order, which is what its products' registry references point at.
        """
        ndx_guppy = get_package(package_name="ndx_guppy", installation_instructions="pip install ndx-guppy")
        guppy_interface = self.data_interface_objects["Guppy"]
        module_metadata = metadata["FiberPhotometry"]["Guppy"][guppy_interface.metadata_key]["ProcessingModule"]
        processing_module = get_module(
            nwbfile=nwbfile, name=module_metadata["name"], description=module_metadata["description"]
        )

        # Recording sites: each row links to its signal + isosbestic-control acquisition rows.
        fiber_photometry_table = get_fiber_photometry_table(nwbfile=nwbfile)
        assert fiber_photometry_table is not None, (
            "No FiberPhotometryTable was written, so the GuPPy recording sites cannot be linked to the "
            "acquisition fibers. Supply the full FiberPhotometry metadata chain (Devices, "
            "FiberPhotometryIndicators, FiberPhotometryTable rows, and a "
            "'fiber_photometry_table_region' for each acquisition series) -- see the TDT + GuPPy "
            "conversion gallery example."
        )
        recording_site_to_rows = self._derive_recording_site_to_table_rows(metadata)
        recording_sites_table = ndx_guppy.GuppyRecordingSitesTable(
            name=_RECORDING_SITES_TABLE_NAME,
            description=_RECORDING_SITES_TABLE_DESCRIPTION,
            target_tables={"fiber_photometry_table_region": fiber_photometry_table},
        )
        for recording_site in guppy_interface.recording_sites:
            recording_sites_table.add_row(
                recording_site=recording_site,
                fiber_photometry_table_region=recording_site_to_rows[recording_site],
            )
        processing_module.add(recording_sites_table)

        # Events: each row links to its event type's occurrence rows in the merged EventsTable.
        merged_events_table = nwbfile.events[_MERGED_EVENTS_TABLE_NAME]
        event_type_column = list(merged_events_table["event_type"][:])
        events_table = ndx_guppy.GuppyEventsTable(
            name=_EVENTS_TABLE_NAME,
            description=_EVENTS_TABLE_DESCRIPTION,
            target_tables={"events": merged_events_table},
        )
        for event_name in guppy_interface.event_names:
            occurrence_rows = [index for index, event_type in enumerate(event_type_column) if event_type == event_name]
            events_table.add_row(event_name=event_name, events=occurrence_rows)
        processing_module.add(events_table)

    def _derive_recording_site_to_table_rows(self, metadata: dict) -> dict[str, list[int]]:
        """Map each GuPPy recording site to the acquisition ``FiberPhotometryTable`` row indices of its series.

        Each recording site owns the rows of its signal and (optional) isosbestic-control acquisition
        series, which the user declared as that series' ``fiber_photometry_table_region`` -- a list of
        row keys into ``FiberPhotometryTable['rows']``. Those keys are resolved to integers by their
        position in the rows dict, the same order the rows are written in, so the link never depends on
        fragile hand-written integers. Fails loudly if a series declares no region or names a row key
        the table does not define.
        """
        fiber_photometry_metadata = metadata["FiberPhotometry"]
        rows = fiber_photometry_metadata["FiberPhotometryTable"]["rows"]
        row_key_to_index = {row_key: index for index, row_key in enumerate(rows)}

        recording_site_to_rows: dict[str, list[int]] = {}
        for series_spec in self._series_specs:
            metadata_key = series_spec["metadata_key"]
            series_metadata = fiber_photometry_metadata[metadata_key]
            assert "fiber_photometry_table_region" in series_metadata, (
                f"Acquisition series '{metadata_key}' declares no 'fiber_photometry_table_region', so its GuPPy "
                f"recording site '{series_spec['recording_site']}' cannot be linked to the acquisition fibers. "
                f"Set metadata['FiberPhotometry']['{metadata_key}']['fiber_photometry_table_region']."
            )
            row_keys = series_metadata["fiber_photometry_table_region"]
            missing = [row_key for row_key in row_keys if row_key not in row_key_to_index]
            assert not missing, (
                f"Acquisition series '{metadata_key}' references FiberPhotometryTable row(s) {missing} not "
                f"present in metadata['FiberPhotometry']['FiberPhotometryTable']['rows'] "
                f"(available: {list(row_key_to_index)})."
            )
            recording_site_to_rows.setdefault(series_spec["recording_site"], []).extend(
                row_key_to_index[row_key] for row_key in row_keys
            )
        return {recording_site: sorted(rows) for recording_site, rows in recording_site_to_rows.items()}
