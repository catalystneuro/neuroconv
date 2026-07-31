import re
from typing import Literal

import numpy
from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from .guppydatainterface import (
    _EVENTS_TABLE_DESCRIPTION,
    _EVENTS_TABLE_NAME,
    _RECORDING_SITES_TABLE_DESCRIPTION,
    _RECORDING_SITES_TABLE_NAME,
    _GuppyInterface,
)
from ..csv._demux import StrideDemux
from ..csv.csvfiberphotometrydatainterface import CSVFiberPhotometryInterface
from ..csv.multifilecsvfiberphotometrydatainterface import (
    MultiFileCSVFiberPhotometryInterface,
)
from ..doric.doricfiberphotometrydatainterface import DoricFiberPhotometryInterface
from ..npm.npmfiberphotometrydatainterface import NPMFiberPhotometryInterface
from ..tdt.tdtfiberphotometrydatainterface import TDTFiberPhotometryInterface
from ...events.csv_events.csveventsdatainterface import CSVEventsInterface
from ...events.doric_events.doriccsveventsdatainterface import DoricCSVEventsInterface
from ...events.doric_events.doriceventsdatainterface import DoricEventsInterface
from ...events.npm_events.npmeventsdatainterface import NPMEventsInterface
from ...events.tdt_events.tdteventsdatainterface import TDTEventsInterface
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

# The acquisition formats this converter can read, mapped to the interfaces it builds for each -- every
# format GuPPy itself supports. Adding another means adding its entry here, a branch in each of the two
# _build_* methods below, and widening the ``acquisition_format`` Literal. Nothing else knows the format.
_ACQUISITION_FORMAT_TO_INTERFACES = {
    "tdt": (TDTFiberPhotometryInterface, TDTEventsInterface),
    "csv": (MultiFileCSVFiberPhotometryInterface, CSVEventsInterface),
    "doric": (DoricFiberPhotometryInterface, DoricEventsInterface),
    "npm": (NPMFiberPhotometryInterface, NPMEventsInterface),
}


# GuPPy invents these names while demultiplexing an interleaved NPM recording: a file index, one of
# three ordinal channel slots, and a positional column index. See _npm_store_to_demux.
_NPM_STORE_PATTERN = re.compile(r"^file(\d+)_ch(ev|od|pr)(\d+)$")
_NPM_SLOTS = ("ev", "od", "pr")
# The low three bits of an NPM state word are one flag per excitation LED; the higher bits are digital
# lines. GuPPy orders its channel slots by the whole word, so the wavelength is recovered from the bits.
_NPM_EXCITATION_CODE_TO_WAVELENGTH = {1: 415, 2: 470, 4: 560}
_NPM_EXCITATION_BITS = 0b111


def _npm_column_count(file_path) -> int:
    """Return how many columns a CSV has, which is how GuPPy tells an NPM event file from a data file."""
    import pandas

    return int(pandas.read_csv(file_path, header=None, nrows=1).shape[1])


