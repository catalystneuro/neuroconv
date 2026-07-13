from copy import deepcopy
from typing import Literal

from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from .guppydatainterface import GuppyInterface
from ..tdt.tdtfiberphotometrydatainterface import TDTFiberPhotometryInterface
from ...events.tdt_events.tdteventsdatainterface import TDTEventsInterface
from ....nwbconverter import ConverterPipe

# GuPPy stores are labeled by role in storesList.csv; each becomes one single-series acquisition
# interface (and one FiberPhotometryTable row). The order here fixes the per-region row order.
_STORE_ROLES = ("signal", "control")


class TDTFiberPhotometryGuppyConverter(ConverterPipe):
    """Bundle raw TDT fiber photometry acquisition, raw events, and GuPPy-derived processing outputs.

    Combines the three parts of a GuPPy session: the raw TDT acquisition (added to
    ``nwbfile.acquisition`` via the ``ndx-fiber-photometry`` extension), :class:`TDTEventsInterface`
    (raw discrete events/epocs added to ``nwbfile.events`` as ``pynwb.event.EventsTable`` objects), and
    :class:`GuppyInterface` (derived traces, transient tables, and cross-correlations added to a
    ``fiber_photometry`` ProcessingModule).

    The acquisition side follows the single-series ``TDTFiberPhotometryInterface`` design: one interface
    (and one ``FiberPhotometryTable`` row) per GuPPy store. The stores are discovered from the GuPPy
    ``storesList.csv`` -- each region contributes its ``signal`` and (optional) ``control`` store -- so
    the converter builds exactly the acquisition channels GuPPy processed. All the single-series
    interfaces share one ``FiberPhotometryTable``, which the first one to run assembles from the
    converter-merged metadata.

    GuPPy and TDT share a single origin (recording start = ``session_start_time``): GuPPy emits
    timestamps in seconds since recording start, the same clock the raw TDT streams use. No
    cross-system re-alignment is therefore needed -- both interfaces write on the shared clock,
    rooted at ``nwbfile.session_start_time`` (taken from the TDT tank).
    """

    display_name = "TDT Fiber Photometry + GuPPy"
    keywords = TDTFiberPhotometryInterface.keywords + TDTEventsInterface.keywords + GuppyInterface.keywords
    associated_suffixes = TDTFiberPhotometryInterface.associated_suffixes + GuppyInterface.associated_suffixes
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
            the per-region derived ``.hdf5`` files, and the ``GuPPyParamtersUsed.json``
            provenance file (discovered automatically by :class:`GuppyInterface`).
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
        guppy_interface = GuppyInterface(folder_path=guppy_folder_path, verbose=verbose)
        # Store only the behavioral event stores GuPPy listed in storesList.csv, named with the
        # human-readable semantic names from that file (the selection and renaming happen in
        # get_metadata, since add_to_nwbfile only writes the epocs left in event_types).
        self._event_store_to_event_name = guppy_interface.event_store_to_event_name

        # One single-series TDT acquisition interface (and one FiberPhotometryTable row) per GuPPy
        # signal/control store. The GuPPy side already discovered these stores from storesList.csv.
        data_interfaces: dict = {}
        self._series_specs: list[dict] = []
        self._region_to_row_keys: dict[str, list[str]] = {}
        self._tdt_interface_names: list[str] = []
        for region in guppy_interface.regions:
            store_names = guppy_interface.region_to_store_names[region]
            for role in _STORE_ROLES:
                if role not in store_names:
                    continue
                store_name = store_names[role]
                metadata_key = f"{region}_{role}"
                interface_name = f"TDTFiberPhotometry_{region}_{role}"
                data_interfaces[interface_name] = TDTFiberPhotometryInterface(
                    folder_path=tdt_folder_path,
                    stream_names=store_name,
                    metadata_key=metadata_key,
                    verbose=verbose,
                )
                # One table row per series; the row key doubles as the response-series metadata key.
                self._series_specs.append(
                    dict(
                        interface_name=interface_name,
                        metadata_key=metadata_key,
                        region=region,
                        role=role,
                        store_name=store_name,
                        row_key=metadata_key,
                        series_name=f"{region}_{role}",
                    )
                )
                self._region_to_row_keys.setdefault(region, []).append(metadata_key)
                self._tdt_interface_names.append(interface_name)

        events_interface = TDTEventsInterface(folder_path=tdt_folder_path, verbose=verbose)
        # Insertion order matters: the TDT interfaces (which build the shared FiberPhotometryTable) run
        # before GuPPy, whose derived traces link back into that table.
        data_interfaces["TDTEvents"] = events_interface
        data_interfaces["Guppy"] = guppy_interface
        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

    def get_metadata(self):
        """Merge sub-interface metadata into a single coherent fiber photometry conversion.

        The single-series TDT scaffolds all default to one shared ``row0``; this rebuilds the
        ``FiberPhotometryTable`` with one row per acquisition series and points each series at its own
        row. It also takes the TDT tank as the authoritative session start time, renames the GuPPy
        ProcessingModule to avoid a name collision with the TDT ``fiber_photometry`` lab metadata, and
        keeps only the behavioral event stores GuPPy listed.
        """
        metadata = super().get_metadata()

        # The TDT tank is the authoritative session start time (shared clock origin for GuPPy).
        first_tdt_interface = self.data_interface_objects[self._tdt_interface_names[0]]
        tdt_metadata = first_tdt_interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = tdt_metadata["NWBFile"]["session_start_time"]

        # Give each acquisition series its own FiberPhotometryTable row (the merged scaffolds collapse
        # onto a single shared "row0") and wire each response series to that row.
        fiber_photometry_metadata = metadata["FiberPhotometry"]
        table_metadata = fiber_photometry_metadata["FiberPhotometryTable"]
        template_row = deepcopy(next(iter(table_metadata["rows"].values())))
        rows = {}
        for series_spec in self._series_specs:
            rows[series_spec["row_key"]] = deepcopy(template_row)
            series_metadata = fiber_photometry_metadata[series_spec["metadata_key"]]
            series_metadata["name"] = series_spec["series_name"]
            series_metadata["fiber_photometry_table_region"] = [series_spec["row_key"]]
        table_metadata["rows"] = rows

        # The TDT side adds a FiberPhotometry lab_meta_data object named "fiber_photometry"; rename the
        # GuPPy ProcessingModule to avoid colliding with that name during NWB write.
        metadata["Ophys"]["Guppy"]["ProcessingModule"]["name"] = "guppy"

        # Keep only the behavioral event stores GuPPy listed in storesList.csv and rename each to the
        # human-readable name GuPPy recorded there (e.g. the "PrtR" store becomes the "port_entries"
        # event type). The events interface writes one EventsTable per surviving event type, named by
        # the CamelCased event_name (-> "PortEntries"), so dropping the other epocs here excludes the
        # unprocessed tank stores, and setting event_name fixes the table name GuppyInterface links to.
        metadata_key = self.data_interface_objects["TDTEvents"].metadata_key
        event_types = metadata["Events"][metadata_key]["event_types"]
        renamed_event_types = {}
        for epoc_name, event_name in self._event_store_to_event_name.items():
            entry = event_types[epoc_name]
            entry["event_name"] = event_name
            entry["event_description"] = (
                f"Onset times of the '{event_name}' behavioral events (from TDT store '{epoc_name}')."
            )
            renamed_event_types[epoc_name] = entry
        metadata["Events"][metadata_key]["event_types"] = renamed_event_types
        return metadata

    def get_metadata_schema(self) -> dict:
        """Allow the ``Ophys`` block to carry the ``Guppy`` sub-schema alongside the base schemas."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ophys"]["additionalProperties"] = True
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

        The TDT interfaces run first (the first builds the ``FiberPhotometryTable``), then the GuPPy
        step runs with auto-derived ``fiber_photometry_table_region_indices`` so its derived traces are
        written as ``FiberPhotometryResponseSeries`` linked back into that table. Ordering is guaranteed
        by the insertion order of ``data_interface_objects`` (TDT before GuPPy).
        """
        if metadata is None:
            metadata = self.get_metadata()
        merged_conversion_options = self._build_conversion_options(
            metadata=metadata, conversion_options=conversion_options, stub_test=stub_test
        )
        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            conversion_options=merged_conversion_options,
        )

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
        """Fan ``stub_test`` out to every sub-interface and inject GuPPy's table-region indices."""
        conversion_options = dict(conversion_options) if conversion_options else {}
        merged_conversion_options: dict = {}
        for interface_name in self._tdt_interface_names:
            tdt_options = {"stub_test": stub_test}
            tdt_options.update(conversion_options.pop(interface_name, {}))
            merged_conversion_options[interface_name] = tdt_options
        merged_conversion_options["TDTEvents"] = conversion_options.pop("TDTEvents", {})
        guppy_options: dict = {
            "stub_test": stub_test,
            "fiber_photometry_table_region_indices": self._derive_region_to_table_indices(metadata),
        }
        guppy_options.update(conversion_options.pop("Guppy", {}))
        merged_conversion_options["Guppy"] = guppy_options
        merged_conversion_options.update(conversion_options)
        return merged_conversion_options

    def _derive_region_to_table_indices(self, metadata: dict) -> dict[str, list[int]]:
        """Map each GuPPy region to the acquisition ``FiberPhotometryTable`` row indices of its series.

        Each region owns the rows of its signal and (optional) isosbestic-control acquisition series.
        The integer index is the row's position in the (converter-built) ``FiberPhotometryTable.rows``
        dict -- the same order the rows are added in -- so the region link never depends on fragile
        hand-written integers. Fails loudly if a region's row is missing from the table.
        """
        rows = metadata["FiberPhotometry"]["FiberPhotometryTable"]["rows"]
        row_key_to_index = {row_key: index for index, row_key in enumerate(rows)}
        region_to_indices: dict[str, list[int]] = {}
        for region, row_keys in self._region_to_row_keys.items():
            missing = [row_key for row_key in row_keys if row_key not in row_key_to_index]
            assert not missing, (
                f"GuPPy region '{region}' references FiberPhotometryTable row(s) {missing} not present "
                f"in metadata['FiberPhotometry']['FiberPhotometryTable']['rows'] "
                f"(available: {list(row_key_to_index)}). Check that the converter's table rows were not "
                f"overwritten by user metadata."
            )
            region_to_indices[region] = sorted(row_key_to_index[row_key] for row_key in row_keys)
        return region_to_indices
