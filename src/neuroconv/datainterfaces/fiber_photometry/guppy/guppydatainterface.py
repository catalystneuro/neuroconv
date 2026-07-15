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
from neuroconv.datainterfaces.events.baseeventsinterface import _to_table_object_name
from neuroconv.tools import get_package
from neuroconv.tools.fiber_photometry import get_fiber_photometry_table
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
# GuPPy derived-trace prefix -> unit (deterministic from the output, not user-editable).
_PREFIX_TO_UNIT = dict(cntrl_sig_fit="n.a.", dff="a.u.", z_score="a.u.")
# Per-window peak/area metric row prefixes in the peak_AUC_*.h5 DataFrame index.
_BIN_COLUMN_PATTERN = re.compile(r"bin_\((\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\)$")


class GuppyInterface(BaseTemporalAlignmentInterface):
    """
    Data Interface for converting GuPPy (Guided Photometry Analysis in Python) processed outputs.

    This interface writes the derived products that GuPPy computes as dedicated ``ndx-guppy`` neurodata types:

    * control-fit / ΔF/F / z-score traces
    * transient peaks and their per-(recording_site, trace_type) summary
    * peri-event PSTHs
    * peak / AUC summaries
    * recording-site-pair cross-correlations

    plus the GuPPy parameters (``GuppyParameters``) and two registry tables (``GuppyRecordingSitesTable``,
    ``GuppyEventsTable``) that give each recording_site and event a single structured identity referenced by
    every product.

    The derived traces are ``GuppyDerivedResponseSeries`` (a ``FiberPhotometryResponseSeries`` subtype),
    so they carry the acquisition device/fiber/indicator provenance via ``fiber_photometry_table_region``.
    That link is the type's defining provenance, so this interface does **not stand alone**: its
    :meth:`add_to_nwbfile` requires the acquisition's ``FiberPhotometryTable`` to already be present and a
    ``recording_site_to_fiber_photometry_table_rows`` map (recording_site -> table row indices) supplied by a converter
    that pairs GuPPy with an acquisition interface (see ``TDTFiberPhotometryGuppyConverter``).

    The ``EventsTable`` reference on ``GuppyEventsTable`` is the one optional outward link -- populated
    when the behavioral events live in the NWBFile's ``events`` group (as ``pynwb.event.EventsTable``
    objects), omitted otherwise.

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
        metadata_key: str = "Guppy",
        verbose: bool = False,
    ):
        """Initialize the GuppyInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the GuPPy output folder (the ``<session>_output_<N>`` directory containing
            ``storesList.csv``, the per-recording_site derived ``.hdf5`` files, and the
            ``GuPPyParamtersUsed.json`` provenance file). GuPPy always writes
            ``GuPPyParamtersUsed.json`` into this folder, so it is discovered automatically; if
            it is missing the folder is not a valid GuPPy output and construction fails.
        metadata_key : str, optional
            Key under ``metadata["FiberPhotometry"]`` that scopes everything this interface writes,
            so two GuPPy interfaces in one conversion do not collide. Default = "Guppy".
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        self.metadata_key = metadata_key
        super().__init__(
            folder_path=folder_path,
            verbose=verbose,
        )

        folder_path = Path(folder_path)
        stores_list_path = folder_path / "storesList.csv"
        assert (
            stores_list_path.is_file()
        ), f"storesList.csv not found in {folder_path}; this does not look like a GuPPy output folder."

        recording_sites = self._discover_recording_sites(stores_list_path)
        assert len(recording_sites) > 0, (
            f"No recording_sites discovered in {stores_list_path}. Expected store labels matching "
            f"'signal_<R>' (with optional matching 'control_<R>')."
        )
        recording_site_to_store_ids = self._discover_recording_site_to_store_ids(stores_list_path)
        event_store_to_event_name = self._discover_event_store_to_event_name(stores_list_path)
        event_names = sorted(set(event_store_to_event_name.values()))

        traces_by_recording_site = {
            recording_site: [
                prefix
                for prefix in self._DERIVED_TRACE_PREFIXES
                if (folder_path / f"{prefix}_{recording_site}.hdf5").is_file()
            ]
            for recording_site in recording_sites
        }
        transients_by_recording_site = {
            recording_site: [
                feature
                for feature in self._TRANSIENT_FEATURES
                if (folder_path / f"transientsOccurrences_{feature}_{recording_site}.csv").is_file()
            ]
            for recording_site in recording_sites
        }

        parameters_file_path = folder_path / "GuPPyParamtersUsed.json"
        assert (
            parameters_file_path.is_file()
        ), f"GuPPyParamtersUsed.json not found in {folder_path}; this does not look like a GuPPy output folder."
        with open(parameters_file_path, "r", encoding="utf-8") as parameters_file:
            guppy_parameters = json.load(parameters_file)

        cross_correlations = self._discover_cross_correlations(folder_path=folder_path, recording_sites=recording_sites)
        psths = self._discover_psths(folder_path=folder_path, event_names=event_names, recording_sites=recording_sites)
        peak_aucs = self._discover_peak_aucs(
            folder_path=folder_path, event_names=event_names, recording_sites=recording_sites
        )
        valid_signal_intervals_by_recording_site = self._discover_valid_signal_intervals(
            folder_path=folder_path, recording_sites=recording_sites
        )
        remove_artifacts_flag = guppy_parameters.get("removeArtifacts")
        if remove_artifacts_flag is True and not valid_signal_intervals_by_recording_site:
            warnings.warn(
                "GuPPy parameters specify removeArtifacts=True but no coordsForPreProcessing_<recording_site>.npy "
                "files were found; valid_signal_intervals will not be written.",
                UserWarning,
            )
        elif remove_artifacts_flag is False and valid_signal_intervals_by_recording_site:
            warnings.warn(
                "GuPPy parameters specify removeArtifacts=False but coordsForPreProcessing_<recording_site>.npy "
                "files were found; valid_signal_intervals will be written from the .npy files.",
                UserWarning,
            )

        self._folder_path = folder_path
        self._recording_sites = recording_sites
        self._recording_site_to_store_ids = recording_site_to_store_ids
        self._event_store_to_event_name = event_store_to_event_name
        self._event_names = event_names
        self._traces_by_recording_site = traces_by_recording_site
        self._transients_by_recording_site = transients_by_recording_site
        self._cross_correlations = cross_correlations
        self._psths = psths
        self._peak_aucs = peak_aucs
        self._valid_signal_intervals_by_recording_site = valid_signal_intervals_by_recording_site
        self._guppy_parameters = guppy_parameters
        self._recording_site_to_aligned_timestamps: dict[str, np.ndarray] | None = None

    @staticmethod
    def _discover_recording_sites(stores_list_path: Path) -> list[str]:
        rows = stores_list_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(rows) >= 2, f"storesList.csv at {stores_list_path} must have at least two rows."
        store_labels = [name.strip() for name in rows[1].split(",")]
        return [name[len("signal_") :] for name in store_labels if name.startswith("signal_")]

    @staticmethod
    def _discover_recording_site_to_store_ids(stores_list_path: Path) -> dict[str, dict[str, str]]:
        """Return ``{recording_site: {"signal": <store>, "control": <store>}}`` from ``storesList.csv``.

        Row 0 of ``storesList.csv`` holds the acquisition store ids (e.g. ``Dv2A``) and row 1 holds
        the matching GuPPy store labels (e.g. ``signal_dms``). This mapping is the join key a
        converter uses to link GuPPy recording_sites to acquisition fiber-photometry table rows. Only the
        ``signal_<recording_site>`` and ``control_<recording_site>`` stores participate; behavioral stores
        (``port_entries``, nose pokes, ...) are ignored.
        """
        rows = stores_list_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(rows) >= 2, f"storesList.csv at {stores_list_path} must have at least two rows."
        store_ids = [name.strip() for name in rows[0].split(",")]
        store_labels = [name.strip() for name in rows[1].split(",")]
        assert len(store_ids) == len(store_labels), (
            f"storesList.csv at {stores_list_path} has mismatched row lengths: "
            f"{len(store_ids)} store ids vs {len(store_labels)} store labels."
        )
        recording_site_to_store_ids: dict[str, dict[str, str]] = {}
        for store_id, store_label in zip(store_ids, store_labels):
            for kind in ("signal", "control"):
                prefix = f"{kind}_"
                if store_label.startswith(prefix):
                    recording_site = store_label[len(prefix) :]
                    recording_site_to_store_ids.setdefault(recording_site, {})[kind] = store_id
        return recording_site_to_store_ids

    @staticmethod
    def _discover_event_store_to_event_name(stores_list_path: Path) -> dict[str, str]:
        """Return ``{store_id: event_name}`` for the behavioral event stores in ``storesList.csv``.

        Row 0 of ``storesList.csv`` holds the acquisition store ids (e.g. ``PrtN``) and row 1 the
        matching GuPPy store labels (e.g. ``port_entries``). The ``signal_<recording_site>`` and
        ``control_<recording_site>`` stores are the fiber photometry channels; every *other* store in the
        list is a behavioral event GuPPy processed (e.g. ``PrtN`` -> ``port_entries``,
        ``LNRW`` -> ``rewarded_nose_pokes``). Stores present in the TDT tank but absent from
        ``storesList.csv`` were not used by GuPPy and are excluded.
        """
        rows = stores_list_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(rows) >= 2, f"storesList.csv at {stores_list_path} must have at least two rows."
        store_ids = [name.strip() for name in rows[0].split(",")]
        store_labels = [name.strip() for name in rows[1].split(",")]
        assert len(store_ids) == len(store_labels), (
            f"storesList.csv at {stores_list_path} has mismatched row lengths: "
            f"{len(store_ids)} store ids vs {len(store_labels)} store labels."
        )
        event_store_to_event_name: dict[str, str] = {}
        for store_id, store_label in zip(store_ids, store_labels):
            if store_label.startswith("signal_") or store_label.startswith("control_"):
                continue
            event_store_to_event_name[store_id] = store_label
        return event_store_to_event_name

    @classmethod
    def _discover_cross_correlations(cls, folder_path: Path, recording_sites: list[str]) -> list[dict]:
        cross_correlation_folder = folder_path / "cross_correlation_output"
        if not cross_correlation_folder.is_dir():
            return []

        entries = []
        for cross_correlation_path in sorted(cross_correlation_folder.glob("corr_*.h5")):
            stem = cross_correlation_path.stem
            assert stem.startswith("corr_"), f"Unexpected cross-correlation filename: {cross_correlation_path.name}."
            remainder = stem[len("corr_") :]

            recording_site_2 = next(
                (recording_site for recording_site in recording_sites if remainder.endswith(f"_{recording_site}")), None
            )
            assert recording_site_2 is not None, (
                f"Could not parse target recording_site from {cross_correlation_path.name}; "
                f"expected suffix '_<recording_site>' with recording_site in {recording_sites}."
            )
            remainder = remainder[: -len(f"_{recording_site_2}")]

            recording_site_1 = next(
                (recording_site for recording_site in recording_sites if remainder.endswith(f"_{recording_site}")), None
            )
            assert recording_site_1 is not None, (
                f"Could not parse reference recording_site from {cross_correlation_path.name}; "
                f"expected suffix '_<recording_site>' with recording_site in {recording_sites}."
            )
            remainder = remainder[: -len(f"_{recording_site_1}")]

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
                    recording_site_1=recording_site_1,
                    recording_site_2=recording_site_2,
                )
            )
        return entries

    @classmethod
    def _discover_psths(cls, folder_path: Path, event_names: list[str], recording_sites: list[str]) -> list[dict]:
        """Discover GuPPy peri-event PSTH files for each (event, recording_site, feature).

        GuPPy names PSTH files ``<event>_<recording_site>_<feature>_<recording_site>.h5`` (baseline-corrected) and
        ``<event>_<recording_site>_baselineUncorrected_<feature>_<recording_site>.h5`` (uncorrected). Expected names
        are constructed from the discovered events/recording_sites/features and checked on disk, which avoids
        fragile filename parsing (event and recording_site names both contain underscores).
        """
        entries = []
        for event in event_names:
            for recording_site in recording_sites:
                for feature in cls._TRANSIENT_FEATURES:
                    corrected = folder_path / f"{event}_{recording_site}_{feature}_{recording_site}.h5"
                    if corrected.is_file():
                        entries.append(
                            dict(
                                path=corrected,
                                event=event,
                                recording_site=recording_site,
                                feature=feature,
                                baseline_corrected=True,
                            )
                        )
                    uncorrected = (
                        folder_path / f"{event}_{recording_site}_baselineUncorrected_{feature}_{recording_site}.h5"
                    )
                    if uncorrected.is_file():
                        entries.append(
                            dict(
                                path=uncorrected,
                                event=event,
                                recording_site=recording_site,
                                feature=feature,
                                baseline_corrected=False,
                            )
                        )
        return entries

    @classmethod
    def _discover_peak_aucs(cls, folder_path: Path, event_names: list[str], recording_sites: list[str]) -> list[dict]:
        """Discover GuPPy peak/AUC files (``peak_AUC_<event>_<recording_site>_<feature>_<recording_site>.h5``)."""
        entries = []
        for event in event_names:
            for recording_site in recording_sites:
                for feature in cls._TRANSIENT_FEATURES:
                    path = folder_path / f"peak_AUC_{event}_{recording_site}_{feature}_{recording_site}.h5"
                    if path.is_file():
                        entries.append(dict(path=path, event=event, recording_site=recording_site, feature=feature))
        return entries

    @classmethod
    def _discover_valid_signal_intervals(cls, folder_path: Path, recording_sites: list[str]) -> dict[str, np.ndarray]:
        """Return ``{recording_site: intervals_array}`` for each recording_site with a coords file.

        ``intervals_array`` has shape ``(N, 2)`` with columns
        ``[start_in_seconds, stop_in_seconds]``. These are the intervals that GuPPy
        kept (not the artifacts), per the format in
        ``coordsForPreProcessing_<recording_site>.npy``.
        """
        result = {}
        for recording_site in recording_sites:
            path = folder_path / f"coordsForPreProcessing_{recording_site}.npy"
            if not path.is_file():
                continue
            coords = np.load(path)
            time_values = coords[:, 0]
            assert (
                time_values.shape[0] % 2 == 0
            ), f"Expected even number of coordinates in {path}, got {time_values.shape[0]}."
            result[recording_site] = time_values.reshape(-1, 2)
        return result

    def _read_time_correction(self, recording_site: str) -> dict:
        time_correction_path = self._folder_path / f"timeCorrection_{recording_site}.hdf5"
        assert time_correction_path.is_file(), f"Missing {time_correction_path} for recording_site '{recording_site}'."
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
        use_time_or_trials = self._guppy_parameters.get("use_time_or_trials")
        if isinstance(use_time_or_trials, str) and use_time_or_trials.strip().lower().startswith("time"):
            return "time"
        return "trials"

    def _guppy_parameters_kwargs(self) -> dict:
        """Map ``GuPPyParamtersUsed.json`` keys onto ``GuppyParameters`` constructor kwargs."""
        parameters = self._guppy_parameters
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
        start_points = np.asarray(self._guppy_parameters.get("peak_startPoint"), dtype=np.float64)
        end_points = np.asarray(self._guppy_parameters.get("peak_endPoint"), dtype=np.float64)
        valid = ~np.isnan(start_points)
        return start_points[valid], end_points[valid]

    # ------------------------------------------------------------------ #
    # Object-name / metadata-key builders (single source of truth shared by get_metadata and
    # add_to_nwbfile, so the producer and consumer can never drift into a KeyError).
    # ------------------------------------------------------------------ #
    @staticmethod
    def _trace_name(recording_site: str, prefix: str) -> str:
        return f"{prefix}_{recording_site}"

    @staticmethod
    def _transients_name(recording_site: str, feature: str) -> str:
        return f"transients_{recording_site}_{feature}"

    @staticmethod
    def _cross_correlation_name(feature: str, recording_site_1: str, recording_site_2: str) -> str:
        return f"cross_correlation_{feature}_{recording_site_1}_{recording_site_2}"

    @staticmethod
    def _psth_name(recording_site: str, feature: str, baseline_corrected: bool) -> str:
        suffix = "" if baseline_corrected else "_baseline_uncorrected"
        return f"psth_{recording_site}_{feature}{suffix}"

    @staticmethod
    def _peak_auc_name(recording_site: str, feature: str) -> str:
        return f"peak_auc_{recording_site}_{feature}"

    def get_metadata(self) -> DeepDict:
        """Return metadata pre-populated from the GuPPy outputs and parameters file."""
        metadata = super().get_metadata()

        first_recording_site = self._recording_sites[0]
        time_correction = self._read_time_correction(first_recording_site)
        if time_correction["time_rec_start"] is not None:
            session_start_datetime = datetime.fromtimestamp(time_correction["time_rec_start"], tz=timezone.utc)
            metadata["NWBFile"]["session_start_time"] = session_start_datetime

        guppy_parameters = self._guppy_parameters

        # Every product GuPPy emits is enumerated here so get_metadata is a full manifest of what the
        # file will contain. Each family is a dict keyed by the object's derived default name (the
        # "tag"); the value carries the editable presentation fields -- ``name`` (defaults to the tag,
        # a stable handle add_to_nwbfile recomputes) and a generic ``description``. Descriptions omit
        # processing parameters, which live once in the GuppyParameters lab metadata. Internal join
        # keys (recording_site, trace_basename, trace_type, recording-site pair, baseline flag, event lists) and units
        # are NOT stored here -- editing them would break the join or contradict the data, so
        # add_to_nwbfile derives them from self._* instead.
        prefix_to_description_template = dict(
            cntrl_sig_fit="GuPPy fitted control trace for recording_site '{recording_site}'.",
            dff="GuPPy ΔF/F trace for recording_site '{recording_site}'.",
            z_score="GuPPy z-scored trace for recording_site '{recording_site}'.",
        )
        traces_metadata = {}
        for recording_site in self._recording_sites:
            for prefix in self._traces_by_recording_site[recording_site]:
                name = self._trace_name(recording_site, prefix)
                traces_metadata[name] = dict(
                    name=name, description=prefix_to_description_template[prefix].format(recording_site=recording_site)
                )

        transients_metadata = {}
        for recording_site in self._recording_sites:
            for feature in self._transients_by_recording_site[recording_site]:
                name = self._transients_name(recording_site, feature)
                transients_metadata[name] = dict(
                    name=name,
                    description=f"GuPPy-detected transient peaks in the '{feature}' trace for recording_site '{recording_site}'.",
                )

        cross_correlations_metadata = {}
        for feature, recording_site_1, recording_site_2 in self._group_by_condition(
            self._cross_correlations, ("feature", "recording_site_1", "recording_site_2")
        ):
            name = self._cross_correlation_name(feature, recording_site_1, recording_site_2)
            cross_correlations_metadata[name] = dict(
                name=name,
                description=(
                    f"GuPPy peri-event cross-correlation of the '{feature}' trace between recording_sites "
                    f"'{recording_site_1}' and '{recording_site_2}'."
                ),
            )

        psths_metadata = {}
        for recording_site, feature, baseline_corrected in self._group_by_condition(
            self._psths, ("recording_site", "feature", "baseline_corrected")
        ):
            name = self._psth_name(recording_site, feature, baseline_corrected)
            baseline = "baseline-corrected" if baseline_corrected else "baseline-uncorrected"
            psths_metadata[name] = dict(
                name=name,
                description=f"GuPPy peri-event PSTH of the '{feature}' trace for recording_site '{recording_site}' ({baseline}).",
            )

        peak_aucs_metadata = {}
        for recording_site, feature in self._group_by_condition(self._peak_aucs, ("recording_site", "feature")):
            name = self._peak_auc_name(recording_site, feature)
            peak_aucs_metadata[name] = dict(
                name=name,
                description=f"GuPPy peak/area summary of the '{feature}' PSTH for recording_site '{recording_site}'.",
            )

        guppy_version = guppy_parameters.get("guppy_version")
        processing_module_description = "GuPPy-derived fiber photometry processing outputs."
        if guppy_version is not None:
            processing_module_description = (
                f"GuPPy-derived fiber photometry processing outputs (GuPPy version {guppy_version})."
            )

        metadata["FiberPhotometry"][self.metadata_key] = dict(
            ProcessingModule=dict(
                name="fiber_photometry",
                description=processing_module_description,
            ),
            Traces=traces_metadata,
            Transients=transients_metadata,
            TransientSummary=dict(
                name="transient_summary",
                description=(
                    "Per-(recording_site, trace_type) GuPPy transient summary: events/min and mean peak amplitude."
                ),
            ),
            CrossCorrelations=cross_correlations_metadata,
            PSTHs=psths_metadata,
            PeakAUCs=peak_aucs_metadata,
        )
        return metadata

    def get_metadata_schema(self) -> dict:
        """Return the metadata schema for this interface."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"].setdefault("FiberPhotometry", get_base_schema(tag="FiberPhotometry"))

        # Every product family is a keyed collection: an object whose keys are the derived object names
        # mapping to a ``{name, description}`` value schema (additionalProperties), not a positional
        # array. name/description are the editable presentation surface; units and all internal join
        # keys are derived at write time and never appear here. The two singular objects
        # (ProcessingModule, TransientSummary) are plain ``{name, description}`` objects.
        named_object = dict(
            type="object",
            required=["name", "description"],
            properties=dict(name=dict(type="string"), description=dict(type="string")),
        )
        named_collection = dict(type="object", additionalProperties=named_object)

        metadata_schema["properties"]["FiberPhotometry"]["properties"][self.metadata_key] = dict(
            type="object",
            additionalProperties=False,
            # The data-dependent families are empty ({}) for sessions that lack those products, which
            # validates fine, so only the always-present keys are required.
            required=[
                "ProcessingModule",
                "Traces",
                "TransientSummary",
            ],
            properties=dict(
                ProcessingModule=named_object,
                Traces=named_collection,
                Transients=named_collection,
                TransientSummary=named_object,
                CrossCorrelations=named_collection,
                PSTHs=named_collection,
                PeakAUCs=named_collection,
            ),
        )
        return metadata_schema

    def get_original_timestamps(self) -> dict[str, np.ndarray]:
        """Return the original (GuPPy-corrected) timestamps for each recording_site."""
        return {
            recording_site: self._read_time_correction(recording_site)["timestamps"]
            for recording_site in self._recording_sites
        }

    def get_timestamps(self) -> dict[str, np.ndarray]:
        """Return the (possibly aligned) timestamps for each recording_site."""
        if self._recording_site_to_aligned_timestamps is not None:
            return self._recording_site_to_aligned_timestamps
        return self.get_original_timestamps()

    def set_aligned_timestamps(self, recording_site_to_aligned_timestamps: dict[str, np.ndarray]) -> None:
        """Override the per-recording_site timestamps with externally-aligned arrays."""
        self._recording_site_to_aligned_timestamps = recording_site_to_aligned_timestamps

    def set_aligned_starting_time(self, aligned_starting_time: float) -> None:
        """Shift every recording_site's timestamps by ``aligned_starting_time``."""
        recording_site_to_timestamps = self.get_timestamps()
        self.set_aligned_timestamps(
            {
                recording_site: timestamps + aligned_starting_time
                for recording_site, timestamps in recording_site_to_timestamps.items()
            }
        )

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *,
        recording_site_to_fiber_photometry_table_rows: dict[str, list[int]],
        stub_test: bool = False,
    ) -> None:
        """
        Add GuPPy-derived fiber photometry products to an NWBFile as ndx-guppy neurodata types.

        Builds the ``GuppyParameters`` lab metadata, the ``GuppyRecordingSitesTable`` and ``GuppyEventsTable``
        registries, and the per-product objects (traces, transients, summary, cross-correlation, PSTH,
        peak/AUC, valid intervals), each referencing its registry rows. Products are written on the
        timestamps GuPPy emits, or on the externally-aligned timestamps provided via
        :meth:`set_aligned_timestamps` / :meth:`set_aligned_starting_time`.

        This interface does **not stand alone**: the acquisition ``FiberPhotometryTable`` must already be
        present in ``nwbfile`` and ``recording_site_to_fiber_photometry_table_rows`` is required (the derived
        traces are ``FiberPhotometryResponseSeries`` whose ``fiber_photometry_table_region`` link is their
        defining provenance). Both are supplied by a converter that owns the acquisition side (see
        ``TDTFiberPhotometryGuppyConverter``).

        Parameters
        ----------
        nwbfile : NWBFile
            The in-memory NWBFile to add the data to. Must already contain the acquisition
            ``FiberPhotometryTable`` (as a ``FiberPhotometry`` lab_meta_data object).
        metadata : dict
            Metadata dictionary; must contain ``metadata["FiberPhotometry"][self.metadata_key]``.
        recording_site_to_fiber_photometry_table_rows : dict[str, list[int]]
            Mapping from GuPPy recording_site label (e.g. ``"dms"``) to the acquisition
            ``FiberPhotometryTable`` row indices that recording_site's derived traces were computed from
            (typically the excitation signal and isosbestic control rows).
        stub_test : bool, optional
            If True, only a short slice of each large product is written. Default = False.
        """
        ndx_guppy = get_package(package_name="ndx_guppy", installation_instructions="pip install ndx-guppy")

        fiber_photometry_table = get_fiber_photometry_table(nwbfile)
        assert fiber_photometry_table is not None, (
            "No FiberPhotometryTable found in the NWBFile. GuppyInterface does not stand alone; the "
            "acquisition interface must add the fiber photometry table before GuPPy runs (drive both "
            "through a converter, e.g. TDTFiberPhotometryGuppyConverter)."
        )
        guppy_metadata = metadata["FiberPhotometry"][self.metadata_key]
        processing_module_metadata = guppy_metadata["ProcessingModule"]
        processing_module = get_module(
            nwbfile=nwbfile,
            name=processing_module_metadata["name"],
            description=processing_module_metadata["description"],
        )

        recording_site_to_original_timestamps = self.get_original_timestamps()
        recording_site_to_timestamps = self.get_timestamps()
        recording_site_to_stub_end_time: dict[str, float] = {}
        bin_basis = self._bin_basis()

        # Session-wide typed parameters.
        self._add_guppy_parameters_to_nwbfile(ndx_guppy=ndx_guppy, nwbfile=nwbfile)

        # Registries: recording_site and event identity, referenced by every product.
        recording_sites_table = self._add_guppy_recording_sites_table_to_nwbfile(
            ndx_guppy=ndx_guppy,
            processing_module=processing_module,
            fiber_photometry_table=fiber_photometry_table,
            recording_site_to_fiber_photometry_table_rows=recording_site_to_fiber_photometry_table_rows,
            recording_site_to_original_timestamps=recording_site_to_original_timestamps,
            recording_site_to_timestamps=recording_site_to_timestamps,
        )
        events_table = self._add_guppy_events_table_to_nwbfile(
            ndx_guppy=ndx_guppy, processing_module=processing_module, nwbfile=nwbfile
        )
        # Derived continuous traces.
        self._add_guppy_derived_response_series_to_nwbfile(
            ndx_guppy=ndx_guppy,
            processing_module=processing_module,
            traces_metadata=guppy_metadata["Traces"],
            fiber_photometry_table=fiber_photometry_table,
            recording_site_to_fiber_photometry_table_rows=recording_site_to_fiber_photometry_table_rows,
            recording_site_to_timestamps=recording_site_to_timestamps,
            recording_sites_table=recording_sites_table,
            recording_site_to_stub_end_time=recording_site_to_stub_end_time,
            stub_test=stub_test,
        )

        # Per-(recording_site, trace_type) transient peak tables.
        self._add_guppy_transients_tables_to_nwbfile(
            ndx_guppy=ndx_guppy,
            processing_module=processing_module,
            transients_metadata=guppy_metadata["Transients"],
            recording_sites_table=recording_sites_table,
            recording_site_to_original_timestamps=recording_site_to_original_timestamps,
            recording_site_to_timestamps=recording_site_to_timestamps,
            recording_site_to_stub_end_time=recording_site_to_stub_end_time,
            stub_test=stub_test,
        )

        # Single per-session transient summary table.
        self._add_guppy_transient_summary_table_to_nwbfile(
            ndx_guppy=ndx_guppy,
            processing_module=processing_module,
            recording_sites_table=recording_sites_table,
            summary_metadata=guppy_metadata["TransientSummary"],
        )

        # Cross-correlations: one GuppyCrossCorrelation per (trace_type, recording-site-pair) condition.
        self._add_guppy_cross_correlations_to_nwbfile(
            ndx_guppy=ndx_guppy,
            processing_module=processing_module,
            cross_correlations_metadata=guppy_metadata["CrossCorrelations"],
            recording_sites_table=recording_sites_table,
            events_table=events_table,
            bin_basis=bin_basis,
            stub_test=stub_test,
        )

        # Peri-event PSTHs: one GuppyPSTH per (recording_site, trace_type, baseline) condition.
        self._add_guppy_psths_to_nwbfile(
            ndx_guppy=ndx_guppy,
            processing_module=processing_module,
            psths_metadata=guppy_metadata["PSTHs"],
            recording_sites_table=recording_sites_table,
            events_table=events_table,
            bin_basis=bin_basis,
            stub_test=stub_test,
        )

        # Peak/AUC summaries: one GuppyPeakAUC per (recording_site, trace_type) condition.
        self._add_guppy_peak_aucs_to_nwbfile(
            ndx_guppy=ndx_guppy,
            processing_module=processing_module,
            peak_aucs_metadata=guppy_metadata["PeakAUCs"],
            recording_sites_table=recording_sites_table,
            events_table=events_table,
            bin_basis=bin_basis,
        )

    def _recording_site_reference(self, recording_sites_table, recording_site_names: list[str]) -> DynamicTableRegion:
        """Build a DynamicTableRegion into the GuppyRecordingSitesTable for the given recording_site name(s)."""
        recording_site_to_row_index = {
            recording_site: index for index, recording_site in enumerate(self._recording_sites)
        }
        return DynamicTableRegion(
            name="recording_site",
            data=[recording_site_to_row_index[recording_site] for recording_site in recording_site_names],
            description="GuPPy recording_site(s) this object was computed from.",
            table=recording_sites_table,
        )

    def _event_reference(self, events_table, event_names: list[str], name: str = "event") -> DynamicTableRegion:
        """Build a DynamicTableRegion into the GuppyEventsTable for the given event name(s)."""
        event_to_row_index = {event_name: index for index, event_name in enumerate(self._event_names)}
        return DynamicTableRegion(
            name=name,
            data=[event_to_row_index[event_name] for event_name in event_names],
            description="GuPPy behavioral event(s) this object's columns were aligned to.",
            table=events_table,
        )

    def _add_guppy_parameters_to_nwbfile(self, *, ndx_guppy, nwbfile: NWBFile) -> None:
        """Add the session-wide typed GuppyParameters lab metadata."""
        nwbfile.add_lab_meta_data(ndx_guppy.GuppyParameters(**self._guppy_parameters_kwargs()))

    def _add_guppy_derived_response_series_to_nwbfile(
        self,
        *,
        ndx_guppy,
        processing_module,
        traces_metadata: dict,
        fiber_photometry_table,
        recording_site_to_fiber_photometry_table_rows: dict,
        recording_site_to_timestamps: dict,
        recording_sites_table,
        recording_site_to_stub_end_time: dict,
        stub_test: bool,
    ) -> None:
        """Add each derived continuous trace as a GuppyDerivedResponseSeries.

        The source ``.hdf5`` basename, trace_type, and unit are derived from the interface's discovered
        state; the editable name/description come from ``traces_metadata`` (keyed by the trace's derived
        default name). Under ``stub_test`` each trace is truncated to its first ~1 s and the truncated
        end time is recorded in ``recording_site_to_stub_end_time`` so the transient tables can be clipped to
        match.
        """
        for recording_site in self._recording_sites:
            for prefix in self._traces_by_recording_site[recording_site]:
                trace_basename = self._trace_name(recording_site, prefix)
                entry = traces_metadata[trace_basename]
                trace_name = entry["name"]
                with h5py.File(self._folder_path / f"{trace_basename}.hdf5", "r") as f:
                    data = f["data"][:]
                timestamps = recording_site_to_timestamps[recording_site]
                if stub_test:
                    stub_sample_count = int(np.searchsorted(timestamps, timestamps[0] + 1.0, side="right"))
                    stub_sample_count = max(1, min(stub_sample_count, data.shape[0]))
                    data = data[:stub_sample_count]
                    timestamps = timestamps[:stub_sample_count]
                    recording_site_to_stub_end_time[recording_site] = float(timestamps[-1])

                assert recording_site in recording_site_to_fiber_photometry_table_rows, (
                    f"No recording_site_to_fiber_photometry_table_rows supplied for recording_site '{recording_site}' (trace "
                    f"'{trace_name}'). GuppyInterface does not stand alone; drive it through a converter "
                    f"(e.g. TDTFiberPhotometryGuppyConverter)."
                )
                # A fresh DynamicTableRegion per trace: one recording_site cannot be parented to multiple series.
                fiber_photometry_table_region = fiber_photometry_table.create_fiber_photometry_table_region(
                    description=(
                        f"Acquisition fiber-photometry table rows (excitation signal and isosbestic "
                        f"control) that GuPPy trace '{trace_name}' was computed from."
                    ),
                    region=recording_site_to_fiber_photometry_table_rows[recording_site],
                )
                response_series = ndx_guppy.GuppyDerivedResponseSeries(
                    name=trace_name,
                    description=entry["description"],
                    data=data,
                    unit=_PREFIX_TO_UNIT[prefix],
                    timestamps=timestamps,
                    trace_type=_PREFIX_TO_TRACE_TYPE[prefix],
                    recording_site=self._recording_site_reference(recording_sites_table, [recording_site]),
                    fiber_photometry_table_region=fiber_photometry_table_region,
                )
                processing_module.add(response_series)

    def _add_guppy_transients_tables_to_nwbfile(
        self,
        *,
        ndx_guppy,
        processing_module,
        transients_metadata: dict,
        recording_sites_table,
        recording_site_to_original_timestamps: dict,
        recording_site_to_timestamps: dict,
        recording_site_to_stub_end_time: dict,
        stub_test: bool,
    ) -> None:
        """Add one GuppyTransientsTable per (recording_site, trace_type) of detected transient peaks.

        Recording site and trace_type (which is also the ``transientsOccurrences_*`` file key) are derived from
        the interface's discovered state; the editable name/description come from ``transients_metadata``
        (keyed by the table's derived default name).
        """
        recording_site_to_row_index = {
            recording_site: index for index, recording_site in enumerate(self._recording_sites)
        }
        for recording_site in self._recording_sites:
            for feature in self._transients_by_recording_site[recording_site]:
                entry = transients_metadata[self._transients_name(recording_site, feature)]
                trace_type = feature
                occurrences = pandas.read_csv(
                    self._folder_path / f"transientsOccurrences_{trace_type}_{recording_site}.csv"
                )
                peak_timestamps = occurrences["timestamps"].to_numpy(dtype=float)
                peak_amplitudes = occurrences["amplitude"].to_numpy(dtype=float)
                # Peaks are in GuPPy's emitted timebase; map them onto the (possibly aligned) timestamps.
                peak_timestamps = np.interp(
                    peak_timestamps,
                    recording_site_to_original_timestamps[recording_site],
                    recording_site_to_timestamps[recording_site],
                )
                if stub_test:
                    stub_end_time = recording_site_to_stub_end_time.get(recording_site)
                    if stub_end_time is not None:
                        keep_mask = peak_timestamps <= stub_end_time
                        peak_timestamps = peak_timestamps[keep_mask]
                        peak_amplitudes = peak_amplitudes[keep_mask]

                transients_table = ndx_guppy.GuppyTransientsTable(
                    name=entry["name"],
                    description=entry["description"],
                    trace_type=trace_type,
                    unit="a.u.",
                    columns=[
                        DynamicTableRegion(
                            name="recording_site",
                            data=[recording_site_to_row_index[recording_site]] * len(peak_timestamps),
                            description=f"GuPPy recording_site '{recording_site}'.",
                            table=recording_sites_table,
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

    def _add_guppy_cross_correlations_to_nwbfile(
        self,
        *,
        ndx_guppy,
        processing_module,
        cross_correlations_metadata: dict,
        recording_sites_table,
        events_table,
        bin_basis: str,
        stub_test: bool,
    ) -> None:
        """Add one GuppyCrossCorrelation per (trace_type, recording-site-pair) condition, concatenating every
        event's trials/bins along the trials/bin axes.

        Condition keys (trace_type, recording-site pair) are derived from the interface's discovered state; the
        editable name/description come from ``cross_correlations_metadata`` (keyed by the derived name).
        """
        cross_correlation_groups = self._group_by_condition(
            self._cross_correlations, ("feature", "recording_site_1", "recording_site_2")
        )
        for (feature, recording_site_1, recording_site_2), entries in cross_correlation_groups.items():
            entry = cross_correlations_metadata[
                self._cross_correlation_name(feature, recording_site_1, recording_site_2)
            ]
            concatenated = self._concatenate_event_matrices(entries, stub_test=stub_test)
            cross_correlation_kwargs = dict(
                name=entry["name"],
                description=entry["description"],
                trace_type=feature,
                unit="a.u.",
                recording_site=self._recording_site_reference(
                    recording_sites_table, [recording_site_1, recording_site_2]
                ),
                event=self._event_reference(events_table, concatenated["trial_event_names"]),
                summary_event=self._event_reference(
                    events_table, concatenated["summary_event_names"], name="summary_event"
                ),
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
                    bin_event=self._event_reference(events_table, concatenated["bin_event_names"], name="bin_event"),
                    binned_mean=concatenated["binned_value"],
                    binned_error=concatenated["binned_error"],
                )
            processing_module.add(ndx_guppy.GuppyCrossCorrelation(**cross_correlation_kwargs))

    def _add_guppy_psths_to_nwbfile(
        self,
        *,
        ndx_guppy,
        processing_module,
        psths_metadata: dict,
        recording_sites_table,
        events_table,
        bin_basis: str,
        stub_test: bool,
    ) -> None:
        """Add one GuppyPSTH per (recording_site, trace_type, baseline) condition, concatenating every event's
        trials/bins along the trials/bin axes.

        Condition keys (recording_site, trace_type, baseline flag) are derived from the interface's discovered
        state; the editable name/description come from ``psths_metadata`` (keyed by the derived name).
        """
        psth_groups = self._group_by_condition(self._psths, ("recording_site", "feature", "baseline_corrected"))
        for (recording_site, feature, baseline_corrected), entries in psth_groups.items():
            entry = psths_metadata[self._psth_name(recording_site, feature, baseline_corrected)]
            concatenated = self._concatenate_event_matrices(entries, stub_test=stub_test)
            psth_kwargs = dict(
                name=entry["name"],
                description=entry["description"],
                trace_type=feature,
                baseline_corrected=bool(baseline_corrected),
                unit="a.u.",
                recording_site=self._recording_site_reference(recording_sites_table, [recording_site]),
                event=self._event_reference(events_table, concatenated["trial_event_names"]),
                summary_event=self._event_reference(
                    events_table, concatenated["summary_event_names"], name="summary_event"
                ),
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
                    bin_event=self._event_reference(events_table, concatenated["bin_event_names"], name="bin_event"),
                    binned_mean=concatenated["binned_value"],
                    binned_error=concatenated["binned_error"],
                )
            processing_module.add(ndx_guppy.GuppyPSTH(**psth_kwargs))

    def _add_guppy_peak_aucs_to_nwbfile(
        self,
        *,
        ndx_guppy,
        processing_module,
        peak_aucs_metadata: dict,
        recording_sites_table,
        events_table,
        bin_basis: str,
    ) -> None:
        """Add one GuppyPeakAUC per (recording_site, trace_type) condition, concatenated across events.

        Condition keys (recording_site, trace_type) are derived from the interface's discovered state; the
        editable name/description come from ``peak_aucs_metadata`` (keyed by the derived name).
        """
        peak_auc_groups = self._group_by_condition(self._peak_aucs, ("recording_site", "feature"))
        for (recording_site, feature), entries in peak_auc_groups.items():
            entry = peak_aucs_metadata[self._peak_auc_name(recording_site, feature)]
            peak_auc = self._build_peak_auc(
                ndx_guppy=ndx_guppy,
                entries=entries,
                name=entry["name"],
                description=entry["description"],
                recording_site=recording_site,
                trace_type=feature,
                events_table=events_table,
                recording_sites_table=recording_sites_table,
                bin_basis=bin_basis,
            )
            processing_module.add(peak_auc)

    def _add_guppy_recording_sites_table_to_nwbfile(
        self,
        *,
        ndx_guppy,
        processing_module,
        fiber_photometry_table,
        recording_site_to_fiber_photometry_table_rows: dict,
        recording_site_to_original_timestamps: dict,
        recording_site_to_timestamps: dict,
    ):
        """Build and add the GuppyRecordingSitesTable, linking each recording_site to its fiber photometry rows.

        Valid-signal (artifact-free) intervals are a per-recording_site fact, carried here as an
        obs_intervals-style ragged column: each recording_site's ``[start, stop]`` windows are shifted from
        GuPPy's emitted recording timebase onto the (possibly aligned) timestamps by the same scalar
        offset applied to that recording_site's timestamps (they are boundary values, not per-sample timestamps
        to interpolate against). When any recording_site has intervals the column is written for every row
        (empty entry for recording_sites without); when none do, the column is omitted entirely.
        """
        valid_signal_intervals_by_recording_site: dict[str, list[list[float]]] = {}
        if self._valid_signal_intervals_by_recording_site:
            for recording_site in self._recording_sites:
                intervals = self._valid_signal_intervals_by_recording_site.get(recording_site)
                if intervals is None:
                    valid_signal_intervals_by_recording_site[recording_site] = []
                    continue
                time_offset = float(recording_site_to_timestamps[recording_site][0]) - float(
                    recording_site_to_original_timestamps[recording_site][0]
                )
                valid_signal_intervals_by_recording_site[recording_site] = (intervals + time_offset).tolist()

        recording_sites_table = ndx_guppy.GuppyRecordingSitesTable(
            name="recording_sites",
            description="GuPPy recording sites (one row per recording site). Each row's optional fiber link points "
            "at the acquisition FiberPhotometryTable signal + isosbestic rows for that recording site.",
            target_tables={"fiber_photometry_table_region": fiber_photometry_table},
        )
        any_valid_signal_intervals = any(
            valid_signal_intervals_by_recording_site.get(recording_site) for recording_site in self._recording_sites
        )
        for recording_site in self._recording_sites:
            assert recording_site in recording_site_to_fiber_photometry_table_rows, (
                f"No recording_site_to_fiber_photometry_table_rows supplied for recording_site '{recording_site}'. GuppyInterface "
                f"does not stand alone; drive it through a converter (e.g. TDTFiberPhotometryGuppyConverter)."
            )
            row_kwargs = dict(
                recording_site=recording_site,
                store_id=self._recording_site_to_store_ids.get(recording_site, {}).get("signal"),
                store_label=f"signal_{recording_site}",
                fiber_photometry_table_region=list(recording_site_to_fiber_photometry_table_rows[recording_site]),
            )
            if any_valid_signal_intervals:
                row_kwargs["valid_signal_intervals"] = valid_signal_intervals_by_recording_site.get(recording_site, [])
            recording_sites_table.add_row(**row_kwargs)
        processing_module.add(recording_sites_table)
        return recording_sites_table

    @staticmethod
    def _resolve_events_table(nwbfile: NWBFile, event_name: str):
        """Return the pynwb EventsTable (in ``nwbfile.events``) holding this event's onsets, or None.

        The events writer names a solo (one-type) table by the CamelCased event name
        (``port_entries`` -> ``PortEntries``), so that is the primary lookup. If instead several
        event types were merged into one table, that table carries an ``event_type`` discriminator
        column; the fallback finds the table whose discriminator lists ``event_name``.
        """
        if nwbfile.events is None:
            return None
        table = nwbfile.events.get(_to_table_object_name(event_name))
        if table is not None:
            return table
        for events_table in nwbfile.events.values():
            if "event_type" in events_table.colnames and event_name in list(events_table["event_type"][:]):
                return events_table
        return None

    def _add_guppy_events_table_to_nwbfile(self, *, ndx_guppy, processing_module, nwbfile: NWBFile):
        """Build and add the GuppyEventsTable, optionally referencing the EventsTable objects that hold
        each event's onset timestamps.

        The behavioral events are written (by the events interface) as ``pynwb.event.EventsTable``
        objects in ``nwbfile.events``. When every GuPPy event resolves to such a table, each registry
        row references its table via the optional ``events`` column; otherwise (e.g. standalone GuPPy
        with no acquisition events) the column is omitted.
        """
        name_to_store = {event_name: store for store, event_name in self._event_store_to_event_name.items()}
        event_references = [self._resolve_events_table(nwbfile, event_name) for event_name in self._event_names]
        include_event_references = len(event_references) > 0 and all(
            reference is not None for reference in event_references
        )

        events_table = ndx_guppy.GuppyEventsTable(
            name="events",
            description="GuPPy behavioral events (one row per event GuPPy aligned to).",
        )
        for event_name in self._event_names:
            store = name_to_store[event_name]
            events_table.add_row(
                event_name=event_name,
                event_description=(
                    f"Behavioral event '{event_name}' that GuPPy aligned to (acquisition store '{store}')."
                ),
                store_id=store,
                store_label=event_name,
            )
        if include_event_references:
            events_table.add_column(
                name="events",
                description="Reference to the EventsTable (in nwbfile.events) holding this event's onset timestamps.",
                data=event_references,
            )
        processing_module.add(events_table)
        return events_table

    def _add_guppy_transient_summary_table_to_nwbfile(
        self, *, ndx_guppy, processing_module, recording_sites_table, summary_metadata: dict
    ):
        """Build and add the per-session GuppyTransientSummaryTable, if any freqAndAmp files exist."""
        recording_site_to_row_index = {
            recording_site: index for index, recording_site in enumerate(self._recording_sites)
        }
        summary_recording_site_indices: list[int] = []
        summary_trace_types: list[str] = []
        summary_frequencies: list[float] = []
        summary_amplitudes: list[float] = []
        for recording_site in self._recording_sites:
            for feature in self._transients_by_recording_site[recording_site]:
                freq_amp_path = self._folder_path / f"freqAndAmp_{feature}_{recording_site}.h5"
                if not freq_amp_path.is_file():
                    continue
                freq_amp_dataframe = pandas.read_hdf(freq_amp_path)
                summary_recording_site_indices.append(recording_site_to_row_index[recording_site])
                summary_trace_types.append(feature)
                summary_frequencies.append(float(freq_amp_dataframe["freq (events/min)"].iloc[0]))
                summary_amplitudes.append(float(freq_amp_dataframe["amplitude"].iloc[0]))

        if not summary_recording_site_indices:
            return

        transient_summary_table = ndx_guppy.GuppyTransientSummaryTable(
            name=summary_metadata["name"],
            description=summary_metadata["description"],
            columns=[
                DynamicTableRegion(
                    name="recording_site",
                    data=summary_recording_site_indices,
                    description="GuPPy recording_site for this summary row.",
                    table=recording_sites_table,
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
        e.g. ``("recording_site", "feature", "baseline_corrected")`` for PSTHs. Within each group the entries
        are ordered by their event's position in ``self._event_names`` so concatenation across events
        is deterministic.
        """
        event_order = {event_name: index for index, event_name in enumerate(self._event_names)}
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
        self,
        *,
        ndx_guppy,
        entries: list[dict],
        name: str,
        description: str,
        recording_site: str,
        trace_type: str,
        recording_sites_table,
        events_table,
        bin_basis: str,
    ):
        """Build a full-fidelity GuppyPeakAUC for one (recording_site, trace_type) condition, concatenated across events.

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
            name=name,
            description=description,
            trace_type=trace_type,
            unit="a.u.",
            recording_site=self._recording_site_reference(recording_sites_table, [recording_site]),
            event=self._event_reference(events_table, trial_event_names),
            summary_event=self._event_reference(events_table, summary_event_names, name="summary_event"),
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
                bin_event=self._event_reference(events_table, bin_event_names, name="bin_event"),
                binned_peak_positive=np.concatenate(binned_peak_positive_blocks, axis=1),
                binned_peak_negative=np.concatenate(binned_peak_negative_blocks, axis=1),
                binned_area_under_curve=np.concatenate(binned_area_blocks, axis=1),
            )
        return ndx_guppy.GuppyPeakAUC(**kwargs)
