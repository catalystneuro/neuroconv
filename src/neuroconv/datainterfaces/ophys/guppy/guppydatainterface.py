import json
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas
from ndx_fiber_photometry import FiberPhotometryResponseSeries
from pydantic import DirectoryPath, validate_call
from pynwb.core import DynamicTable, VectorData
from pynwb.epoch import TimeIntervals
from pynwb.file import NWBFile

from neuroconv.basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils import DeepDict
from neuroconv.utils.json_schema import get_base_schema


def _column_parses_as_float(column: str) -> bool:
    try:
        float(column)
    except ValueError:
        return False
    return True


class GuppyInterface(BaseTemporalAlignmentInterface):
    """
    Data Interface for converting GuPPy (Guided Photometry Analysis in Python) processed outputs.

    GuPPy is a processing tool, not an acquisition system. This interface writes only the
    derived products that GuPPy actually computes (control fit, ΔF/F, z-score, transients, and
    per-region freq/amplitude summary). The raw signal/control traces and TTL/behavioral
    events are out of scope and are owned by the acquisition and event interfaces respectively.

    The derived continuous traces are written as ``ndx_fiber_photometry.FiberPhotometryResponseSeries``
    so they carry the same device/fiber/indicator provenance as the raw acquisition. Those series are
    not self-contained: each one needs a ``DynamicTableRegion`` into a ``FiberPhotometryTable`` that
    the *acquisition* side owns. This interface therefore does **not stand alone** -- its
    :meth:`add_to_nwbfile` requires the acquisition's ``FiberPhotometryTable`` to already be present in
    the NWBFile and a ``fiber_photometry_table_region_indices`` map (region -> table row indices) to be
    supplied by a converter that pairs GuPPy with an acquisition interface (see
    ``TDTFiberPhotometryGuppyConverter``). GuPPy retrieves that table and builds the per-trace regions
    itself; it exposes the join key the converter needs to compute the indices via
    :attr:`region_to_store_names`.

    All derived series and tables are placed in a ``ProcessingModule`` (default name
    ``fiber_photometry``).

    Note: each derived trace is 1-D ``(N,)`` but its table region may point at multiple rows (the
    excitation signal and isosbestic control it was computed from). This deliberately departs from
    the ``data.shape[1] == len(table_region)`` convention; it is an agreed interim representation
    tracked in ndx-fiber-photometry issue #54.
    """

    keywords = ("fiber photometry", "GuPPy", "processed")
    display_name = "Guppy"
    info = "Data Interface for converting fiber photometry data processed by GuPPy."
    associated_suffixes = ("hdf5", "csv", "h5", "json")

    _DERIVED_TRACE_PREFIXES = ("cntrl_sig_fit", "dff", "z_score")
    _TRANSIENT_FEATURES = ("z_score", "dff")

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        verbose: bool = False,
    ):
        """Initialize the GuppyInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the GuPPy output folder (the ``<session>_output_<N>`` directory containing
            ``storesList.csv``, the per-region derived ``.hdf5`` files, and the
            ``GuPPyParamtersUsed.json`` provenance file). GuPPy always writes
            ``GuPPyParamtersUsed.json`` into this folder, so it is discovered automatically; if
            it is missing the folder is not a valid GuPPy output and construction fails.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            folder_path=folder_path,
            verbose=verbose,
        )

        folder_path = Path(folder_path)
        stores_list_path = folder_path / "storesList.csv"
        assert (
            stores_list_path.is_file()
        ), f"storesList.csv not found in {folder_path}; this does not look like a GuPPy output folder."

        regions = self._discover_regions(stores_list_path)
        assert len(regions) > 0, (
            f"No regions discovered in {stores_list_path}. Expected semantic names matching "
            f"'signal_<R>' (with optional matching 'control_<R>')."
        )
        region_to_store_names = self._discover_region_to_store_names(stores_list_path)
        event_store_to_event_name = self._discover_event_store_to_event_name(stores_list_path)

        traces_by_region = {
            region: [
                prefix for prefix in self._DERIVED_TRACE_PREFIXES if (folder_path / f"{prefix}_{region}.hdf5").is_file()
            ]
            for region in regions
        }
        transients_by_region = {
            region: [
                feature
                for feature in self._TRANSIENT_FEATURES
                if (folder_path / f"transientsOccurrences_{feature}_{region}.csv").is_file()
            ]
            for region in regions
        }

        parameters_file_path = folder_path / "GuPPyParamtersUsed.json"
        assert (
            parameters_file_path.is_file()
        ), f"GuPPyParamtersUsed.json not found in {folder_path}; this does not look like a GuPPy output folder."
        with open(parameters_file_path, "r") as parameters_file:
            guppy_parameters = json.load(parameters_file)

        cross_correlations = self._discover_cross_correlations(folder_path=folder_path, regions=regions)
        valid_signal_intervals_by_region = self._discover_valid_signal_intervals(
            folder_path=folder_path, regions=regions
        )
        remove_artifacts_flag = guppy_parameters.get("removeArtifacts")
        if remove_artifacts_flag is True and not valid_signal_intervals_by_region:
            warnings.warn(
                "GuPPy parameters specify removeArtifacts=True but no coordsForPreProcessing_<region>.npy "
                "files were found; valid_signal_intervals will not be written.",
                UserWarning,
            )
        elif remove_artifacts_flag is False and valid_signal_intervals_by_region:
            warnings.warn(
                "GuPPy parameters specify removeArtifacts=False but coordsForPreProcessing_<region>.npy "
                "files were found; valid_signal_intervals will be written from the .npy files.",
                UserWarning,
            )

        artifact_removal_method = None
        if valid_signal_intervals_by_region:
            artifact_removal_method = guppy_parameters.get("artifactsRemovalMethod")
            if artifact_removal_method is None:
                warnings.warn(
                    "GuPPy parameters do not specify 'artifactsRemovalMethod' but artifact removal "
                    "intervals were found; defaulting to 'concatenate' (GuPPy's UI default).",
                    UserWarning,
                )
                artifact_removal_method = "concatenate"

        self.folder_path = folder_path
        self.parameters_file_path = parameters_file_path
        self.regions = regions
        self.region_to_store_names = region_to_store_names
        self.event_store_to_event_name = event_store_to_event_name
        self.traces_by_region = traces_by_region
        self.transients_by_region = transients_by_region
        self.cross_correlations = cross_correlations
        self.valid_signal_intervals_by_region = valid_signal_intervals_by_region
        self.artifact_removal_method = artifact_removal_method
        self.guppy_parameters = guppy_parameters
        self._region_to_aligned_timestamps: dict[str, np.ndarray] | None = None

    @staticmethod
    def _discover_regions(stores_list_path: Path) -> list[str]:
        rows = stores_list_path.read_text().strip().splitlines()
        assert len(rows) >= 2, f"storesList.csv at {stores_list_path} must have at least two rows."
        semantic_names = [name.strip() for name in rows[1].split(",")]
        return [name[len("signal_") :] for name in semantic_names if name.startswith("signal_")]

    @staticmethod
    def _discover_region_to_store_names(stores_list_path: Path) -> dict[str, dict[str, str]]:
        """Return ``{region: {"signal": <store>, "control": <store>}}`` from ``storesList.csv``.

        Row 0 of ``storesList.csv`` holds the acquisition store names (e.g. ``Dv2A``) and row 1 holds
        the matching GuPPy semantic names (e.g. ``signal_dms``). This mapping is the join key a
        converter uses to link GuPPy regions to acquisition fiber-photometry table rows. Only the
        ``signal_<region>`` and ``control_<region>`` stores participate; behavioral stores
        (``port_entries``, nose pokes, ...) are ignored.
        """
        rows = stores_list_path.read_text().strip().splitlines()
        assert len(rows) >= 2, f"storesList.csv at {stores_list_path} must have at least two rows."
        store_names = [name.strip() for name in rows[0].split(",")]
        semantic_names = [name.strip() for name in rows[1].split(",")]
        assert len(store_names) == len(semantic_names), (
            f"storesList.csv at {stores_list_path} has mismatched row lengths: "
            f"{len(store_names)} store names vs {len(semantic_names)} semantic names."
        )
        region_to_store_names: dict[str, dict[str, str]] = {}
        for store_name, semantic_name in zip(store_names, semantic_names):
            for kind in ("signal", "control"):
                prefix = f"{kind}_"
                if semantic_name.startswith(prefix):
                    region = semantic_name[len(prefix) :]
                    region_to_store_names.setdefault(region, {})[kind] = store_name
        return region_to_store_names

    @staticmethod
    def _discover_event_store_to_event_name(stores_list_path: Path) -> dict[str, str]:
        """Return ``{store_name: event_name}`` for the behavioral event stores in ``storesList.csv``.

        Row 0 of ``storesList.csv`` holds the acquisition store names (e.g. ``PrtN``) and row 1 the
        matching GuPPy semantic names (e.g. ``port_entries``). The ``signal_<region>`` and
        ``control_<region>`` stores are the fiber photometry channels; every *other* store in the
        list is a behavioral event GuPPy processed (e.g. ``PrtN`` -> ``port_entries``,
        ``LNRW`` -> ``rewarded_nose_pokes``). Stores present in the TDT tank but absent from
        ``storesList.csv`` were not used by GuPPy and are excluded.
        """
        rows = stores_list_path.read_text().strip().splitlines()
        assert len(rows) >= 2, f"storesList.csv at {stores_list_path} must have at least two rows."
        store_names = [name.strip() for name in rows[0].split(",")]
        semantic_names = [name.strip() for name in rows[1].split(",")]
        assert len(store_names) == len(semantic_names), (
            f"storesList.csv at {stores_list_path} has mismatched row lengths: "
            f"{len(store_names)} store names vs {len(semantic_names)} semantic names."
        )
        event_store_to_event_name: dict[str, str] = {}
        for store_name, semantic_name in zip(store_names, semantic_names):
            if semantic_name.startswith("signal_") or semantic_name.startswith("control_"):
                continue
            event_store_to_event_name[store_name] = semantic_name
        return event_store_to_event_name

    @classmethod
    def _discover_cross_correlations(cls, folder_path: Path, regions: list[str]) -> list[dict]:
        cross_correlation_folder = folder_path / "cross_correlation_output"
        if not cross_correlation_folder.is_dir():
            return []

        entries = []
        for cross_correlation_path in sorted(cross_correlation_folder.glob("corr_*.h5")):
            stem = cross_correlation_path.stem
            assert stem.startswith("corr_"), f"Unexpected cross-correlation filename: {cross_correlation_path.name}."
            remainder = stem[len("corr_") :]

            region_2 = next((region for region in regions if remainder.endswith(f"_{region}")), None)
            assert region_2 is not None, (
                f"Could not parse target region from {cross_correlation_path.name}; "
                f"expected suffix '_<region>' with region in {regions}."
            )
            remainder = remainder[: -len(f"_{region_2}")]

            region_1 = next((region for region in regions if remainder.endswith(f"_{region}")), None)
            assert region_1 is not None, (
                f"Could not parse reference region from {cross_correlation_path.name}; "
                f"expected suffix '_<region>' with region in {regions}."
            )
            remainder = remainder[: -len(f"_{region_1}")]

            feature = next((feat for feat in cls._TRANSIENT_FEATURES if remainder.endswith(f"_{feat}")), None)
            assert feature is not None, (
                f"Could not parse feature from {cross_correlation_path.name}; "
                f"expected suffix '_<feature>' with feature in {cls._TRANSIENT_FEATURES}."
            )
            event = remainder[: -len(f"_{feature}")]
            assert event, f"Could not parse event name from {cross_correlation_path.name}."

            entries.append(
                dict(
                    path=cross_correlation_path,
                    event=event,
                    feature=feature,
                    region_1=region_1,
                    region_2=region_2,
                )
            )
        return entries

    @classmethod
    def _discover_valid_signal_intervals(cls, folder_path: Path, regions: list[str]) -> dict[str, np.ndarray]:
        """Return ``{region: intervals_array}`` for each region with a coords file.

        ``intervals_array`` has shape ``(N, 2)`` with columns
        ``[start_in_seconds, stop_in_seconds]``. These are the intervals that GuPPy
        kept (not the artifacts), per the format in
        ``coordsForPreProcessing_<region>.npy``.
        """
        result = {}
        for region in regions:
            path = folder_path / f"coordsForPreProcessing_{region}.npy"
            if not path.is_file():
                continue
            coords = np.load(path)
            time_values = coords[:, 0]
            assert (
                time_values.shape[0] % 2 == 0
            ), f"Expected even number of coordinates in {path}, got {time_values.shape[0]}."
            result[region] = time_values.reshape(-1, 2)
        return result

    def _read_time_correction(self, region: str) -> dict:
        time_correction_path = self.folder_path / f"timeCorrection_{region}.hdf5"
        assert time_correction_path.is_file(), f"Missing {time_correction_path} for region '{region}'."
        with h5py.File(time_correction_path, "r") as f:
            # `timeRecStart` is absent for some acquisition formats (e.g. headerless CSV inputs)
            # that do not carry an absolute recording start time.
            time_rec_start = float(f["timeRecStart"][0]) if "timeRecStart" in f else None
            return dict(
                time_rec_start=time_rec_start,
                timestamps=f["timestampNew"][:],
                sampling_rate=float(f["sampling_rate"][0]),
            )

    def get_metadata(self) -> DeepDict:
        """Return metadata pre-populated from the GuPPy outputs and parameters file."""
        metadata = super().get_metadata()

        first_region = self.regions[0]
        time_correction = self._read_time_correction(first_region)
        if time_correction["time_rec_start"] is not None:
            session_start_datetime = datetime.fromtimestamp(time_correction["time_rec_start"], tz=timezone.utc)
            metadata["NWBFile"]["session_start_time"] = session_start_datetime

        guppy_parameters = self.guppy_parameters
        zscore_method = guppy_parameters.get("zscore_method", "unspecified")
        baseline_window_start = guppy_parameters.get("baselineWindowStart")
        baseline_window_end = guppy_parameters.get("baselineWindowEnd")
        filter_window = guppy_parameters.get("filter_window")
        isosbestic_control = guppy_parameters.get("isosbestic_control")

        prefix_to_unit = dict(cntrl_sig_fit="n.a.", dff="a.u.", z_score="a.u.")
        prefix_to_description_template = dict(
            cntrl_sig_fit=(
                "GuPPy fitted control trace for region '{region}' (linear fit of control_{region} onto signal_{region}; "
                "filter_window={filter_window}, isosbestic_control={isosbestic_control})."
            ),
            dff=(
                "GuPPy ΔF/F trace for region '{region}', computed as "
                "(signal_{region} − cntrl_sig_fit_{region}) / cntrl_sig_fit_{region}."
            ),
            z_score=(
                "GuPPy z-score trace for region '{region}' derived from dff_{region} "
                "(zscore_method={zscore_method}, baselineWindowStart={baseline_window_start}, "
                "baselineWindowEnd={baseline_window_end})."
            ),
        )

        traces_metadata = []
        for region in self.regions:
            for prefix in self.traces_by_region[region]:
                description = prefix_to_description_template[prefix].format(
                    region=region,
                    filter_window=filter_window,
                    isosbestic_control=isosbestic_control,
                    zscore_method=zscore_method,
                    baseline_window_start=baseline_window_start,
                    baseline_window_end=baseline_window_end,
                )
                traces_metadata.append(
                    dict(
                        name=f"{prefix}_{region}",
                        trace_basename=f"{prefix}_{region}",
                        region=region,
                        unit=prefix_to_unit[prefix],
                        description=description,
                    )
                )

        transients_metadata = []
        for region in self.regions:
            for feature in self.transients_by_region[region]:
                transients_metadata.append(
                    dict(
                        name=f"transients_{region}_{feature}",
                        region=region,
                        feature=feature,
                        description=(
                            f"GuPPy-detected transient peaks in {feature}_{region} "
                            f"(transientsThresh={guppy_parameters.get('transientsThresh')}, "
                            f"highAmpFilt={guppy_parameters.get('highAmpFilt')}, "
                            f"moving_window={guppy_parameters.get('moving_window')})."
                        ),
                    )
                )

        cross_correlations_metadata = []
        for entry in self.cross_correlations:
            event = entry["event"]
            feature = entry["feature"]
            region_1 = entry["region_1"]
            region_2 = entry["region_2"]
            cross_correlations_metadata.append(
                dict(
                    name=f"cross_correlation_{event}_{feature}_{region_1}_{region_2}",
                    event_name=event,
                    feature=feature,
                    region_1=region_1,
                    region_2=region_2,
                    description=(
                        f"GuPPy cross-correlation between region '{region_1}' (reference) and "
                        f"region '{region_2}' (target), aligned to event '{event}' onsets, computed "
                        f"on the '{feature}' trace. Positive lag means '{region_2}' leads "
                        f"'{region_1}'. Values are normalized per trial (divided by peak absolute value)."
                    ),
                )
            )

        guppy_version = guppy_parameters.get("guppy_version")
        processing_module_description = "GuPPy-derived fiber photometry processing outputs."
        if guppy_version is not None:
            processing_module_description = (
                f"GuPPy-derived fiber photometry processing outputs (GuPPy version {guppy_version})."
            )

        metadata["Ophys"]["Guppy"] = dict(
            ProcessingModule=dict(
                name="fiber_photometry",
                description=processing_module_description,
            ),
            Traces=traces_metadata,
            Transients=transients_metadata,
            TransientSummary=dict(
                name="transient_summary",
                description=("Per-(region, feature) GuPPy transient summary: events/min and mean peak amplitude."),
            ),
            CrossCorrelations=cross_correlations_metadata,
        )
        return metadata

    def get_metadata_schema(self) -> dict:
        """Return the metadata schema for this interface."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"].setdefault("Ophys", get_base_schema(tag="Ophys"))
        metadata_schema["properties"]["Ophys"]["properties"]["Guppy"] = dict(
            type="object",
            additionalProperties=False,
            required=["ProcessingModule", "Traces", "Transients", "TransientSummary", "CrossCorrelations"],
            properties=dict(
                ProcessingModule=dict(
                    type="object",
                    required=["name", "description"],
                    properties=dict(
                        name=dict(type="string"),
                        description=dict(type="string"),
                    ),
                ),
                Traces=dict(
                    type="array",
                    items=dict(
                        type="object",
                        required=["name", "trace_basename", "region", "unit", "description"],
                        properties=dict(
                            name=dict(type="string"),
                            trace_basename=dict(type="string"),
                            region=dict(type="string"),
                            unit=dict(type="string"),
                            description=dict(type="string"),
                        ),
                    ),
                ),
                Transients=dict(
                    type="array",
                    items=dict(
                        type="object",
                        required=["name", "region", "feature", "description"],
                        properties=dict(
                            name=dict(type="string"),
                            region=dict(type="string"),
                            feature=dict(type="string", enum=list(self._TRANSIENT_FEATURES)),
                            description=dict(type="string"),
                        ),
                    ),
                ),
                TransientSummary=dict(
                    type="object",
                    required=["name", "description"],
                    properties=dict(
                        name=dict(type="string"),
                        description=dict(type="string"),
                    ),
                ),
                CrossCorrelations=dict(
                    type="array",
                    items=dict(
                        type="object",
                        required=["name", "event_name", "feature", "region_1", "region_2", "description"],
                        properties=dict(
                            name=dict(type="string"),
                            event_name=dict(type="string"),
                            feature=dict(type="string", enum=list(self._TRANSIENT_FEATURES)),
                            region_1=dict(type="string"),
                            region_2=dict(type="string"),
                            description=dict(type="string"),
                        ),
                    ),
                ),
            ),
        )
        return metadata_schema

    def get_original_timestamps(self) -> dict[str, np.ndarray]:
        """Return the original (GuPPy-corrected) timestamps for each region."""
        return {region: self._read_time_correction(region)["timestamps"] for region in self.regions}

    def get_timestamps(self) -> dict[str, np.ndarray]:
        """Return the (possibly aligned) timestamps for each region."""
        if self._region_to_aligned_timestamps is not None:
            return self._region_to_aligned_timestamps
        return self.get_original_timestamps()

    def set_aligned_timestamps(self, region_to_aligned_timestamps: dict[str, np.ndarray]) -> None:
        """Override the per-region timestamps with externally-aligned arrays."""
        self._region_to_aligned_timestamps = region_to_aligned_timestamps

    def set_aligned_starting_time(self, aligned_starting_time: float) -> None:
        """Shift every region's timestamps by ``aligned_starting_time``."""
        region_to_timestamps = self.get_timestamps()
        self.set_aligned_timestamps(
            {region: timestamps + aligned_starting_time for region, timestamps in region_to_timestamps.items()}
        )

    @staticmethod
    def _get_fiber_photometry_table(nwbfile: NWBFile):
        """Return the acquisition ``FiberPhotometryTable`` already present in ``nwbfile``.

        GuPPy does not own this table; the acquisition interface must have added it (as a
        ``FiberPhotometry`` lab_meta_data object) before this interface runs.
        """
        fiber_photometry_lab_meta_data = next(
            (
                lab_meta_data
                for lab_meta_data in nwbfile.lab_meta_data.values()
                if hasattr(lab_meta_data, "fiber_photometry_table")
            ),
            None,
        )
        assert fiber_photometry_lab_meta_data is not None, (
            "No FiberPhotometryTable found in the NWBFile. GuppyInterface does not stand alone; the "
            "acquisition interface must add the fiber photometry table before GuPPy runs (drive both "
            "through a converter, e.g. TDTFiberPhotometryGuppyConverter)."
        )
        return fiber_photometry_lab_meta_data.fiber_photometry_table

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        fiber_photometry_table_region_indices: dict[str, list[int]],
        *,
        stub_test: bool = False,
    ) -> None:
        """
        Add GuPPy-derived fiber photometry products to an NWBFile.

        Traces, transient peaks, and valid-signal intervals are written on the timestamps GuPPy
        emits (seconds since recording start), or on the externally-aligned timestamps provided
        via :meth:`set_aligned_timestamps` / :meth:`set_aligned_starting_time`.

        This interface does **not stand alone**: the acquisition ``FiberPhotometryTable`` must already
        be present in ``nwbfile``, and ``fiber_photometry_table_region_indices`` is required. Both are
        supplied by a converter that owns the acquisition side (see
        ``TDTFiberPhotometryGuppyConverter``). Calling this without them fails loudly.

        Parameters
        ----------
        nwbfile : NWBFile
            The in-memory NWBFile to add the data to. Must already contain the acquisition
            ``FiberPhotometryTable`` (as a ``FiberPhotometry`` lab_meta_data object).
        metadata : dict
            Metadata dictionary; must contain ``metadata["Ophys"]["Guppy"]``.
        fiber_photometry_table_region_indices : dict[str, list[int]]
            Mapping from GuPPy region label (e.g. ``"dms"``) to the acquisition
            ``FiberPhotometryTable`` row indices that region's derived traces were computed from
            (typically the excitation signal and isosbestic control rows). GuPPy builds a fresh
            ``DynamicTableRegion`` per trace from these indices -- fresh per trace because a
            ``DynamicTableRegion`` cannot be parented to more than one ``TimeSeries``.
        stub_test : bool, optional
            If True, only the first ~1 second of each trace is written, and transient tables are
            filtered to peaks falling inside that window. Default = False.
        """
        fiber_photometry_table = self._get_fiber_photometry_table(nwbfile)
        guppy_metadata = metadata["Ophys"]["Guppy"]
        processing_module_metadata = guppy_metadata["ProcessingModule"]
        processing_module = get_module(
            nwbfile=nwbfile,
            name=processing_module_metadata["name"],
            description=processing_module_metadata["description"],
        )

        region_to_original_timestamps = self.get_original_timestamps()
        region_to_timestamps = self.get_timestamps()
        # Cache per-region stub bounds so transient tables share the trace's stub window.
        region_to_stub_end_time: dict[str, float] = {}

        # Derived continuous traces
        for trace_metadata in guppy_metadata["Traces"]:
            region = trace_metadata["region"]
            trace_basename = trace_metadata["trace_basename"]
            trace_path = self.folder_path / f"{trace_basename}.hdf5"
            with h5py.File(trace_path, "r") as f:
                data = f["data"][:]

            timestamps = region_to_timestamps[region]
            if stub_test:
                # Keep ~1 second, selected by timestamp window so gapped (artifact-removed)
                # timelines still stub correctly.
                stub_sample_count = int(np.searchsorted(timestamps, timestamps[0] + 1.0, side="right"))
                stub_sample_count = max(1, min(stub_sample_count, data.shape[0]))
                data = data[:stub_sample_count]
                timestamps = timestamps[:stub_sample_count]
                region_to_stub_end_time[region] = float(timestamps[-1])

            trace_name = trace_metadata["name"]
            assert region in fiber_photometry_table_region_indices, (
                f"No fiber_photometry_table_region_indices supplied for region '{region}' (trace "
                f"'{trace_name}'). GuppyInterface does not stand alone; drive it through a converter "
                f"(e.g. TDTFiberPhotometryGuppyConverter)."
            )
            # A fresh DynamicTableRegion per trace: one region cannot be parented to multiple series.
            fiber_photometry_table_region = fiber_photometry_table.create_fiber_photometry_table_region(
                description=(
                    f"Acquisition fiber-photometry table rows (excitation signal and isosbestic "
                    f"control) that GuPPy trace '{trace_name}' was computed from."
                ),
                region=fiber_photometry_table_region_indices[region],
            )
            response_series = FiberPhotometryResponseSeries(
                name=trace_name,
                description=trace_metadata["description"],
                data=data,
                unit=trace_metadata["unit"],
                timestamps=timestamps,
                fiber_photometry_table_region=fiber_photometry_table_region,
            )
            processing_module.add(response_series)

        # Per-region, per-feature transient peak tables
        for transient_metadata in guppy_metadata["Transients"]:
            region = transient_metadata["region"]
            feature = transient_metadata["feature"]
            occurrences_path = self.folder_path / f"transientsOccurrences_{feature}_{region}.csv"
            occurrences = pandas.read_csv(occurrences_path)
            peak_timestamps = occurrences["timestamps"].to_numpy(dtype=float)
            peak_amplitudes = occurrences["amplitude"].to_numpy(dtype=float)

            # Peaks are in GuPPy's emitted timebase; map them onto the (possibly aligned) timestamps.
            peak_timestamps = np.interp(
                peak_timestamps, region_to_original_timestamps[region], region_to_timestamps[region]
            )

            if stub_test:
                stub_end_time = region_to_stub_end_time.get(region)
                if stub_end_time is not None:
                    keep_mask = peak_timestamps <= stub_end_time
                    peak_timestamps = peak_timestamps[keep_mask]
                    peak_amplitudes = peak_amplitudes[keep_mask]

            transients_table = DynamicTable(
                name=transient_metadata["name"],
                description=transient_metadata["description"],
                columns=[
                    VectorData(
                        name="timestamp",
                        description="Timestamp of the detected transient peak (seconds, GuPPy timebase).",
                        data=peak_timestamps.astype(np.float64),
                    ),
                    VectorData(
                        name="amplitude",
                        description="Trace value at the detected transient peak.",
                        data=peak_amplitudes.astype(np.float64),
                    ),
                ],
            )
            processing_module.add(transients_table)

        # Single per-session transient summary table
        summary_metadata = guppy_metadata["TransientSummary"]
        summary_regions: list[str] = []
        summary_features: list[str] = []
        summary_frequencies: list[float] = []
        summary_amplitudes: list[float] = []
        for region in self.regions:
            for feature in self.transients_by_region[region]:
                freq_amp_path = self.folder_path / f"freqAndAmp_{feature}_{region}.h5"
                if not freq_amp_path.is_file():
                    continue
                freq_amp_dataframe = pandas.read_hdf(freq_amp_path)
                summary_regions.append(region)
                summary_features.append(feature)
                summary_frequencies.append(float(freq_amp_dataframe["freq (events/min)"].iloc[0]))
                summary_amplitudes.append(float(freq_amp_dataframe["amplitude"].iloc[0]))

        if summary_regions:
            transient_summary_table = DynamicTable(
                name=summary_metadata["name"],
                description=summary_metadata["description"],
                columns=[
                    VectorData(name="region", description="Brain region label.", data=summary_regions),
                    VectorData(
                        name="feature",
                        description="Trace used for transient detection ('z_score' or 'dff').",
                        data=summary_features,
                    ),
                    VectorData(
                        name="frequency_per_min",
                        description="Detected transient frequency in events per minute.",
                        data=summary_frequencies,
                    ),
                    VectorData(
                        name="mean_amplitude",
                        description="Mean amplitude of detected transient peaks.",
                        data=summary_amplitudes,
                    ),
                ],
            )
            processing_module.add(transient_summary_table)

        # Per-(event, feature, region pair) cross-correlation tables
        cross_correlation_entries_by_name = {
            entry["event"] + "|" + entry["feature"] + "|" + entry["region_1"] + "|" + entry["region_2"]: entry
            for entry in self.cross_correlations
        }
        for cross_correlation_metadata in guppy_metadata["CrossCorrelations"]:
            entry_key = (
                cross_correlation_metadata["event_name"]
                + "|"
                + cross_correlation_metadata["feature"]
                + "|"
                + cross_correlation_metadata["region_1"]
                + "|"
                + cross_correlation_metadata["region_2"]
            )
            entry = cross_correlation_entries_by_name[entry_key]
            cross_correlation_dataframe = pandas.read_hdf(entry["path"])
            if stub_test:
                cross_correlation_dataframe = cross_correlation_dataframe.iloc[
                    : min(len(cross_correlation_dataframe), 100)
                ]

            lag_axis = cross_correlation_dataframe["timestamps"].to_numpy(dtype=np.float64)
            entry_name = cross_correlation_metadata["name"]
            entry_description = cross_correlation_metadata["description"]

            trial_columns = [
                column for column in cross_correlation_dataframe.columns if _column_parses_as_float(column)
            ]
            bin_pattern = re.compile(r"^bin_\((\d+)-(\d+)\)$")
            bin_columns = sorted(
                (int(match.group(1)), int(match.group(2)), column)
                for column, match in (
                    (column, bin_pattern.match(column)) for column in cross_correlation_dataframe.columns
                )
                if match is not None
            )

            trial_table = DynamicTable(name=entry_name, description=entry_description)
            trial_table.add_column(
                name="trial_onset_in_seconds",
                description="Trial event onset time in seconds.",
            )
            trial_table.add_column(
                name="lag_in_seconds",
                description="Lag axis in seconds, symmetric around zero.",
                index=True,
            )
            trial_table.add_column(
                name="cross_correlation",
                description=(
                    "Normalized cross-correlation aligned to the trial event onset. "
                    "Each value at lag L is correlate(region_1, region_2) at lag L, "
                    "divided by the per-trial peak absolute value."
                ),
                index=True,
            )
            for trial_column in trial_columns:
                trial_table.add_row(
                    trial_onset_in_seconds=float(trial_column),
                    lag_in_seconds=lag_axis,
                    cross_correlation=cross_correlation_dataframe[trial_column].to_numpy(dtype=np.float64),
                )
            processing_module.add(trial_table)

            mean_table = DynamicTable(
                name=f"{entry_name}_mean",
                description=f"Across-trial mean cross-correlation for {entry_name}.",
                columns=[
                    VectorData(
                        name="lag_in_seconds",
                        description="Lag axis in seconds, symmetric around zero.",
                        data=lag_axis,
                    ),
                    VectorData(
                        name="mean",
                        description="Across-trial mean cross-correlation at each lag.",
                        data=cross_correlation_dataframe["mean"].to_numpy(dtype=np.float64),
                    ),
                ],
            )
            processing_module.add(mean_table)

            if bin_columns:
                psth_bins_table = DynamicTable(
                    name=f"{entry_name}_psth_bins",
                    description=(
                        f"Trial-binned PSTH cross-correlations for {entry_name}. "
                        f"Each row is a bin of consecutive trials, with mean and error across the bin."
                    ),
                )
                psth_bins_table.add_column(
                    name="bin_start_trial_index",
                    description="Start trial index of the bin (inclusive).",
                )
                psth_bins_table.add_column(
                    name="bin_end_trial_index",
                    description="End trial index of the bin (exclusive).",
                )
                psth_bins_table.add_column(
                    name="lag_in_seconds",
                    description="Lag axis in seconds, symmetric around zero.",
                    index=True,
                )
                psth_bins_table.add_column(
                    name="cross_correlation",
                    description="Mean cross-correlation across trials in the bin at each lag.",
                    index=True,
                )
                psth_bins_table.add_column(
                    name="cross_correlation_error",
                    description=(
                        "Error (e.g., SEM) of cross-correlation across trials in the bin at each lag. "
                        "NaN when the bin contains fewer than two valid trials."
                    ),
                    index=True,
                )
                for bin_start, bin_end, value_column in bin_columns:
                    error_column = f"bin_err_({bin_start}-{bin_end})"
                    psth_bins_table.add_row(
                        bin_start_trial_index=bin_start,
                        bin_end_trial_index=bin_end,
                        lag_in_seconds=lag_axis,
                        cross_correlation=cross_correlation_dataframe[value_column].to_numpy(dtype=np.float64),
                        cross_correlation_error=cross_correlation_dataframe[error_column].to_numpy(dtype=np.float64),
                    )
                processing_module.add(psth_bins_table)

        if self.valid_signal_intervals_by_region:
            valid_signal_intervals = TimeIntervals(
                name="valid_signal_intervals",
                description=(
                    "Time intervals retained as valid signal (i.e., not removed as artifacts) "
                    f"during GuPPy preprocessing. Method: {self.artifact_removal_method}. "
                    "Sourced from coordsForPreProcessing_<region>.npy."
                ),
            )
            valid_signal_intervals.add_column(
                name="region",
                description="Region the interval applies to.",
            )
            for region in sorted(self.valid_signal_intervals_by_region):
                intervals = self.valid_signal_intervals_by_region[region]
                # Interval boundaries are in GuPPy's emitted recording timebase. Shift them by the
                # same scalar offset applied to the region's timestamps (they are boundary values,
                # not per-sample timestamps to interpolate against).
                time_offset = float(region_to_timestamps[region][0]) - float(region_to_original_timestamps[region][0])
                shifted_intervals = intervals + time_offset
                for start, stop in shifted_intervals:
                    valid_signal_intervals.add_row(
                        start_time=float(start),
                        stop_time=float(stop),
                        region=region,
                    )
            processing_module.add(valid_signal_intervals)
