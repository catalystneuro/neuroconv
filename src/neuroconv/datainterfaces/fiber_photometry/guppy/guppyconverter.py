from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from .guppy_utils import (
    ACQUISITION_SUFFIXES,
    AcquisitionFormat,
    build_acquisition_interface,
    build_events_interfaces,
)
from .guppydatainterface import (
    _EVENTS_TABLE_DESCRIPTION,
    _EVENTS_TABLE_NAME,
    _RECORDING_SITES_TABLE_DESCRIPTION,
    _RECORDING_SITES_TABLE_NAME,
    _GuppyInterface,
)
from ....nwbconverter import ConverterPipe
from ....tools import get_package
from ....tools.fiber_photometry import get_fiber_photometry_table
from ....tools.nwb_helpers import get_module

# GuPPy stores are labeled by role in storesList.csv. A role is an excitation wavelength (signal is the
# indicator's excitation, control the isosbestic), which is the axis acquisition series are grouped on:
# one series per role, column-stacking that role's store from every recording site. See
# https://github.com/catalystneuro/ndx-fiber-photometry/issues/55.
_STORE_ROLES = ("signal", "control")
# The single merged EventsTable every behavioral event type is written into (one DynamicTableRegion
# from the GuppyEventsTable then references its occurrence rows).
_MERGED_EVENTS_TABLE_KEY = "guppy_behavioral_events"
_MERGED_EVENTS_TABLE_NAME = "BehavioralEvents"


