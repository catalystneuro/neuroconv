from typing import Literal

from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from .guppydatainterface import GuppyInterface
from ..tdt_fp.tdtfiberphotometrydatainterface import TDTFiberPhotometryInterface
from ...events.tdt_events.tdteventsdatainterface import TDTEventsInterface
from ....nwbconverter import ConverterPipe


class TDTFiberPhotometryGuppyConverter(ConverterPipe):
    """Bundle raw TDT fiber photometry acquisition, raw events, and GuPPy-derived processing outputs.

    Combines the three parts of a GuPPy session: :class:`TDTFiberPhotometryInterface` (raw acquisition
    traces added to ``nwbfile.acquisition`` via the ``ndx-fiber-photometry`` extension),
    :class:`TDTEventsInterface` (raw discrete events/epocs added to ``nwbfile.acquisition`` via the
    ``ndx-events`` extension), and :class:`GuppyInterface` (derived traces, transient tables, and
    cross-correlations added to a ``fiber_photometry`` ProcessingModule).

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
        human-readable name from that file (e.g. the ``PrtN`` store becomes the ``port_entries``
        Events object). Stores present in the tank but absent from ``storesList.csv`` (and the
        fiber signal/control stores) are excluded by ``get_metadata``.
        """
        tdt_interface = TDTFiberPhotometryInterface(folder_path=tdt_folder_path, verbose=verbose)
        guppy_interface = GuppyInterface(
            folder_path=guppy_folder_path,
            verbose=verbose,
        )
        # Store only the behavioral event stores GuPPy listed in storesList.csv, named with the
        # human-readable semantic names from that file (the selection and renaming happen in
        # get_metadata, since add_to_nwbfile only writes the epocs left in event_columns).
        self._event_store_to_event_name = guppy_interface.event_store_to_event_name
        events_interface = TDTEventsInterface(folder_path=tdt_folder_path, verbose=verbose)
        super().__init__(
            data_interfaces={
                "TDTFiberPhotometry": tdt_interface,
                "TDTEvents": events_interface,
                "Guppy": guppy_interface,
            },
            verbose=verbose,
        )

    def get_metadata(self):
        """Merge sub-interface metadata, with the TDT tank as the authoritative session start time."""
        metadata = super().get_metadata()
        tdt_metadata = self.data_interface_objects["TDTFiberPhotometry"].get_metadata()
        metadata["NWBFile"]["session_start_time"] = tdt_metadata["NWBFile"]["session_start_time"]
        # The TDT side adds a FiberPhotometry lab_meta_data object named "fiber_photometry";
        # rename the GuPPy ProcessingModule to avoid colliding with that name during NWB write.
        metadata["Ophys"]["Guppy"]["ProcessingModule"]["name"] = "guppy"
        # Keep only the behavioral event stores GuPPy listed in storesList.csv and rename each to the
        # human-readable name GuPPy recorded there (e.g. the "PrtN" store becomes the "port_entries"
        # Events object). add_to_nwbfile only writes the epocs left in event_columns, so dropping the
        # others here excludes the unprocessed tank stores from acquisition.
        metadata_key = self.data_interface_objects["TDTEvents"].metadata_key
        event_columns = metadata["Events"][metadata_key]["event_columns"]
        renamed_event_columns = {}
        for epoc_name, event_name in self._event_store_to_event_name.items():
            column = event_columns[epoc_name]
            column["column_name"] = event_name
            column["description"] = (
                f"Onset times of the '{event_name}' behavioral events (from TDT store '{epoc_name}')."
            )
            renamed_event_columns[epoc_name] = column
        metadata["Events"][metadata_key]["event_columns"] = renamed_event_columns
        return metadata

    def get_metadata_schema(self) -> dict:
        """Allow the ``Ophys`` block to carry both ``Guppy`` and ``FiberPhotometry`` sub-schemas."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ophys"]["additionalProperties"] = True
        return metadata_schema

    def get_conversion_options_schema(self) -> dict:
        """Expose top-level stub/window options alongside the per-interface schemas."""
        schema = super().get_conversion_options_schema()
        schema["properties"]["stub_test"] = {
            "type": "boolean",
            "default": False,
            "description": "If True, only a short stub of each trace is written.",
        }
        schema["properties"]["t1"] = {
            "type": "number",
            "default": 0.0,
            "description": "Start time (seconds) for the TDT acquisition window.",
        }
        schema["properties"]["t2"] = {
            "type": "number",
            "default": 0.0,
            "description": "End time (seconds) for the TDT acquisition window. 0 means end of recording.",
        }
        return schema

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        conversion_options: dict | None = None,
        stub_test: bool = False,
        t1: float = 0.0,
        t2: float = 0.0,
    ) -> None:
        """Add raw TDT and GuPPy-derived data to the provided NWBFile.

        The TDT interface runs first (it builds the ``FiberPhotometryTable``), then the GuPPy step runs
        with auto-derived ``fiber_photometry_table_region_indices`` so its derived traces are written as
        ``FiberPhotometryResponseSeries`` linked back into that table. Ordering is guaranteed by the
        insertion order of ``data_interface_objects`` (TDT before GuPPy).
        """
        if metadata is None:
            metadata = self.get_metadata()

        conversion_options = conversion_options.copy() if conversion_options else {}
        tdt_options = {"stub_test": stub_test, "t1": t1, "t2": t2}
        tdt_options.update(conversion_options.pop("TDTFiberPhotometry", {}))
        events_options: dict = {}
        events_options.update(conversion_options.pop("TDTEvents", {}))
        guppy_options: dict = {
            "stub_test": stub_test,
            "fiber_photometry_table_region_indices": self._derive_region_to_table_indices(metadata),
        }
        guppy_options.update(conversion_options.pop("Guppy", {}))
        merged_conversion_options = {
            "TDTFiberPhotometry": tdt_options,
            "TDTEvents": events_options,
            "Guppy": guppy_options,
        }
        merged_conversion_options.update(conversion_options)

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
        t1: float = 0.0,
        t2: float = 0.0,
    ) -> None:
        """Run the NWB conversion for both TDT acquisition and GuPPy processing outputs."""
        if metadata is None:
            metadata = self.get_metadata()

        conversion_options = conversion_options.copy() if conversion_options else {}
        tdt_options = {"stub_test": stub_test, "t1": t1, "t2": t2}
        tdt_options.update(conversion_options.pop("TDTFiberPhotometry", {}))
        events_options: dict = {}
        events_options.update(conversion_options.pop("TDTEvents", {}))
        guppy_options: dict = {
            "stub_test": stub_test,
            "fiber_photometry_table_region_indices": self._derive_region_to_table_indices(metadata),
        }
        guppy_options.update(conversion_options.pop("Guppy", {}))
        merged_conversion_options = {
            "TDTFiberPhotometry": tdt_options,
            "TDTEvents": events_options,
            "Guppy": guppy_options,
        }
        merged_conversion_options.update(conversion_options)

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

    def _derive_region_to_table_indices(self, metadata: dict) -> dict[str, list[int]]:
        """Auto-derive each GuPPy region's fiber-photometry table row indices from the shared linkage.

        The join key is the acquisition store / ``stream_name`` that both sides reference:
        ``GuPPy region -> storesList store names -> response-series stream_name -> table row indices``.
        Each region unions the rows of every response series whose ``stream_name`` is one of that
        region's signal/control stores (rows can be many-to-many: several series may share a stream,
        and a region spans both its signal and isosbestic-control rows). Fails loudly if a region
        resolves to no rows.
        """
        response_series_metadata = metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"]
        stream_name_to_indices: dict[str, set] = {}
        for series in response_series_metadata:
            stream_name_to_indices.setdefault(series["stream_name"], set()).update(
                series["fiber_photometry_table_region"]
            )

        guppy_interface = self.data_interface_objects["Guppy"]
        region_to_indices: dict[str, list[int]] = {}
        for region in guppy_interface.regions:
            store_names = guppy_interface.region_to_store_names[region]
            indices: set = set()
            for store_name in store_names.values():
                indices.update(stream_name_to_indices.get(store_name, set()))
            assert indices, (
                f"GuPPy region '{region}' (stores {sorted(store_names.values())}) matched no "
                f"FiberPhotometryResponseSeries 'stream_name' in the acquisition metadata; cannot link "
                f"it to the fiber photometry table. Check that storesList.csv store names align with "
                f"the FiberPhotometryResponseSeries 'stream_name' entries."
            )
            region_to_indices[region] = sorted(indices)
        return region_to_indices