def _parses_as_float(value) -> bool:
    """Return whether a column label is numeric, which is how GuPPy detects a header-less NPM file."""
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _is_event_csv(file_path) -> bool:
    """Return whether a ``.csv`` holds GuPPy event onsets rather than acquisition traces.

    A GuPPy event CSV is a lone ``timestamps`` column. Doric exports are wide and lead with a device
    header row, so the two are told apart by the header alone -- the same distinction GuPPy draws when
    it decides which files in a session folder its Doric reader should look at.
    """
    import pandas

    columns = list(pandas.read_csv(file_path, nrows=0).columns)
    return len(columns) == 1 and str(columns[0]).strip().lower() == "timestamps"


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
    ``acquisition_format`` and the two ``_build_*`` methods that dispatch on it, which is where support
    for the remaining GuPPy-readable formats is added.

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
    # Derived from the supported formats rather than hard-coded, so this stays accurate as formats land.
    associated_suffixes = tuple(
        dict.fromkeys(
            _GuppyInterface.associated_suffixes
            + tuple(
                suffix
                for interfaces in _ACQUISITION_FORMAT_TO_INTERFACES.values()
                for interface in interfaces
                for suffix in interface.associated_suffixes
            )
        )
    )
    info = "Converter that bundles a GuPPy session's raw acquisition with its GuPPy-derived processing outputs."

    @validate_call
    def __init__(
        self,
        fiber_photometry_folder_path: DirectoryPath,
        events_folder_path: DirectoryPath,
        guppy_folder_path: DirectoryPath,
        *,
        acquisition_format: Literal["tdt", "csv", "doric", "npm"],
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
            data_interfaces[interface_name] = self._build_acquisition_interface(
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
            events_interfaces, source_id_to_store_id = self._build_events_interfaces(
                acquisition_format=acquisition_format,
                folder_path=events_folder_path,
                guppy_folder_path=guppy_folder_path,
                event_store_ids=list(self._event_store_to_event_name),
                verbose=verbose,
            )
        data_interfaces.update(events_interfaces)
        self._events_interface_names: list[str] = list(events_interfaces)
        # Most formats key their seeded event types by the same id storesList.csv uses, but not all can:
        # see _build_events_interfaces. This maps the ones that differ back onto the storesList id that
        # get_metadata joins on. Empty means "they already agree".
        self._event_source_id_to_store_id: dict[str, str] = source_id_to_store_id
        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

    # ------------------------------------------------------------------ acquisition-format seam
    # The only methods that know the acquisition format: the two _build_* dispatchers and the Doric
    # helpers they lean on. Supporting another GuPPy-readable format means adding a branch to each
    # dispatcher; everything else in this class is format-independent.

    @staticmethod
    def _npm_run_parameters(guppy_folder_path: DirectoryPath) -> dict:
        """Read the NPM settings the GuPPy run used but ``storesList.csv`` does not record.

        Which clock a store was read on, what unit it was in, and -- for the header-less layout -- how
        many channels were interleaved are all choices made when GuPPy ran, and none leave a mark on the
        raw file. GuPPy records the first two in a ``.npm_params.json`` beside ``storesList.csv``, keyed
        by the same file index the store names use, and the channel count in ``GuPPyParamtersUsed.json``.
        Both are required rather than guessed: an inferred clock silently produces wrong timestamps.
        """
        import json

        npm_parameters_path = guppy_folder_path / ".npm_params.json"
        assert npm_parameters_path.is_file(), (
            f"Missing {npm_parameters_path}. A GuPPy NPM run records the timestamp column and time unit "
            f"it used there, and neither can be recovered from the raw files."
        )
        npm_parameters = json.loads(npm_parameters_path.read_text(encoding="utf-8"))
        guppy_parameters = json.loads((guppy_folder_path / "GuPPyParamtersUsed.json").read_text(encoding="utf-8"))
        number_of_channels = guppy_parameters.get("noChannels")
        return dict(
            timestamp_column_names=npm_parameters["npm_timestamp_column_names"],
            time_units=npm_parameters["npm_time_units"],
            # Only the header-less layout needs this: a file carrying a state column derives its own
            # channel count, so a run that never read a header-less file need not have recorded one.
            number_of_channels=None if number_of_channels is None else int(number_of_channels),
        )

    @staticmethod
    def _npm_source_files(folder_path: DirectoryPath) -> list:
        """Return the folder's CSVs in the order GuPPy indexes them as ``file{N}``.

        GuPPy sorts the folder's CSVs by path and drops the files it derived itself, then indexes what
        remains. Event files are **not** dropped, so they occupy an index too and ``file{N}`` means "the
        Nth surviving CSV" rather than "the Nth data file" -- an event file that sorts early shifts every
        data file after it.
        """
        derived = set()
        for pattern in ("*chev*", "*chod*", "*chpr*", "event*"):
            derived.update(folder_path.glob(pattern))
        candidates = [path for path in sorted(folder_path.glob("*.csv")) if path not in derived]
        return [path for path in candidates if not _is_event_csv(path)]

    @classmethod
    def _npm_store_to_demux(cls, folder_path: DirectoryPath, store_id: str, *, number_of_channels: int) -> dict:
        """Decode a GuPPy NPM store name into the file, slot and column it was demultiplexed from.

        A name like ``file0_chod3`` is entirely synthetic: GuPPy invented it while splitting an
        interleaved NPM recording, and none of its three parts appear on disk. ``file0`` indexes
        :meth:`_npm_source_files`; ``chod`` is an ordinal into the LED states sorted ascending, sampled
        from rows 2-11 so the startup frame is skipped; ``3`` is a positional index into the columns left
        after GuPPy canonicalizes the timestamps and drops ``FrameCounter`` and the state column, with
        position 0 being the timestamps themselves.

        ``number_of_channels`` is used only for the legacy headerless layout, whose channel count has no
        on-disk signature; a file carrying a state column derives its own and ignores the argument, just
        as GuPPy does.
        """
        import pandas

        match = _NPM_STORE_PATTERN.match(store_id)
        assert (
            match is not None
        ), f"'{store_id}' is not a GuPPy NPM store name; expected the form 'file<N>_ch<ev|od|pr><column>'."
        file_index, slot, column_position = int(match.group(1)), match.group(2), int(match.group(3))
        slot_ordinal = _NPM_SLOTS.index(slot)

        source_files = cls._npm_source_files(folder_path)
        assert file_index < len(source_files), (
            f"Store '{store_id}' names file index {file_index}, but '{folder_path}' holds only "
            f"{len(source_files)} NPM source file(s): {[path.name for path in source_files]}."
        )
        file_path = source_files[file_index]

        dataframe = pandas.read_csv(file_path, index_col=False, nrows=12)
        headerless = any(_parses_as_float(column) for column in dataframe.columns)
        if headerless:
            # The legacy layout has no state column at all: channels cycle by row parity alone, and the
            # cycle length is whatever the GuPPy run was told it was.
            assert number_of_channels is not None, (
                f"'{file_path}' is a header-less NPM file, whose interleave has no on-disk signature, but "
                f"the GuPPy run recorded no 'noChannels'. Store '{store_id}' cannot be demultiplexed."
            )
            return dict(
                file_path=file_path,
                headerless=True,
                num_channels=number_of_channels,
                first_row=slot_ordinal,
                data_column=column_position,
                timestamps_column=0,
                state_value=None,
            )

        column_by_lowercase_name = {str(column).lower(): column for column in dataframe.columns}
        state_column = column_by_lowercase_name.get("flags") or column_by_lowercase_name.get("ledstate")
        assert state_column is not None, (
            f"'{file_path}' has a header but no 'Flags' or 'LedState' column, so GuPPy could not have "
            f"demultiplexed it into '{store_id}'."
        )
        state = pandas.read_csv(file_path, index_col=False)[state_column].to_numpy().astype(int)
        unique_states = numpy.unique(state[2:12])
        assert slot_ordinal < len(unique_states), (
            f"Store '{store_id}' names channel slot '{slot}' (index {slot_ordinal}), but '{file_path}' "
            f"interleaves only {len(unique_states)} channel(s) (states {unique_states.tolist()})."
        )
        state_value = int(unique_states[slot_ordinal])

        # Reproduce GuPPy's column trimming: the canonical timestamps column replaces the several it
        # found (only when there are several), then FrameCounter and the state column go.
        timestamp_columns = [column for column in dataframe.columns if "timestamp" in str(column).lower()]
        remaining = list(dataframe.columns)
        if len(timestamp_columns) > 1:
            remaining.insert(1, "Timestamp")
            remaining = [column for column in remaining if column not in timestamp_columns]
        remaining = [
            column for column in remaining if column not in (column_by_lowercase_name.get("framecounter"), state_column)
        ]
        assert column_position < len(remaining), (
            f"Store '{store_id}' names column position {column_position}, but '{file_path}' leaves only "
            f"{len(remaining)} column(s) after GuPPy's trimming: {remaining}."
        )
        return dict(
            file_path=file_path,
            headerless=False,
            num_channels=len(unique_states),
            first_row=int(numpy.where(state == state_value)[0][0]),
            data_column=remaining[column_position],
            timestamps_column=timestamp_columns[0] if timestamp_columns else None,
            state_value=state_value,
        )

    @staticmethod
    def _resolve_doric_file(folder_path: DirectoryPath):
        """Return the one Doric acquisition file in ``folder_path``.

        GuPPy requires a Doric session folder to hold exactly one acquisition file and hard-errors
        otherwise, so this mirrors that rule rather than guessing. Single-column ``timestamps`` CSVs are
        event files, not acquisition, and are excluded the way GuPPy excludes them.
        """
        candidates = sorted(folder_path.glob("*.doric")) + [
            path for path in sorted(folder_path.glob("*.csv")) if not _is_event_csv(path)
        ]
        assert len(candidates) == 1, (
            f"Expected exactly one Doric acquisition file in '{folder_path}', found {len(candidates)}: "
            f"{[path.name for path in candidates]}. A GuPPy Doric session folder holds one .doric or one "
            f"DoricStudio .csv export."
        )
        return candidates[0]

    @staticmethod
    def _doric_store_id_to_stream_name(file_path) -> dict[str, str]:
        """Map each GuPPy Doric store id to the stream name the Doric interface knows it by.

        GuPPy names a Doric store by the tail of its path -- the last two components for the modern
        ``DataAcquisition`` layout (skipping a ``Values`` leaf), the group name alone for the legacy
        ``Traces`` layout -- while the interface names it by the whole path with ``/`` replaced by ``_``.
        That flattening is not invertible on its own, because group names contain underscores too
        (``CAM1_EXC1``), so the mapping is derived from each stream's real internal path instead. Doric
        CSV columns need no translation and map to themselves.
        """
        store_id_to_stream_name: dict[str, list[str]] = {}
        for stream_name, stream_info in DoricFiberPhotometryInterface._discover_streams(file_path).items():
            if stream_info["format"] == "csv":
                store_id = stream_info["data_column"]
            else:
                parts = stream_info["data_path"].split("/")
                if parts[0] == "Traces":
                    store_id = parts[-1]
                elif parts[-1] == "Values":
                    store_id = f"{parts[-3]}/{parts[-2]}"
                else:
                    store_id = f"{parts[-2]}/{parts[-1]}"
            store_id_to_stream_name.setdefault(store_id, []).append(stream_name)

        ambiguous = {store: names for store, names in store_id_to_stream_name.items() if len(names) > 1}
        assert not ambiguous, (
            f"Doric file '{file_path}' contains streams that GuPPy would name identically: "
            f"{ambiguous}. GuPPy keeps only the tail of a stream's path, so these cannot be told apart "
            f"from a storesList.csv entry."
        )
        return {store: names[0] for store, names in store_id_to_stream_name.items()}

    @staticmethod
    def _build_acquisition_interface(
        *,
        acquisition_format: str,
        folder_path: DirectoryPath,
        guppy_folder_path: DirectoryPath,
        store_ids: list[str],
        metadata_key: str,
        verbose: bool,
    ):
        """Build the acquisition interface writing one series from the ordered ``store_ids``.

        The interface column-stacks the stores in the given order, which is the order
        ``_derive_recording_site_to_table_rows`` zips against the declared region -- so every branch
        must preserve ``store_ids`` order.

        For TDT, GuPPy's store ids are the tank's stream names verbatim and pass straight through; for
        CSV they are filename stems, so each names one file. Doric store ids are abbreviated paths that
        need real translation, which is why this dispatch exists at all rather than every format sharing
        one call.
        """
        if acquisition_format == "tdt":
            return TDTFiberPhotometryInterface(
                folder_path=folder_path,
                stream_names=store_ids,
                metadata_key=metadata_key,
                verbose=verbose,
            )
        if acquisition_format == "csv":
            # GuPPy writes one CSV per store, named for the store, with a fixed timestamps/data header.
            # The interface stacks them in file order and asserts they share a time axis.
            return MultiFileCSVFiberPhotometryInterface(
                file_paths=[folder_path / f"{store_id}.csv" for store_id in store_ids],
                data_columns="data",
                timestamps_column="timestamps",
                metadata_key=metadata_key,
                verbose=verbose,
            )
        if acquisition_format == "doric":
            file_path = GuppyConverter._resolve_doric_file(folder_path)
            store_id_to_stream_name = GuppyConverter._doric_store_id_to_stream_name(file_path)
            missing = [store_id for store_id in store_ids if store_id not in store_id_to_stream_name]
            # The Doric interface does not validate stream_names at construction, so an untranslated id
            # would surface much later as a bare KeyError; name the offending store here instead.
            assert not missing, (
                f"GuPPy's storesList.csv names acquisition store(s) {missing} that '{file_path}' does not "
                f"provide (available: {sorted(store_id_to_stream_name)})."
            )
            return DoricFiberPhotometryInterface(
                file_path=file_path,
                stream_names=[store_id_to_stream_name[store_id] for store_id in store_ids],
                metadata_key=metadata_key,
                verbose=verbose,
            )
        if acquisition_format == "npm":
            run_parameters = GuppyConverter._npm_run_parameters(guppy_folder_path)
            demuxes = [
                GuppyConverter._npm_store_to_demux(
                    folder_path, store_id, number_of_channels=run_parameters["number_of_channels"]
                )
                for store_id in store_ids
            ]
            # A role becomes one interface, so its stores must all be the same channel of the same file;
            # only the column may differ between recording sites.
            distinct = {(demux["file_path"], demux["first_row"], demux["num_channels"]) for demux in demuxes}
            assert len(distinct) == 1, (
                f"The '{metadata_key}' stores {store_ids} do not share one NPM file and channel "
                f"({[(demux['file_path'].name, demux['first_row']) for demux in demuxes]}), so they cannot "
                f"be written as one series."
            )
            first = demuxes[0]
            file_index = GuppyConverter._npm_source_files(folder_path).index(first["file_path"])
            time_unit = run_parameters["time_units"][file_index]

            if first["headerless"]:
                # No state column to select on, so reproduce GuPPy's blind stride. skip_rows carries the
                # phase rather than index, which is capped below the channel count.
                return CSVFiberPhotometryInterface(
                    file_path=first["file_path"],
                    data_columns=[demux["data_column"] for demux in demuxes],
                    timestamps_column=0,
                    demux_configuration=StrideDemux(
                        channels=first["num_channels"], index=0, skip_rows=first["first_row"]
                    ),
                    time_unit=time_unit,
                    metadata_key=metadata_key,
                    verbose=verbose,
                )

            excitation_code = first["state_value"] & _NPM_EXCITATION_BITS
            assert excitation_code in _NPM_EXCITATION_CODE_TO_WAVELENGTH, (
                f"The '{metadata_key}' stores were demultiplexed from NPM state {first['state_value']}, whose "
                f"excitation bits ({excitation_code:#05b}) are not a single wavelength. GuPPy treats such a "
                f"frame as its own channel, but a fiber photometry series is written per excitation."
            )
            timestamps_column = run_parameters["timestamp_column_names"][file_index] or first["timestamps_column"]
            return NPMFiberPhotometryInterface(
                file_path=first["file_path"],
                excitation_wavelength_in_nm=_NPM_EXCITATION_CODE_TO_WAVELENGTH[excitation_code],
                regions=[demux["data_column"] for demux in demuxes],
                timestamps_column=timestamps_column,
                time_unit=time_unit,
                metadata_key=metadata_key,
                verbose=verbose,
            )
        raise NotImplementedError(
            f"No acquisition interface is wired up for acquisition_format={acquisition_format!r}."
        )

    @staticmethod
    def _build_events_interfaces(
        *,
        acquisition_format: str,
        folder_path: DirectoryPath,
        guppy_folder_path: DirectoryPath,
        event_store_ids: list[str],
        verbose: bool,
    ) -> tuple[dict, dict]:
        """Build the interfaces reading the raw discrete events, keyed by converter interface name.

        Between them the returned interfaces must cover **every** behavioral event store GuPPy listed,
        and each type's ``event_type_source_id`` has to be the store id ``storesList.csv`` records --
        that id is the join key ``get_metadata`` uses to select and rename them. How many interfaces it
        takes is format-dependent, hence a dict rather than a single interface: one TDT interface reads
        every epoc in the tank and keys them by epoc name, while GuPPy's CSV format writes each store to
        its own file and ``CSVEventsInterface`` reads one file apiece.
        """
        if acquisition_format == "tdt":
            return {"Events": TDTEventsInterface(folder_path=folder_path, verbose=verbose)}, {}
        if acquisition_format == "csv":
            # A GuPPy event CSV is a single 'timestamps' column, so there is no event-type column to
            # split on; with event_type_column=None the lone type is keyed by the file stem, which is
            # the store id.
            return {
                f"Events_{store_id}": CSVEventsInterface(
                    file_path=folder_path / f"{store_id}.csv",
                    timestamps_column="timestamps",
                    event_type_column=None,
                    metadata_key=store_id,
                    verbose=verbose,
                )
                for store_id in event_store_ids
            }, {}
        if acquisition_format == "doric":
            file_path = GuppyConverter._resolve_doric_file(folder_path)
            is_csv_export = file_path.suffix.lower() == ".csv"
            # Doric event stores are digital lines of the one acquisition file, so a single interface
            # covers them all. Its signal ids match GuPPy's store ids except in the modern HDF5 layout,
            # where GuPPy prefixes the containing group: 'DigitalIO/CAM1' against the interface's 'CAM1'.
            # Only that layout is stripped -- doing it blindly would turn the CSV store 'DI/O-1' into
            # 'O-1'.
            store_id_to_signal_id = {
                store_id: (
                    store_id[len("DigitalIO/") :]
                    if not is_csv_export and store_id.startswith("DigitalIO/")
                    else store_id
                )
                for store_id in event_store_ids
            }
            # Naming the GuPPy store id as the spec's event_name makes it the seeded
            # event_type_source_id, so the select/rename/route blocks join on it exactly as they do for
            # the other formats. (The display name is overwritten with GuPPy's label there.)
            detection_configuration = {
                signal_id: [{"detection": "high_period", "event_name": store_id}]
                for store_id, signal_id in store_id_to_signal_id.items()
            }
            events_interface_class = DoricCSVEventsInterface if is_csv_export else DoricEventsInterface
            return {
                "Events": events_interface_class(
                    file_path=file_path,
                    detection_configuration=detection_configuration,
                    metadata_key="guppy_doric_events",
                    verbose=verbose,
                )
            }, {}
        if acquisition_format == "npm":
            run_parameters = GuppyConverter._npm_run_parameters(guppy_folder_path)
            # GuPPy writes NPM events to their own two-column file, and names each store by prefixing
            # "event" to the label it split on -- or calls the whole file "event0" when it split nothing.
            event_files = [
                path
                for path in sorted(folder_path.glob("*.csv"))
                if not _is_event_csv(path) and _npm_column_count(path) == 2
            ]
            assert len(event_files) == 1, (
                f"Expected exactly one NPM event file in '{folder_path}', found {len(event_files)}: "
                f"{[path.name for path in event_files]}."
            )
            event_file_path = event_files[0]
            file_index = sorted(folder_path.glob("*.csv")).index(event_file_path)
            time_unit = run_parameters["time_units"][file_index]

            if event_store_ids == ["event0"]:
                # The unsplit store: every row of the file as one event type. NPMEventsInterface always
                # splits by label, so this reads the same file through the generic CSV interface, which
                # keys its lone type by the file stem -- hence the translation back to 'event0'.
                return {
                    "Events": CSVEventsInterface(
                        file_path=event_file_path,
                        timestamps_column=0,
                        event_type_column=None,
                        time_unit=time_unit,
                        metadata_key="guppy_npm_events",
                        verbose=verbose,
                    )
                }, {event_file_path.stem: "event0"}

            unsplit = [store_id for store_id in event_store_ids if store_id == "event0"]
            assert not unsplit, (
                f"GuPPy's storesList.csv mixes the unsplit store 'event0' with split stores "
                f"{[store for store in event_store_ids if store != 'event0']}. 'event0' means the whole "
                f"event file as one type, which cannot coexist with types split out of that same file."
            )
            return {
                "Events": NPMEventsInterface(
                    file_path=event_file_path,
                    time_unit=time_unit,
                    metadata_key="guppy_npm_events",
                    verbose=verbose,
                )
            }, {store_id[len("event") :]: store_id for store_id in event_store_ids}
        raise NotImplementedError(f"No events interface is wired up for acquisition_format={acquisition_format!r}.")

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
        in :meth:`_build_events_interfaces` -- for which the seam supplies the translation.
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