class GuppyConverter(ConverterPipe):
    """Bundle a GuPPy session's raw acquisition, raw events, and GuPPy-derived processing outputs.

    Combines the three parts of a GuPPy session: the raw acquisition (added to ``nwbfile.acquisition``
    via the ``ndx-fiber-photometry`` extension), the raw discrete events (added to ``nwbfile.events`` as
    ``pynwb.event.EventsTable`` objects), and the private GuPPy interface (derived traces, transient
    tables, and cross-correlations added to a ``guppy`` ProcessingModule). GuPPy outputs have no
    standalone public interface -- this converter is their entry point.

    Everything the converter does with a GuPPy session is independent of how the session was recorded:
    ``storesList.csv`` names the acquisition stores as opaque ids, and the converter groups them, links
    them, and writes them without knowing what produced them. The acquisition format is confined to
    ``acquisition_format`` and the :mod:`~.guppy_utils` module it is passed to, which is where support
    for further GuPPy-readable formats is added.

    The stores are discovered from the GuPPy ``storesList.csv`` -- each recording site contributes its
    ``signal`` and (optional) ``control`` store -- so the converter builds exactly the acquisition
    channels GuPPy processed. Those stores are grouped by role rather than written one per series: each
    role is an excitation wavelength, and one acquisition interface per role column-stacks that role's
    store from every recording site into a single ``FiberPhotometryResponseSeries``. A two-site
    isosbestic session therefore yields two acquisition series, not four.

    As with every fiber photometry interface, the ``FiberPhotometry`` metadata chain (devices,
    indicators, the ``FiberPhotometryTable`` and its rows, and each series'
    ``fiber_photometry_table_region``) is **supplied by the user**; the converter does not invent it.
    Each acquisition series reads its own block at ``metadata["FiberPhotometry"][metadata_key]``, where
    ``metadata_key`` is the role (``"signal"`` or ``"control"``). The ``FiberPhotometryTable`` still
    carries one row per store -- the grouping changes, not the rows -- and each series' region lists its
    stacked stores' rows in column order, which is how the converter recovers the row belonging to each
    GuPPy recording site.

    That cross-interface knowledge makes the converter the author of the two GuPPy registries
    (``GuppyRecordingSitesTable``, ``GuppyEventsTable``): it is the only side that can link each recording
    site to its acquisition fiber rows and each event to its occurrence rows in the merged
    ``EventsTable``, so it builds both registries complete and the GuPPy interface reuses them.

    GuPPy and the acquisition share a single origin (recording start = ``session_start_time``): GuPPy
    emits timestamps in seconds since recording start, the same clock the raw streams use. No
    cross-system re-alignment is therefore needed -- both interfaces write on the shared clock,
    rooted at ``nwbfile.session_start_time``.
    """

    display_name = "GuPPy Fiber Photometry"
    keywords = _GuppyInterface.keywords + ("events",)
    associated_suffixes = tuple(dict.fromkeys(_GuppyInterface.associated_suffixes + ACQUISITION_SUFFIXES))
    info = "Converter that bundles a GuPPy session's raw acquisition with its GuPPy-derived processing outputs."

    @validate_call
    def __init__(
        self,
        fiber_photometry_folder_path: DirectoryPath,
        events_folder_path: DirectoryPath,
        guppy_folder_path: DirectoryPath,
        *,
        acquisition_format: AcquisitionFormat,
        verbose: bool = False,
    ):
        """Initialize the GuPPy converter.

        Parameters
        ----------
        fiber_photometry_folder_path : DirectoryPath
            Path to the folder holding the raw acquisition traces -- for TDT, the tank folder
            containing the Tbk, Tdx, tev, tin and tsq files; for CSV, the folder holding one
            ``<store>.csv`` per channel; for Doric, the folder holding the single ``.doric`` or
            DoricStudio ``.csv`` export. For NPM this must be the GuPPy session folder itself, since
            GuPPy's ``file<N>`` store names index that folder's CSVs in sorted order.
        events_folder_path : DirectoryPath
            Path to the folder holding the raw discrete events. GuPPy writes a session's traces and
            events into one folder, so for TDT this is the same tank folder as
            ``fiber_photometry_folder_path``; the two are named separately because other acquisition
            formats read them through different interfaces.
        guppy_folder_path : DirectoryPath
            Path to the GuPPy ``<session>_output_<N>`` folder containing ``storesList.csv``,
            the per-recording-site derived ``.hdf5`` files, and the ``GuPPyParamtersUsed.json``
            provenance file (discovered automatically by the GuPPy interface).
        acquisition_format : {"tdt", "csv", "doric", "npm"}
            The format the session was recorded in, selecting which interfaces read the two raw
            folders. ``"doric"`` covers all three Doric layouts -- modern and legacy ``.doric`` HDF5 and
            DoricStudio ``.csv`` exports -- resolved from the one acquisition file in the folder, and
            ``"npm"`` covers both the state-column and header-less Neurophotometrics layouts.
        verbose : bool, optional
            Whether to print status messages, default = False.

        Notes
        -----
        The raw events stored are exactly the behavioral event stores GuPPy listed in
        ``storesList.csv`` -- i.e. only the epocs GuPPy actually processed -- each given the
        human-readable name from that file (e.g. the ``PrtR`` store becomes the ``port_entries``
        ``EventsTable``). Stores present in the source but absent from ``storesList.csv`` (and the
        fiber signal/control stores) are excluded by ``get_metadata``.
        """
        self.acquisition_format = acquisition_format
        guppy_interface = _GuppyInterface(folder_path=guppy_folder_path, verbose=verbose)
        # Store only the behavioral event stores GuPPy listed in storesList.csv, named with the
        # human-readable semantic names from that file (the selection and renaming happen in
        # get_metadata, since add_to_nwbfile only writes the epocs left in event_types).
        self._event_store_to_event_name = guppy_interface.event_store_to_event_name

        # The GuPPy interface is registered FIRST because get_metadata merges the sub-interfaces in
        # registration order, last one wins: GuPPy reports a session_start_time of its own (derived from
        # timeCorrection), so registering it ahead of the acquisition lets the acquisition's own value
        # take precedence when it has one, and lets GuPPy's stand as the fallback when it does not.
        data_interfaces: dict = {"Guppy": guppy_interface}

        # One acquisition interface per role (excitation wavelength), column-stacking that role's store
        # from every recording site that has one. The GuPPy side already discovered these stores from
        # storesList.csv. `recording_sites` runs parallel to the stacked stores, so the site owning
        # column i -- and therefore the region row at index i -- is recoverable by position.
        self._series_specs: list[dict] = []
        self._acquisition_interface_names: list[str] = []
        for role in _STORE_ROLES:
            recording_sites = [
                recording_site
                for recording_site in guppy_interface.recording_sites
                if role in guppy_interface.recording_site_to_store_ids[recording_site]
            ]
            if not recording_sites:
                continue  # a session without isosbestic controls contributes no control series
            store_ids = [
                guppy_interface.recording_site_to_store_ids[recording_site][role] for recording_site in recording_sites
            ]
            interface_name = f"FiberPhotometry_{role}"
            data_interfaces[interface_name] = build_acquisition_interface(
                acquisition_format=acquisition_format,
                folder_path=fiber_photometry_folder_path,
                guppy_folder_path=guppy_folder_path,
                store_ids=store_ids,
                metadata_key=role,
                verbose=verbose,
            )
            self._series_specs.append(
                dict(
                    metadata_key=role,
                    recording_sites=recording_sites,
                    series_name=f"FiberPhotometryResponseSeries{role.capitalize()}",
                )
            )
            self._acquisition_interface_names.append(interface_name)

        # How many events interfaces a session needs is itself format-dependent: one TDT interface reads
        # every epoc in a tank, while GuPPy's CSV format stores each event in its own file and needs one
        # interface per store. The rest of the converter therefore works over a list of them. A session
        # whose storesList holds only signal/control stores gets none at all -- an events interface asked
        # to read nothing is an error in some formats, not an empty result.
        events_interfaces, source_id_to_store_id = {}, {}
        if self._event_store_to_event_name:
            events_interfaces, source_id_to_store_id = build_events_interfaces(
                acquisition_format=acquisition_format,
                folder_path=events_folder_path,
                guppy_folder_path=guppy_folder_path,
                event_store_ids=list(self._event_store_to_event_name),
                verbose=verbose,
            )
        data_interfaces.update(events_interfaces)
        self._events_interface_names: list[str] = list(events_interfaces)
        # Most formats key their seeded event types by the same id storesList.csv uses, but not all can:
        # see build_events_interfaces. This maps the ones that differ back onto the storesList id that
        # get_metadata joins on. Empty means "they already agree".
        self._event_source_id_to_store_id: dict[str, str] = source_id_to_store_id
        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

    def get_metadata(self):
        """Merge sub-interface metadata into a single coherent fiber photometry conversion.

        Gives each acquisition series a distinct default name and keeps only the behavioral event
        stores GuPPy listed. The ``session_start_time`` needs no handling here: the base merge takes it
        from whichever sub-interface reports one last, and the interfaces are registered so that is the
        acquisition when it embeds a recording start, and GuPPy otherwise.

        The ``FiberPhotometry`` chain itself (devices, indicators, table rows, per-series regions) is
        the user's to supply, exactly as for a bare acquisition interface.
        """
        metadata = super().get_metadata()

        # Every single-series scaffold defaults to the same "FiberPhotometryResponseSeries" name; suffix
        # each one with its role so the two series do not collide in nwbfile.acquisition.
        fiber_photometry_metadata = metadata["FiberPhotometry"]
        for series_spec in self._series_specs:
            fiber_photometry_metadata[series_spec["metadata_key"]]["name"] = series_spec["series_name"]

        # Select: each events interface seeds one event type per store it found, and its write is driven
        # by that dict rather than by the source, so dropping the stores GuPPy did not list is what keeps
        # them out of the NWB file. A format may split its stores over several interfaces, so the stores
        # GuPPy listed are only guaranteed to be covered by the interfaces taken together.
        covered_stores: set[str] = set()
        for events_metadata_key, seeded_event_types in self._iter_event_type_blocks(metadata):
            kept = {
                source_id: entry
                for source_id, entry in seeded_event_types.items()
                if self._store_id_for(source_id) in self._event_store_to_event_name
            }
            metadata["Events"][events_metadata_key]["event_types"] = kept
            covered_stores.update(self._store_id_for(source_id) for source_id in kept)
        missing_stores = [store for store in self._event_store_to_event_name if store not in covered_stores]
        assert not missing_stores, (
            f"GuPPy's storesList.csv lists behavioral event store(s) {missing_stores} that the raw events "
            f"source does not provide with any occurrences (available: {sorted(covered_stores)}). The "
            f"GuPPy output and the raw events source do not describe the same session."
        )

        # Rename: each surviving store takes the human-readable name GuPPy recorded for it in
        # storesList.csv (e.g. the "PrtR" store becomes the "port_entries" event type).
        for _, event_types in self._iter_event_type_blocks(metadata):
            for source_id, entry in event_types.items():
                store = self._store_id_for(source_id)
                event_name = self._event_store_to_event_name[store]
                entry["event_name"] = event_name
                entry["event_description"] = (
                    f"Onset times of the '{event_name}' behavioral events (from acquisition store '{store}')."
                )

        # Route: send every surviving type into one merged EventsTable (shared table_metadata_key + a
        # declared EventTables entry naming it), so a single DynamicTableRegion from the GuppyEventsTable
        # can reference each type's occurrence rows. The EventTables entry is required, not decorative:
        # it is what makes the first interface write a merged table carrying the event_type discriminator
        # column, without which a second interface contributing to the same table fails.
        for _, event_types in self._iter_event_type_blocks(metadata):
            for entry in event_types.values():
                entry["table_metadata_key"] = _MERGED_EVENTS_TABLE_KEY
        metadata["Events"].setdefault("EventTables", {})[_MERGED_EVENTS_TABLE_KEY] = dict(
            table_name=_MERGED_EVENTS_TABLE_NAME,
            description="All behavioral events GuPPy aligned to, merged into one table with an event_type discriminator.",
        )
        return metadata

    def _store_id_for(self, event_type_source_id: str) -> str:
        """Return the ``storesList.csv`` id an interface's seeded event type corresponds to.

        Most events interfaces key their types by the same id GuPPy recorded, so this is the identity.
        The exception is an interface that cannot be told what to call a type -- see the ``event0`` case
        in :func:`~.guppy_utils.build_events_interfaces` -- for which the seam supplies the translation.
        """
        return self._event_source_id_to_store_id.get(event_type_source_id, event_type_source_id)

    def _iter_event_type_blocks(self, metadata: dict):
        """Yield ``(metadata_key, event_types)`` for each events interface, in registration order.

        Shared by the select/rename/route blocks above so each stays a separate, single-purpose pass
        over however many events interfaces the acquisition format needed.
        """
        for interface_name in self._events_interface_names:
            events_metadata_key = self.data_interface_objects[interface_name].metadata_key
            yield events_metadata_key, metadata["Events"][events_metadata_key]["event_types"]

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
        """Add the raw acquisition and GuPPy-derived data to the provided NWBFile.

        The GuPPy registries carry links that only this converter can compute (it owns the acquisition
        ``FiberPhotometryTable`` and forced the merged ``EventsTable``), so it authors them itself. Each
        step below therefore depends on the one above it, and the sequence is spelled out by name rather
        than looped over ``data_interface_objects``: the acquisition interfaces build the shared
        ``FiberPhotometryTable``, the events interfaces write the merged ``EventsTable``, the registries link
        into both, and the GuPPy interface reuses them for the products that reference their rows.

        Note this is deliberately *not* ``data_interface_objects`` order: ``Guppy`` is registered first,
        for metadata precedence, but written last.
        """
        if metadata is None:
            metadata = self.get_metadata()
        conversion_options = conversion_options or {}

        for interface_name in self._acquisition_interface_names:
            self.data_interface_objects[interface_name].add_to_nwbfile(
                nwbfile=nwbfile, metadata=metadata, **conversion_options.get(interface_name, {})
            )
        for interface_name in self._events_interface_names:
            self.data_interface_objects[interface_name].add_to_nwbfile(
                nwbfile=nwbfile, metadata=metadata, **conversion_options.get(interface_name, {})
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
            "'fiber_photometry_table_region' for each acquisition series)."
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

        # Events: each row links to its event type's occurrence rows in the merged EventsTable. A session
        # whose storesList holds no event store writes no such table, and there is nothing for the
        # converter to link -- the GuPPy interface then builds the link-free registry itself, exactly as
        # it does when run standalone.
        if not self._events_interface_names:
            return
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
        """Map each GuPPy recording site to the acquisition ``FiberPhotometryTable`` row indices of its stores.

        Each series stacks one store per recording site, and the user declares the matching
        ``fiber_photometry_table_region`` -- a list of row keys into ``FiberPhotometryTable['rows']``,
        one per stacked column. That column order is the series' own contract (column *i* of the data is
        recorded on region row *i*), and the converter chose it, so zipping the region against the
        series' ``recording_sites`` recovers each site's row. Row keys are resolved to integers by their
        position in the rows dict, the same order the rows are written in, so the link never depends on
        fragile hand-written integers.

        Fails loudly if a series declares no region, declares a region of the wrong length, or names a
        row key the table does not define.
        """
        fiber_photometry_metadata = metadata["FiberPhotometry"]
        rows = fiber_photometry_metadata["FiberPhotometryTable"]["rows"]
        row_key_to_index = {row_key: index for index, row_key in enumerate(rows)}

        recording_site_to_rows: dict[str, list[int]] = {}
        for series_spec in self._series_specs:
            metadata_key = series_spec["metadata_key"]
            recording_sites = series_spec["recording_sites"]
            series_metadata = fiber_photometry_metadata[metadata_key]
            assert "fiber_photometry_table_region" in series_metadata, (
                f"Acquisition series '{metadata_key}' declares no 'fiber_photometry_table_region', so the GuPPy "
                f"recording sites {recording_sites} cannot be linked to the acquisition fibers. "
                f"Set metadata['FiberPhotometry']['{metadata_key}']['fiber_photometry_table_region']."
            )
            row_keys = series_metadata["fiber_photometry_table_region"]
            assert len(row_keys) == len(recording_sites), (
                f"Acquisition series '{metadata_key}' stacks {len(recording_sites)} store(s) (one per recording "
                f"site {recording_sites}) but declares {len(row_keys)} FiberPhotometryTable row(s) {list(row_keys)}. "
                f"The region must name one row per stacked column, in the same order."
            )
            missing = [row_key for row_key in row_keys if row_key not in row_key_to_index]
            assert not missing, (
                f"Acquisition series '{metadata_key}' references FiberPhotometryTable row(s) {missing} not "
                f"present in metadata['FiberPhotometry']['FiberPhotometryTable']['rows'] "
                f"(available: {list(row_key_to_index)})."
            )
            for recording_site, row_key in zip(recording_sites, row_keys):
                recording_site_to_rows.setdefault(recording_site, []).append(row_key_to_index[row_key])
        return {recording_site: sorted(rows) for recording_site, rows in recording_site_to_rows.items()}
