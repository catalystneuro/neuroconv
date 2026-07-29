from typing import Literal

from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from .guppydatainterface import _GuppyInterface
from ..tdt.tdtfiberphotometrydatainterface import TDTFiberPhotometryInterface
from ...events.tdt_events.tdteventsdatainterface import TDTEventsInterface
from ....nwbconverter import ConverterPipe
from ....tools.fiber_photometry import get_fiber_photometry_table

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
    ``fiber_photometry`` ProcessingModule). GuPPy outputs have no standalone public interface -- this
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
        # Insertion order matters: the TDT interfaces (which build the shared FiberPhotometryTable) run
        # before GuPPy, whose derived traces link back into that table.
        data_interfaces["TDTEvents"] = events_interface
        data_interfaces["Guppy"] = guppy_interface
        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

    def get_metadata(self):
        """Merge sub-interface metadata into a single coherent fiber photometry conversion.

        Takes the TDT tank as the authoritative session start time, gives each acquisition series a
        distinct default name, renames the GuPPy ProcessingModule to avoid a name collision with the
        TDT ``fiber_photometry`` lab metadata, and keeps only the behavioral event stores GuPPy listed.

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

        # The TDT side adds a FiberPhotometry lab_meta_data object named "fiber_photometry"; rename the
        # GuPPy ProcessingModule to avoid colliding with that name during NWB write.
        guppy_metadata_key = self.data_interface_objects["Guppy"].metadata_key
        metadata["FiberPhotometry"]["Guppy"][guppy_metadata_key]["ProcessingModule"]["name"] = "guppy"

        # Keep only the behavioral event stores GuPPy listed in storesList.csv and rename each to the
        # human-readable name GuPPy recorded there (e.g. the "PrtR" store becomes the "port_entries"
        # event type). Route every surviving type into a single merged EventsTable (shared
        # table_metadata_key + a declared EventTables entry that names it), so one DynamicTableRegion
        # from the GuppyEventsTable can reference each type's occurrence rows.
        events_metadata_key = self.data_interface_objects["TDTEvents"].metadata_key
        event_types = metadata["Events"][events_metadata_key]["event_types"]
        renamed_event_types = {}
        for epoc_name, event_name in self._event_store_to_event_name.items():
            entry = event_types[epoc_name]
            entry["event_name"] = event_name
            entry["event_description"] = (
                f"Onset times of the '{event_name}' behavioral events (from TDT store '{epoc_name}')."
            )
            entry["table_metadata_key"] = _MERGED_EVENTS_TABLE_KEY
            renamed_event_types[epoc_name] = entry
        metadata["Events"][events_metadata_key]["event_types"] = renamed_event_types
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

    def get_conversion_options_schema(self) -> dict:
        """Expose a top-level ``stub_test`` option alongside the per-interface schemas."""
        schema = super().get_conversion_options_schema()
        schema["properties"]["stub_test"] = {
            "type": "boolean",
            "default": False,
            "description": "If True, only a short stub of each trace is written.",
        }
        return schema

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        conversion_options: dict | None = None,
        stub_test: bool = False,
    ) -> None:
        """Add raw TDT and GuPPy-derived data to the provided NWBFile.

        Runs the sub-interfaces in insertion order (the TDT acquisition interfaces build the shared
        ``FiberPhotometryTable``; ``TDTEvents`` writes one merged ``EventsTable``; the GuPPy interface
        writes its products plus two *slim* registry tables), then populates the registries' outward
        links -- the links only the converter can compute, since it is the side that owns the
        acquisition table and forced the merged events table.
        """
        if metadata is None:
            metadata = self.get_metadata()
        merged_conversion_options = self._build_conversion_options(
            metadata=metadata, conversion_options=conversion_options, stub_test=stub_test
        )
        for interface_name, data_interface in self.data_interface_objects.items():
            data_interface.add_to_nwbfile(
                nwbfile=nwbfile, metadata=metadata, **merged_conversion_options.get(interface_name, {})
            )
        self._link_guppy_registries(nwbfile=nwbfile, metadata=metadata)

    def _link_guppy_registries(self, *, nwbfile: NWBFile, metadata: dict) -> None:
        """Populate the two GuPPy registries' optional outward links, after the GuPPy interface runs.

        The interface writes both registries slim (identities only) because it does not know the
        acquisition row layout or how the raw events were tabled. Both link columns are declared
        optional and ragged by ``ndx-guppy``, so the converter fills them in here with a post-hoc
        ``add_column``. Registry row order is the interface's canonical recording-site / event order,
        which is what the products' registry references already point at.
        """
        guppy_interface = self.data_interface_objects["Guppy"]
        guppy_metadata = metadata["FiberPhotometry"]["Guppy"][guppy_interface.metadata_key]
        processing_module = nwbfile.processing[guppy_metadata["ProcessingModule"]["name"]]

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
        self._add_ragged_region_column(
            table=processing_module["recording_sites"],
            name="fiber_photometry_table_region",
            description="The acquisition fiber rows (signal + isosbestic control) of this recording site.",
            row_references=[
                recording_site_to_rows[recording_site] for recording_site in guppy_interface.recording_sites
            ],
            target_table=fiber_photometry_table,
        )

        # Events: each row links to its event type's occurrence rows in the merged EventsTable.
        merged_events_table = nwbfile.events[_MERGED_EVENTS_TABLE_NAME]
        event_type_column = list(merged_events_table["event_type"][:])
        self._add_ragged_region_column(
            table=processing_module["events"],
            name="events",
            description="The occurrence rows of this event type in the merged EventsTable.",
            row_references=[
                [index for index, event_type in enumerate(event_type_column) if event_type == event_name]
                for event_name in guppy_interface.event_names
            ],
            target_table=merged_events_table,
        )

    @staticmethod
    def _add_ragged_region_column(
        *, table, name: str, description: str, row_references: list[list[int]], target_table
    ) -> None:
        """Add a ragged ``DynamicTableRegion`` column of per-row references onto an existing table.

        ``row_references`` holds one list of target-row indices per existing row of ``table``; hdmf
        flattens it and builds the VectorIndex from ``index=True``. The target is attached afterwards
        rather than passed as ``table=``: both columns are predefined by ``ndx-guppy`` as
        ``table=True``, and hdmf compares that spec against the argument by identity, so handing it the
        table object itself trips a spurious "does not match the entered table argument" warning.
        """
        assert len(row_references) == len(table), (
            f"Cannot add '{name}': got {len(row_references)} reference lists for a table of " f"{len(table)} rows."
        )
        table.add_column(name=name, description=description, data=row_references, index=True, table=True)
        table[name].target.table = target_table

    def run_conversion(
        self,
        nwbfile_path: str | None = None,
        nwbfile: NWBFile | None = None,
        metadata: dict | None = None,
        overwrite: bool = False,
        backend: Literal["hdf5", "zarr"] | None = None,
        backend_configuration=None,
        conversion_options: dict | None = None,
        append_on_disk_nwbfile: bool = False,
        stub_test: bool = False,
    ) -> None:
        """Run the NWB conversion for both TDT acquisition and GuPPy processing outputs."""
        if metadata is None:
            metadata = self.get_metadata()
        merged_conversion_options = self._build_conversion_options(
            metadata=metadata, conversion_options=conversion_options, stub_test=stub_test
        )
        super().run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            backend=backend,
            backend_configuration=backend_configuration,
            conversion_options=merged_conversion_options,
            append_on_disk_nwbfile=append_on_disk_nwbfile,
        )

    def _build_conversion_options(self, *, metadata: dict, conversion_options: dict | None, stub_test: bool) -> dict:
        """Fan ``stub_test`` out to every sub-interface (no linkage data is injected into GuPPy)."""
        conversion_options = dict(conversion_options) if conversion_options else {}
        merged_conversion_options: dict = {}
        for interface_name in self._tdt_interface_names:
            tdt_options = {"stub_test": stub_test}
            tdt_options.update(conversion_options.pop(interface_name, {}))
            merged_conversion_options[interface_name] = tdt_options
        merged_conversion_options["TDTEvents"] = conversion_options.pop("TDTEvents", {})
        guppy_options: dict = {"stub_test": stub_test}
        guppy_options.update(conversion_options.pop("Guppy", {}))
        merged_conversion_options["Guppy"] = guppy_options
        merged_conversion_options.update(conversion_options)
        return merged_conversion_options

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
