import json
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas
from hdmf.common import DynamicTableRegion
from pydantic import DirectoryPath, validate_call
from pynwb.core import VectorData
from pynwb.file import NWBFile

from neuroconv.basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from neuroconv.tools import get_package
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils import DeepDict
from neuroconv.utils.json_schema import get_base_schema


def _column_parses_as_float(column: str) -> bool:
    try:
        float(column)
    except ValueError:
        return False
    return True


# GuPPy derived-trace prefix -> ndx-guppy trace_type controlled value.
_PREFIX_TO_TRACE_TYPE = dict(cntrl_sig_fit="control_fit", dff="dff", z_score="z_score")
# Per-window peak/area metric row prefixes in the peak_AUC_*.h5 DataFrame index.
_BIN_COLUMN_PATTERN = re.compile(r"bin_\((\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\)$")


class GuppyInterface(BaseTemporalAlignmentInterface):
    """
    Data Interface for converting GuPPy (Guided Photometry Analysis in Python) processed outputs.

    GuPPy is a processing tool, not an acquisition system. This interface writes the derived products
    GuPPy computes -- control fit / ΔF/F / z-score traces, transient peaks and their summary, peri-event
    PSTHs, peak/AUC summaries, region-pair cross-correlations, and the valid-signal intervals -- as the
    dedicated ``ndx-guppy`` neurodata types, plus the GuPPy parameters (``GuppyParameters``) and two
    registry tables (``GuppyRegionsTable``, ``GuppyEventsTable``) that give region and event a single
    structured identity referenced by every product.

    The derived traces are ``GuppyDerivedResponseSeries`` (a ``FiberPhotometryResponseSeries`` subtype),
    so they carry the acquisition device/fiber/indicator provenance via ``fiber_photometry_table_region``.
    That link is the type's defining provenance, so this interface does **not stand alone**: its
    :meth:`add_to_nwbfile` requires the acquisition's ``FiberPhotometryTable`` to already be present and a
    ``fiber_photometry_table_region_indices`` map (region -> table row indices) supplied by a converter
    that pairs GuPPy with an acquisition interface (see ``TDTFiberPhotometryGuppyConverter``).

    The behavioral ``Events`` object reference on ``GuppyEventsTable`` is the one optional outward link --
    populated when the events live in the NWBFile's ``behavior`` module, omitted otherwise.

    All products are placed in a ``ProcessingModule`` (default name ``fiber_photometry``).
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
        event_names = sorted(set(event_store_to_event_name.values()))

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
        psths = self._discover_psths(folder_path=folder_path, event_names=event_names, regions=regions)
        peak_aucs = self._discover_peak_aucs(folder_path=folder_path, event_names=event_names, regions=regions)
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
        self.event_names = event_names
        self.traces_by_region = traces_by_region
        self.transients_by_region = transients_by_region
        self.cross_correlations = cross_correlations
        self.psths = psths
        self.peak_aucs = peak_aucs
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
    def _discover_psths(cls, folder_path: Path, event_names: list[str], regions: list[str]) -> list[dict]:
        """Discover GuPPy peri-event PSTH files for each (event, region, feature).

        GuPPy names PSTH files ``<event>_<region>_<feature>_<region>.h5`` (baseline-corrected) and
        ``<event>_<region>_baselineUncorrected_<feature>_<region>.h5`` (uncorrected). Expected names
        are constructed from the discovered events/regions/features and checked on disk, which avoids
        fragile filename parsing (event and region names both contain underscores).
        """
        entries = []
        for event in event_names:
            for region in regions:
                for feature in cls._TRANSIENT_FEATURES:
                    corrected = folder_path / f"{event}_{region}_{feature}_{region}.h5"
                    if corrected.is_file():
                        entries.append(
                            dict(path=corrected, event=event, region=region, feature=feature, baseline_corrected=True)
                        )
                    uncorrected = folder_path / f"{event}_{region}_baselineUncorrected_{feature}_{region}.h5"
                    if uncorrected.is_file():
                        entries.append(
                            dict(
                                path=uncorrected, event=event, region=region, feature=feature, baseline_corrected=False
                            )
                        )
        return entries

    @classmethod
    def _discover_peak_aucs(cls, folder_path: Path, event_names: list[str], regions: list[str]) -> list[dict]:
        """Discover GuPPy peak/AUC files (``peak_AUC_<event>_<region>_<feature>_<region>.h5``)."""
        entries = []
        for event in event_names:
            for region in regions:
                for feature in cls._TRANSIENT_FEATURES:
                    path = folder_path / f"peak_AUC_{event}_{region}_{feature}_{region}.h5"
                    if path.is_file():
                        entries.append(dict(path=path, event=event, region=region, feature=feature))
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

    def _bin_basis(self) -> str:
        """Whether GuPPy PSTH/cross-correlation bins are defined over 'trials' or 'time'."""
        use_time_or_trials = self.guppy_parameters.get("use_time_or_trials")
        if isinstance(use_time_or_trials, str) and use_time_or_trials.strip().lower().startswith("time"):
            return "time"
        return "trials"

    def _guppy_parameters_kwargs(self) -> dict:
        """Map ``GuPPyParamtersUsed.json`` keys onto ``GuppyParameters`` constructor kwargs."""
        parameters = self.guppy_parameters
        text_keys = dict(
            guppy_version="guppy_version",
            zscore_method="zscore_method",
            artifactsRemovalMethod="artifacts_removal_method",
        )
        bool_keys = dict(isosbestic_control="isosbestic_control", removeArtifacts="remove_artifacts")
        int_keys = dict(bin_psth_trials="bin_psth_trials")
        float_keys = dict(
            baselineWindowStart="baseline_window_start",
            baselineWindowEnd="baseline_window_end",
            filter_window="filter_window",
            transientsThresh="transients_thresh",
            highAmpFilt="high_amp_filt",
            moving_window="moving_window",
            nSecPrev="n_sec_prev",
            nSecPost="n_sec_post",
            timeInterval="time_interval",
            baselineCorrectionStart="baseline_correction_start",
            baselineCorrectionEnd="baseline_correction_end",
        )

        kwargs = dict(name="guppy_parameters")
        for json_key, attribute in text_keys.items():
            if parameters.get(json_key) is not None:
                kwargs[attribute] = str(parameters[json_key])
        for json_key, attribute in bool_keys.items():
            if parameters.get(json_key) is not None:
                kwargs[attribute] = bool(parameters[json_key])
        for json_key, attribute in int_keys.items():
            if parameters.get(json_key) is not None:
                kwargs[attribute] = int(parameters[json_key])
        for json_key, attribute in float_keys.items():
            if parameters.get(json_key) is not None:
                kwargs[attribute] = float(parameters[json_key])
        # GuPPy pads peak_startPoint/peak_endPoint to a fixed length with NaN; keep only the real windows.
        if parameters.get("peak_startPoint") is not None:
            start_points = np.asarray(parameters["peak_startPoint"], dtype=np.float64)
            end_points = np.asarray(parameters["peak_endPoint"], dtype=np.float64)
            valid = ~np.isnan(start_points)
            kwargs["peak_start_points"] = start_points[valid]
            kwargs["peak_end_points"] = end_points[valid]
        return kwargs

    def _peak_windows(self) -> tuple[np.ndarray, np.ndarray]:
        """Return the real (non-NaN-padded) peak window start/stop arrays from the parameters."""
        start_points = np.asarray(self.guppy_parameters.get("peak_startPoint"), dtype=np.float64)
        end_points = np.asarray(self.guppy_parameters.get("peak_endPoint"), dtype=np.float64)
        valid = ~np.isnan(start_points)
        return start_points[valid], end_points[valid]

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
                        trace_type=_PREFIX_TO_TRACE_TYPE[prefix],
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
                        trace_type=feature,
                        description=(
                            f"GuPPy-detected transient peaks in {feature}_{region} "
                            f"(transientsThresh={guppy_parameters.get('transientsThresh')}, "
                            f"highAmpFilt={guppy_parameters.get('highAmpFilt')}, "
                            f"moving_window={guppy_parameters.get('moving_window')})."
                        ),
                    )
                )

        # Each event-bearing product is one object per condition, concatenated across events; metadata
        # mirrors that with one entry per condition carrying the list of events it spans.
        cross_correlations_metadata = []
        for (feature, region_1, region_2), entries in self._group_by_condition(
            self.cross_correlations, ("feature", "region_1", "region_2")
        ).items():
            event_names = [entry["event"] for entry in entries]
            cross_correlations_metadata.append(
                dict(
                    name=f"cross_correlation_{feature}_{region_1}_{region_2}",
                    event_names=event_names,
                    trace_type=feature,
                    region_1=region_1,
                    region_2=region_2,
                    description=(
                        f"GuPPy cross-correlation between region '{region_1}' (reference) and "
                        f"region '{region_2}' (target), computed on the '{feature}' trace, with trials "
                        f"concatenated across events ({', '.join(event_names)}). Positive lag means "
                        f"'{region_2}' leads '{region_1}'. Values are normalized per trial (divided by "
                        f"peak absolute value)."
                    ),
                )
            )

        psths_metadata = []
        for (region, feature, baseline_corrected), entries in self._group_by_condition(
            self.psths, ("region", "feature", "baseline_corrected")
        ).items():
            event_names = [entry["event"] for entry in entries]
            suffix = "" if baseline_corrected else "_baseline_uncorrected"
            psths_metadata.append(
                dict(
                    name=f"psth_{region}_{feature}{suffix}",
                    event_names=event_names,
                    region=region,
                    trace_type=feature,
                    baseline_corrected=baseline_corrected,
                    description=(
                        f"GuPPy peri-event PSTH of the '{feature}' trace for region '{region}', with trials "
                        f"concatenated across events ({', '.join(event_names)}); "
                        f"{'baseline-corrected' if baseline_corrected else 'baseline-uncorrected'}."
                    ),
                )
            )

        peak_aucs_metadata = []
        for (region, feature), entries in self._group_by_condition(self.peak_aucs, ("region", "feature")).items():
            event_names = [entry["event"] for entry in entries]
            peak_aucs_metadata.append(
                dict(
                    name=f"peak_auc_{region}_{feature}",
                    event_names=event_names,
                    region=region,
                    trace_type=feature,
                    description=(
                        f"GuPPy peak/area summary of the '{feature}' PSTH for region '{region}', over the "
                        f"configured peak windows, with trials concatenated across events "
                        f"({', '.join(event_names)})."
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
                description=("Per-(region, trace_type) GuPPy transient summary: events/min and mean peak amplitude."),
            ),
            CrossCorrelations=cross_correlations_metadata,
            PSTHs=psths_metadata,
            PeakAUCs=peak_aucs_metadata,
        )
        return metadata

    def get_metadata_schema(self) -> dict:
        """Return the metadata schema for this interface."""
        trace_type_schema = dict(type="string", enum=list(self._TRANSIENT_FEATURES))
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"].setdefault("Ophys", get_base_schema(tag="Ophys"))
        metadata_schema["properties"]["Ophys"]["properties"]["Guppy"] = dict(
            type="object",
            additionalProperties=False,
            # Only the always-present keys are required. The data-dependent product
            # lists (Transients, CrossCorrelations, PSTHs, PeakAUCs) are empty for
            # sessions that lack those products -- e.g. a single-region experiment has
            # no region pairs to cross-correlate -- and empty lists are pruned from the
            # metadata before validation, so requiring them would reject valid sessions.
            required=[
                "ProcessingModule",
                "Traces",
                "TransientSummary",
            ],
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
                        required=["name", "trace_basename", "region", "trace_type", "unit", "description"],
                        properties=dict(
                            name=dict(type="string"),
                            trace_basename=dict(type="string"),
                            region=dict(type="string"),
                            trace_type=dict(type="string"),
                            unit=dict(type="string"),
                            description=dict(type="string"),
                        ),
                    ),
                ),
                Transients=dict(
                    type="array",
                    items=dict(
                        type="object",
                        required=["name", "region", "trace_type", "description"],
                        properties=dict(
                            name=dict(type="string"),
                            region=dict(type="string"),
                            trace_type=trace_type_schema,
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
                        required=["name", "event_names", "trace_type", "region_1", "region_2", "description"],
                        properties=dict(
                            name=dict(type="string"),
                            event_names=dict(type="array", items=dict(type="string")),
                            trace_type=trace_type_schema,
                            region_1=dict(type="string"),
                            region_2=dict(type="string"),
                            description=dict(type="string"),
                        ),
                    ),
                ),
                PSTHs=dict(
                    type="array",
                    items=dict(
                        type="object",
                        required=["name", "event_names", "region", "trace_type", "baseline_corrected", "description"],
                        properties=dict(
                            name=dict(type="string"),
                            event_names=dict(type="array", items=dict(type="string")),
                            region=dict(type="string"),
                            trace_type=trace_type_schema,
                            baseline_corrected=dict(type="boolean"),
                            description=dict(type="string"),
                        ),
                    ),
                ),
                PeakAUCs=dict(
                    type="array",
                    items=dict(
                        type="object",
                        required=["name", "event_names", "region", "trace_type", "description"],
                        properties=dict(
                            name=dict(type="string"),
                            event_names=dict(type="array", items=dict(type="string")),
                            region=dict(type="string"),
                            trace_type=trace_type_schema,
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
        Add GuPPy-derived fiber photometry products to an NWBFile as ndx-guppy neurodata types.

        Builds the ``GuppyParameters`` lab metadata, the ``GuppyRegionsTable`` and ``GuppyEventsTable``
        registries, and the per-product objects (traces, transients, summary, cross-correlation, PSTH,
        peak/AUC, valid intervals), each referencing its registry rows. Products are written on the
        timestamps GuPPy emits, or on the externally-aligned timestamps provided via
        :meth:`set_aligned_timestamps` / :meth:`set_aligned_starting_time`.

        This interface does **not stand alone**: the acquisition ``FiberPhotometryTable`` must already be
        present in ``nwbfile`` and ``fiber_photometry_table_region_indices`` is required (the derived
        traces are ``FiberPhotometryResponseSeries`` whose ``fiber_photometry_table_region`` link is their
        defining provenance). Both are supplied by a converter that owns the acquisition side (see
        ``TDTFiberPhotometryGuppyConverter``).

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
            (typically the excitation signal and isosbestic control rows).
        stub_test : bool, optional
            If True, only a short slice of each large product is written. Default = False.
        """
        ndx_guppy = get_package(package_name="ndx_guppy", installation_instructions="pip install ndx-guppy")

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
        region_to_stub_end_time: dict[str, float] = {}
        bin_basis = self._bin_basis()

        # Session-wide typed parameters.
        nwbfile.add_lab_meta_data(ndx_guppy.GuppyParameters(**self._guppy_parameters_kwargs()))

        # Registries: region and event identity, referenced by every product.
        regions_table = self._add_regions_table(
            ndx_guppy=ndx_guppy,
            processing_module=processing_module,
            fiber_photometry_table=fiber_photometry_table,
            fiber_photometry_table_region_indices=fiber_photometry_table_region_indices,
        )
        events_table = self._add_events_table(ndx_guppy=ndx_guppy, processing_module=processing_module, nwbfile=nwbfile)
        region_to_row_index = {region: index for index, region in enumerate(self.regions)}
        event_to_row_index = {event_name: index for index, event_name in enumerate(self.event_names)}

        def region_reference(region_names: list[str]) -> DynamicTableRegion:
            return DynamicTableRegion(
                name="region",
                data=[region_to_row_index[region] for region in region_names],
                description="GuPPy region(s) this object was computed from.",
                table=regions_table,
            )

        def event_reference(event_names: list[str], name: str = "event") -> DynamicTableRegion:
            return DynamicTableRegion(
                name=name,
                data=[event_to_row_index[event_name] for event_name in event_names],
                description="GuPPy behavioral event(s) this object's columns were aligned to.",
                table=events_table,
            )

        # Derived continuous traces.
        for trace_metadata in guppy_metadata["Traces"]:
            region = trace_metadata["region"]
            trace_basename = trace_metadata["trace_basename"]
            with h5py.File(self.folder_path / f"{trace_basename}.hdf5", "r") as f:
                data = f["data"][:]
            timestamps = region_to_timestamps[region]
            if stub_test:
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
            response_series = ndx_guppy.GuppyDerivedResponseSeries(
                name=trace_name,
                description=trace_metadata["description"],
                data=data,
                unit=trace_metadata["unit"],
                timestamps=timestamps,
                trace_type=trace_metadata["trace_type"],
                region=region_reference([region]),
                fiber_photometry_table_region=fiber_photometry_table_region,
            )
            processing_module.add(response_series)

        # Per-(region, trace_type) transient peak tables.
        for transient_metadata in guppy_metadata["Transients"]:
            region = transient_metadata["region"]
            trace_type = transient_metadata["trace_type"]
            occurrences = pandas.read_csv(self.folder_path / f"transientsOccurrences_{trace_type}_{region}.csv")
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

            transients_table = ndx_guppy.GuppyTransientsTable(
                name=transient_metadata["name"],
                description=transient_metadata["description"],
                trace_type=trace_type,
                unit="a.u.",
                columns=[
                    DynamicTableRegion(
                        name="region",
                        data=[region_to_row_index[region]] * len(peak_timestamps),
                        description=f"GuPPy region '{region}'.",
                        table=regions_table,
                    ),
                    VectorData(
                        name="timestamp",
                        description="Timestamp of the detected transient peak (seconds, session clock).",
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

        # Single per-session transient summary table.
        self._add_transient_summary(
            ndx_guppy=ndx_guppy,
            processing_module=processing_module,
            regions_table=regions_table,
            region_to_row_index=region_to_row_index,
            summary_metadata=guppy_metadata["TransientSummary"],
        )

        # Cross-correlations: one GuppyCrossCorrelation per (trace_type, region-pair) condition,
        # concatenating every event's trials/bins along the trials/bin axes.
        cross_correlation_groups = self._group_by_condition(
            self.cross_correlations, ("feature", "region_1", "region_2")
        )
        for cross_correlation_metadata in guppy_metadata["CrossCorrelations"]:
            entries = cross_correlation_groups[
                (
                    cross_correlation_metadata["trace_type"],
                    cross_correlation_metadata["region_1"],
                    cross_correlation_metadata["region_2"],
                )
            ]
            concatenated = self._concatenate_event_matrices(entries, stub_test=stub_test)
            cross_correlation_kwargs = dict(
                name=cross_correlation_metadata["name"],
                trace_type=cross_correlation_metadata["trace_type"],
                unit="a.u.",
                region=region_reference(
                    [cross_correlation_metadata["region_1"], cross_correlation_metadata["region_2"]]
                ),
                event=event_reference(concatenated["trial_event_names"]),
                summary_event=event_reference(concatenated["summary_event_names"], name="summary_event"),
                lag=concatenated["axis"],
                trial_onset_times=concatenated["trial_onset_times"],
                trials=concatenated["traces"],
                mean=concatenated["mean"],
                error=concatenated["error"],
            )
            if "bin_edges" in concatenated:
                cross_correlation_kwargs.update(
                    bin_edges=concatenated["bin_edges"],
                    bin_edges__bin_basis=bin_basis,
                    bin_event=event_reference(concatenated["bin_event_names"], name="bin_event"),
                    binned_mean=concatenated["binned_value"],
                    binned_error=concatenated["binned_error"],
                )
            processing_module.add(ndx_guppy.GuppyCrossCorrelation(**cross_correlation_kwargs))

        # Peri-event PSTHs: one GuppyPSTH per (region, trace_type, baseline) condition,
        # concatenating every event's trials/bins along the trials/bin axes.
        psth_groups = self._group_by_condition(self.psths, ("region", "feature", "baseline_corrected"))
        for psth_metadata in guppy_metadata["PSTHs"]:
            entries = psth_groups[
                (psth_metadata["region"], psth_metadata["trace_type"], psth_metadata["baseline_corrected"])
            ]
            concatenated = self._concatenate_event_matrices(entries, stub_test=stub_test)
            psth_kwargs = dict(
                name=psth_metadata["name"],
                trace_type=psth_metadata["trace_type"],
                baseline_corrected=bool(psth_metadata["baseline_corrected"]),
                unit="a.u.",
                region=region_reference([psth_metadata["region"]]),
                event=event_reference(concatenated["trial_event_names"]),
                summary_event=event_reference(concatenated["summary_event_names"], name="summary_event"),
                peri_event_time=concatenated["axis"],
                trial_onset_times=concatenated["trial_onset_times"],
                traces=concatenated["traces"],
                mean=concatenated["mean"],
                error=concatenated["error"],
            )
            if "bin_edges" in concatenated:
                psth_kwargs.update(
                    bin_edges=concatenated["bin_edges"],
                    bin_edges__bin_basis=bin_basis,
                    bin_event=event_reference(concatenated["bin_event_names"], name="bin_event"),
                    binned_mean=concatenated["binned_value"],
                    binned_error=concatenated["binned_error"],
                )
            processing_module.add(ndx_guppy.GuppyPSTH(**psth_kwargs))

        # Peak/AUC summaries: one GuppyPeakAUC per (region, trace_type) condition, concatenated across events.
        peak_auc_groups = self._group_by_condition(self.peak_aucs, ("region", "feature"))
        for peak_auc_metadata in guppy_metadata["PeakAUCs"]:
            entries = peak_auc_groups[(peak_auc_metadata["region"], peak_auc_metadata["trace_type"])]
            peak_auc = self._build_peak_auc(
                ndx_guppy=ndx_guppy,
                entries=entries,
                peak_auc_metadata=peak_auc_metadata,
                region_reference=region_reference,
                event_reference=event_reference,
                bin_basis=bin_basis,
            )
            processing_module.add(peak_auc)

        # Valid-signal intervals.
        if self.valid_signal_intervals_by_region:
            valid_signal_intervals = ndx_guppy.GuppyValidSignalIntervals(
                name="valid_signal_intervals",
                description=(
                    "Time intervals retained as valid signal (i.e., not removed as artifacts) "
                    f"during GuPPy preprocessing. Method: {self.artifact_removal_method}. "
                    "Sourced from coordsForPreProcessing_<region>.npy."
                ),
                target_tables={"region": regions_table},
            )
            for region in sorted(self.valid_signal_intervals_by_region):
                intervals = self.valid_signal_intervals_by_region[region]
                # Interval boundaries are in GuPPy's emitted recording timebase. Shift them by the same
                # scalar offset applied to the region's timestamps (they are boundary values, not
                # per-sample timestamps to interpolate against).
                time_offset = float(region_to_timestamps[region][0]) - float(region_to_original_timestamps[region][0])
                for start, stop in intervals + time_offset:
                    valid_signal_intervals.add_row(
                        start_time=float(start),
                        stop_time=float(stop),
                        region=region_to_row_index[region],
                    )
            processing_module.add(valid_signal_intervals)

    def _add_regions_table(
        self, ndx_guppy, processing_module, fiber_photometry_table, fiber_photometry_table_region_indices: dict
    ):
        """Build and add the GuppyRegionsTable, linking each region to its fiber photometry rows."""
        regions_table = ndx_guppy.GuppyRegionsTable(
            name="regions",
            description="GuPPy logical regions (one row per region). Each row's optional fiber link points "
            "at the acquisition FiberPhotometryTable signal + isosbestic rows for that region.",
            target_tables={"fiber_photometry_table_region": fiber_photometry_table},
        )
        for region in self.regions:
            assert region in fiber_photometry_table_region_indices, (
                f"No fiber_photometry_table_region_indices supplied for region '{region}'. GuppyInterface "
                f"does not stand alone; drive it through a converter (e.g. TDTFiberPhotometryGuppyConverter)."
            )
            regions_table.add_row(
                region=region,
                raw_store_name=self.region_to_store_names.get(region, {}).get("signal"),
                fiber_photometry_table_region=list(fiber_photometry_table_region_indices[region]),
            )
        processing_module.add(regions_table)
        return regions_table

    def _add_events_table(self, ndx_guppy, processing_module, nwbfile: NWBFile):
        """Build and add the GuppyEventsTable, optionally referencing behavior Events objects by name."""
        behavior_objects = {}
        if "behavior" in nwbfile.processing:
            behavior_objects = dict(nwbfile.processing["behavior"].data_interfaces)

        name_to_store = {event_name: store for store, event_name in self.event_store_to_event_name.items()}
        event_references = [behavior_objects.get(event_name) for event_name in self.event_names]
        include_event_references = len(event_references) > 0 and all(
            reference is not None for reference in event_references
        )

        events_table = ndx_guppy.GuppyEventsTable(
            name="events",
            description="GuPPy behavioral events (one row per event GuPPy aligned to).",
        )
        for event_name, reference in zip(self.event_names, event_references):
            store = name_to_store[event_name]
            row_kwargs = dict(
                event_name=event_name,
                event_description=(
                    f"Behavioral event '{event_name}' that GuPPy aligned to (acquisition store '{store}')."
                ),
                raw_store_name=store,
            )
            if include_event_references:
                row_kwargs["events"] = reference
            events_table.add_row(**row_kwargs)
        processing_module.add(events_table)
        return events_table

    def _add_transient_summary(
        self, ndx_guppy, processing_module, regions_table, region_to_row_index: dict, summary_metadata: dict
    ):
        """Build and add the per-session GuppyTransientSummaryTable, if any freqAndAmp files exist."""
        summary_region_indices: list[int] = []
        summary_trace_types: list[str] = []
        summary_frequencies: list[float] = []
        summary_amplitudes: list[float] = []
        for region in self.regions:
            for feature in self.transients_by_region[region]:
                freq_amp_path = self.folder_path / f"freqAndAmp_{feature}_{region}.h5"
                if not freq_amp_path.is_file():
                    continue
                freq_amp_dataframe = pandas.read_hdf(freq_amp_path)
                summary_region_indices.append(region_to_row_index[region])
                summary_trace_types.append(feature)
                summary_frequencies.append(float(freq_amp_dataframe["freq (events/min)"].iloc[0]))
                summary_amplitudes.append(float(freq_amp_dataframe["amplitude"].iloc[0]))

        if not summary_region_indices:
            return

        transient_summary_table = ndx_guppy.GuppyTransientSummaryTable(
            name=summary_metadata["name"],
            description=summary_metadata["description"],
            columns=[
                DynamicTableRegion(
                    name="region",
                    data=summary_region_indices,
                    description="GuPPy region for this summary row.",
                    table=regions_table,
                ),
                VectorData(
                    name="trace_type",
                    description="Trace used for transient detection ('z_score' or 'dff').",
                    data=summary_trace_types,
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

    def _group_by_condition(self, entries: list[dict], key_fields: tuple[str, ...]) -> dict[tuple, list[dict]]:
        """Group per-event discovery entries by a condition key, ordering each group by event.

        ``key_fields`` are the entry fields that define a condition (everything except the event),
        e.g. ``("region", "feature", "baseline_corrected")`` for PSTHs. Within each group the entries
        are ordered by their event's position in ``self.event_names`` so concatenation across events
        is deterministic.
        """
        event_order = {event_name: index for index, event_name in enumerate(self.event_names)}
        groups: dict[tuple, list[dict]] = {}
        for entry in entries:
            key = tuple(entry[field] for field in key_fields)
            groups.setdefault(key, []).append(entry)
        for entry_list in groups.values():
            entry_list.sort(key=lambda entry: event_order[entry["event"]])
        return groups

    def _concatenate_event_matrices(self, entries: list[dict], stub_test: bool) -> dict:
        """Read each event's PSTH/cross-correlation dataframe and concatenate across events.

        PSTH and cross-correlation files share a layout: an x-axis column ``timestamps``, one
        float-named column per trial, an across-trial ``mean``/``err``, and optional
        ``bin_(a-b)``/``bin_err_(a-b)`` columns. Trials and bins are concatenated across events (each
        column labeled by its event); the per-event ``mean``/``err`` become one column per event.
        """
        axis = None
        traces_blocks: list[np.ndarray] = []
        trial_onset_times: list[float] = []
        trial_event_names: list[str] = []
        mean_columns: list[np.ndarray] = []
        error_columns: list[np.ndarray] = []
        summary_event_names: list[str] = []
        bin_edges_blocks: list[np.ndarray] = []
        binned_value_blocks: list[np.ndarray] = []
        binned_error_blocks: list[np.ndarray] = []
        bin_event_names: list[str] = []

        for entry in entries:
            event_name = entry["event"]
            dataframe = pandas.read_hdf(entry["path"])
            if stub_test:
                dataframe = dataframe.iloc[: min(len(dataframe), 100)]

            event_axis = dataframe["timestamps"].to_numpy(dtype=np.float64)
            if axis is None:
                axis = event_axis
            else:
                assert np.array_equal(axis, event_axis), (
                    f"GuPPy event files for one condition must share an identical x-axis to be "
                    f"concatenated across events, but '{entry['path'].name}' differs."
                )

            trial_columns = [column for column in dataframe.columns if _column_parses_as_float(column)]
            traces_blocks.append(dataframe[trial_columns].to_numpy(dtype=np.float64))
            trial_onset_times.extend(float(column) for column in trial_columns)
            trial_event_names.extend([event_name] * len(trial_columns))

            mean_columns.append(dataframe["mean"].to_numpy(dtype=np.float64))
            error_columns.append(dataframe["err"].to_numpy(dtype=np.float64))
            summary_event_names.append(event_name)

            binned = self._extract_bins(dataframe)
            if binned is not None:
                bin_edges_blocks.append(binned["bin_edges"])
                binned_value_blocks.append(binned["binned_value"])
                binned_error_blocks.append(binned["binned_error"])
                bin_event_names.extend([event_name] * binned["bin_edges"].shape[0])

        concatenated = dict(
            axis=axis,
            traces=np.concatenate(traces_blocks, axis=1),
            trial_onset_times=np.array(trial_onset_times, dtype=np.float64),
            trial_event_names=trial_event_names,
            mean=np.stack(mean_columns, axis=1),
            error=np.stack(error_columns, axis=1),
            summary_event_names=summary_event_names,
        )
        if bin_edges_blocks:
            concatenated.update(
                bin_edges=np.concatenate(bin_edges_blocks, axis=0),
                binned_value=np.concatenate(binned_value_blocks, axis=1),
                binned_error=np.concatenate(binned_error_blocks, axis=1),
                bin_event_names=bin_event_names,
            )
        return concatenated

    @staticmethod
    def _extract_bins(dataframe: pandas.DataFrame):
        """Return stacked ``(num_x, num_bins)`` binned value/error arrays + ``(num_bins, 2)`` edges, or None.

        Bin value columns match ``bin_(<start>-<stop>)`` (integer ``bin_(0-3)`` for "# of trials" binning
        or decimal ``bin_(0.0-2.0)`` for "Time (min)" binning) and their errors ``bin_err_(<start>-<stop>)``.
        The original column labels are reused verbatim for lookup -- and the error column is derived by
        swapping the ``bin_(`` prefix for ``bin_err_(`` -- so both label formats resolve without
        reconstructing the name from the parsed edges. Bin edges are assumed non-negative.
        """
        bin_columns = sorted(
            (float(match.group(1)), float(match.group(2)), match.string)
            for match in (_BIN_COLUMN_PATTERN.search(column) for column in dataframe.columns)
            if match is not None
        )
        if not bin_columns:
            return None
        bin_edges = np.array([[start, stop] for start, stop, _ in bin_columns], dtype=np.float64)
        binned_value = np.stack(
            [dataframe[column].to_numpy(dtype=np.float64) for _, _, column in bin_columns],
            axis=1,
        )
        binned_error = np.stack(
            [
                dataframe[column.replace("bin_(", "bin_err_(", 1)].to_numpy(dtype=np.float64)
                for _, _, column in bin_columns
            ],
            axis=1,
        )
        return dict(bin_edges=bin_edges, binned_value=binned_value, binned_error=binned_error)

    @staticmethod
    def _partition_peak_auc_index(index):
        """Split a peak_AUC_*.h5 DataFrame index into ``(trial_rows, bin_rows, mean_row)``.

        ``trial_rows`` is a sorted list of ``(onset_time: float, row_label)``; ``bin_rows`` a sorted list
        of ``(start: float, stop: float, row_label)``; ``mean_row`` the single ``..._mean`` label. Bin rows
        are session-id-prefixed labels like ``..._bin_(0-3)`` (integer "# of trials" binning) or
        ``..._bin_(0.0-2.0)`` (decimal "Time (min)" binning); both are routed to ``bin_rows`` rather than
        crashing the trial-onset parse. Bin edges are assumed non-negative.
        """
        mean_row = None
        trial_rows: list[tuple[float, str]] = []
        bin_rows: list[tuple[float, float, str]] = []
        for index_value in index:
            row = str(index_value)
            bin_match = _BIN_COLUMN_PATTERN.search(row)
            if bin_match is not None:
                bin_rows.append((float(bin_match.group(1)), float(bin_match.group(2)), row))
            elif row.endswith("mean"):
                mean_row = row
            else:
                trial_rows.append((float(row.rsplit("_", 1)[-1]), row))
        trial_rows.sort()
        bin_rows.sort()
        return trial_rows, bin_rows, mean_row

    def _build_peak_auc(
        self, ndx_guppy, entries: list[dict], peak_auc_metadata: dict, region_reference, event_reference, bin_basis: str
    ):
        """Build a full-fidelity GuppyPeakAUC for one (region, trace_type) condition, concatenated across events.

        Each event's peak_AUC_*.h5 is a DataFrame whose columns are the per-window metric names
        (``peak_pos_<w>`` / ``peak_neg_<w>`` / ``area_<w>``) and whose index rows are the
        session-id-prefixed per-trial onsets, per-bin labels (``..._bin_(a-b)``), and the across-trial
        mean (``..._mean``). Per-trial and per-bin columns are concatenated across events (each labeled
        by its event); each event's mean becomes one column of the mean_* metrics.
        """
        window_start, window_stop = self._peak_windows()
        window_count = window_start.shape[0]

        peak_positive_blocks: list[np.ndarray] = []
        peak_negative_blocks: list[np.ndarray] = []
        area_blocks: list[np.ndarray] = []
        trial_onset_times: list[float] = []
        trial_event_names: list[str] = []
        mean_peak_positive_columns: list[np.ndarray] = []
        mean_peak_negative_columns: list[np.ndarray] = []
        mean_area_columns: list[np.ndarray] = []
        summary_event_names: list[str] = []
        bin_edges_blocks: list[np.ndarray] = []
        binned_peak_positive_blocks: list[np.ndarray] = []
        binned_peak_negative_blocks: list[np.ndarray] = []
        binned_area_blocks: list[np.ndarray] = []
        bin_event_names: list[str] = []

        for entry in entries:
            event_name = entry["event"]
            dataframe = pandas.read_hdf(entry["path"])

            trial_rows, bin_rows, mean_row = self._partition_peak_auc_index(dataframe.index)

            def matrix(metric_prefix: str, rows: list[str]) -> np.ndarray:
                return np.array(
                    [
                        [float(dataframe.loc[row, f"{metric_prefix}_{window + 1}"]) for row in rows]
                        for window in range(window_count)
                    ],
                    dtype=np.float64,
                )

            trial_row_names = [row for _, row in trial_rows]
            peak_positive_blocks.append(matrix("peak_pos", trial_row_names))
            peak_negative_blocks.append(matrix("peak_neg", trial_row_names))
            area_blocks.append(matrix("area", trial_row_names))
            trial_onset_times.extend(onset for onset, _ in trial_rows)
            trial_event_names.extend([event_name] * len(trial_rows))

            mean_peak_positive_columns.append(matrix("peak_pos", [mean_row]).reshape(-1))
            mean_peak_negative_columns.append(matrix("peak_neg", [mean_row]).reshape(-1))
            mean_area_columns.append(matrix("area", [mean_row]).reshape(-1))
            summary_event_names.append(event_name)

            if bin_rows:
                bin_row_names = [row for _, _, row in bin_rows]
                bin_edges_blocks.append(np.array([[start, stop] for start, stop, _ in bin_rows], dtype=np.float64))
                binned_peak_positive_blocks.append(matrix("peak_pos", bin_row_names))
                binned_peak_negative_blocks.append(matrix("peak_neg", bin_row_names))
                binned_area_blocks.append(matrix("area", bin_row_names))
                bin_event_names.extend([event_name] * len(bin_rows))

        kwargs = dict(
            name=peak_auc_metadata["name"],
            trace_type=peak_auc_metadata["trace_type"],
            unit="a.u.",
            region=region_reference([peak_auc_metadata["region"]]),
            event=event_reference(trial_event_names),
            summary_event=event_reference(summary_event_names, name="summary_event"),
            window_start=window_start,
            window_stop=window_stop,
            trial_onset_times=np.array(trial_onset_times, dtype=np.float64),
            peak_positive=np.concatenate(peak_positive_blocks, axis=1),
            peak_negative=np.concatenate(peak_negative_blocks, axis=1),
            area_under_curve=np.concatenate(area_blocks, axis=1),
            mean_peak_positive=np.stack(mean_peak_positive_columns, axis=1),
            mean_peak_negative=np.stack(mean_peak_negative_columns, axis=1),
            mean_area_under_curve=np.stack(mean_area_columns, axis=1),
        )
        if bin_edges_blocks:
            kwargs.update(
                bin_edges=np.concatenate(bin_edges_blocks, axis=0),
                bin_edges__bin_basis=bin_basis,
                bin_event=event_reference(bin_event_names, name="bin_event"),
                binned_peak_positive=np.concatenate(binned_peak_positive_blocks, axis=1),
                binned_peak_negative=np.concatenate(binned_peak_negative_blocks, axis=1),
                binned_area_under_curve=np.concatenate(binned_area_blocks, axis=1),
            )
        return ndx_guppy.GuppyPeakAUC(**kwargs)
