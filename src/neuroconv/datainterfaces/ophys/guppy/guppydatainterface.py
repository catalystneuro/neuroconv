import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import h5py
import numpy as np
import pandas
from pydantic import DirectoryPath, FilePath, validate_call
from pynwb.base import TimeSeries
from pynwb.core import DynamicTable, VectorData
from pynwb.file import NWBFile

from neuroconv.basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils import DeepDict
from neuroconv.utils.json_schema import get_base_schema


class GuppyInterface(BaseTemporalAlignmentInterface):
    """
    Data Interface for converting GuPPy (Guided Photometry Analysis in Python) processed outputs.

    GuPPy is a processing tool, not an acquisition system. This interface writes only the
    derived products that GuPPy actually computes (control fit, ΔF/F, z-score, transients, and
    per-region freq/amplitude summary). The raw signal/control traces and TTL/behavioral
    events are out of scope and are owned by the acquisition and event interfaces respectively.

    All derived series are placed in a ``ProcessingModule`` (default name ``fiber_photometry``).
    Plain ``pynwb.base.TimeSeries`` and ``pynwb.core.DynamicTable`` objects are used so that no
    NWB extensions are required.
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
        parameters_file_path: FilePath | None = None,
        verbose: bool = False,
    ):
        """Initialize the GuppyInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the GuPPy output folder (the ``<session>_output_<N>`` directory containing
            ``storesList.csv`` and the per-region derived ``.hdf5`` files).
        parameters_file_path : FilePath, optional
            Path to the ``GuPPyParamtersUsed.json`` file produced by GuPPy. GuPPy does not save
            this file at a fixed location relative to ``folder_path``, so the path must be
            provided explicitly when you want the parameters captured. If omitted, the
            parameters are not loaded and trace/transient descriptions fall back to defaults.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            folder_path=folder_path,
            parameters_file_path=parameters_file_path,
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

        if parameters_file_path is not None:
            with open(parameters_file_path, "r") as parameters_file:
                guppy_parameters = json.load(parameters_file)
        else:
            guppy_parameters = {}

        cross_correlations = self._discover_cross_correlations(folder_path=folder_path, regions=regions)

        self.folder_path = folder_path
        self.parameters_file_path = Path(parameters_file_path) if parameters_file_path is not None else None
        self.regions = regions
        self.traces_by_region = traces_by_region
        self.transients_by_region = transients_by_region
        self.cross_correlations = cross_correlations
        self.guppy_parameters = guppy_parameters
        self._region_to_aligned_timestamps: dict[str, np.ndarray] | None = None
        self._region_to_aligned_starting_time_and_rate: dict[str, tuple[float, float]] | None = None

    @staticmethod
    def _discover_regions(stores_list_path: Path) -> list[str]:
        rows = stores_list_path.read_text().strip().splitlines()
        assert len(rows) >= 2, f"storesList.csv at {stores_list_path} must have at least two rows."
        semantic_names = [name.strip() for name in rows[1].split(",")]
        return [name[len("signal_") :] for name in semantic_names if name.startswith("signal_")]

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

        metadata["Ophys"]["Guppy"] = dict(
            ProcessingModule=dict(
                name="fiber_photometry",
                description="GuPPy-derived fiber photometry processing outputs.",
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

    def get_original_starting_time_and_rate(self) -> dict[str, tuple[float, float]]:
        """Return the original ``(starting_time, sampling_rate)`` for each region."""
        result = {}
        for region in self.regions:
            time_correction = self._read_time_correction(region)
            result[region] = (float(time_correction["timestamps"][0]), time_correction["sampling_rate"])
        return result

    def get_starting_time_and_rate(self) -> dict[str, tuple[float, float]]:
        """Return the (possibly aligned) ``(starting_time, sampling_rate)`` for each region."""
        if self._region_to_aligned_starting_time_and_rate is not None:
            return self._region_to_aligned_starting_time_and_rate
        return self.get_original_starting_time_and_rate()

    def set_aligned_starting_time_and_rate(
        self, region_to_aligned_starting_time_and_rate: dict[str, tuple[float, float]]
    ) -> None:
        """Override the per-region ``(starting_time, sampling_rate)`` with externally-aligned values."""
        self._region_to_aligned_starting_time_and_rate = region_to_aligned_starting_time_and_rate

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *,
        stub_test: bool = False,
        timing_source: Literal["original", "aligned_timestamps", "aligned_starting_time_and_rate"] = "original",
    ) -> None:
        """
        Add GuPPy-derived fiber photometry products to an NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            The in-memory NWBFile to add the data to.
        metadata : dict
            Metadata dictionary; must contain ``metadata["Ophys"]["Guppy"]``.
        stub_test : bool, optional
            If True, only the first ~1 second of each trace is written, and transient tables are
            filtered to peaks falling inside that window. Default = False.
        timing_source : {"original", "aligned_timestamps", "aligned_starting_time_and_rate"}, optional
            Source of timing information. ``"aligned_timestamps"`` uses any timestamps provided
            via :meth:`set_aligned_timestamps`; ``"aligned_starting_time_and_rate"`` uses
            ``(starting_time, rate)`` provided via :meth:`set_aligned_starting_time_and_rate`.
        """
        assert timing_source in ("original", "aligned_timestamps", "aligned_starting_time_and_rate"), (
            f"timing_source must be 'original', 'aligned_timestamps', or "
            f"'aligned_starting_time_and_rate'; got {timing_source!r}."
        )

        guppy_metadata = metadata["Ophys"]["Guppy"]
        processing_module_metadata = guppy_metadata["ProcessingModule"]
        processing_module = get_module(
            nwbfile=nwbfile,
            name=processing_module_metadata["name"],
            description=processing_module_metadata["description"],
        )

        original_starting_time_and_rate = self.get_original_starting_time_and_rate()
        # Cache per-region stub bounds so transient tables share the trace's stub window.
        region_to_stub_end_time: dict[str, float] = {}

        # Derived continuous traces
        for trace_metadata in guppy_metadata["Traces"]:
            region = trace_metadata["region"]
            trace_basename = trace_metadata["trace_basename"]
            trace_path = self.folder_path / f"{trace_basename}.hdf5"
            with h5py.File(trace_path, "r") as f:
                data = f["data"][:]

            original_starting_time, original_rate = original_starting_time_and_rate[region]
            if timing_source == "aligned_timestamps":
                timestamps = self.get_timestamps()[region]
                timing_kwargs = dict(timestamps=timestamps)
                rate = original_rate
            elif timing_source == "aligned_starting_time_and_rate":
                starting_time, rate = self.get_starting_time_and_rate()[region]
                timing_kwargs = dict(starting_time=starting_time, rate=rate)
            else:
                timing_kwargs = dict(starting_time=original_starting_time, rate=original_rate)
                rate = original_rate

            if stub_test:
                stub_sample_count = min(int(np.ceil(rate)), data.shape[0])
                data = data[:stub_sample_count]
                if "timestamps" in timing_kwargs:
                    stub_timestamps = timing_kwargs["timestamps"][:stub_sample_count]
                    timing_kwargs = dict(timestamps=stub_timestamps)
                    region_to_stub_end_time[region] = float(stub_timestamps[-1])
                else:
                    region_to_stub_end_time[region] = (
                        timing_kwargs["starting_time"] + (stub_sample_count - 1) / timing_kwargs["rate"]
                    )

            time_series = TimeSeries(
                name=trace_metadata["name"],
                description=trace_metadata["description"],
                data=data,
                unit=trace_metadata["unit"],
                **timing_kwargs,
            )
            processing_module.add(time_series)

        # Per-region, per-feature transient peak tables
        for transient_metadata in guppy_metadata["Transients"]:
            region = transient_metadata["region"]
            feature = transient_metadata["feature"]
            occurrences_path = self.folder_path / f"transientsOccurrences_{feature}_{region}.csv"
            occurrences = pandas.read_csv(occurrences_path)
            peak_timestamps = occurrences["timestamps"].to_numpy(dtype=float)
            peak_amplitudes = occurrences["amplitude"].to_numpy(dtype=float)

            if timing_source == "aligned_starting_time_and_rate":
                aligned_start, _ = self.get_starting_time_and_rate()[region]
                original_start, _ = original_starting_time_and_rate[region]
                peak_timestamps = peak_timestamps + (aligned_start - original_start)
            elif timing_source == "aligned_timestamps":
                original_timestamps = self.get_original_timestamps()[region]
                aligned_timestamps = self.get_timestamps()[region]
                peak_timestamps = np.interp(peak_timestamps, original_timestamps, aligned_timestamps)

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

            trial_columns = [
                column for column in cross_correlation_dataframe.columns if column not in ("timestamps", "mean", "err")
            ]
            columns = [
                VectorData(
                    name="lag_in_seconds",
                    description="Lag axis in seconds, symmetric around zero.",
                    data=cross_correlation_dataframe["timestamps"].to_numpy(dtype=np.float64),
                ),
                VectorData(
                    name="mean",
                    description="Across-trial mean cross-correlation at each lag.",
                    data=cross_correlation_dataframe["mean"].to_numpy(dtype=np.float64),
                ),
            ]
            for trial_column in trial_columns:
                onset_in_seconds = float(trial_column)
                columns.append(
                    VectorData(
                        name=f"trial_at_{onset_in_seconds:.6f}s",
                        description=(
                            f"Normalized cross-correlation aligned to event onset at {onset_in_seconds} s. "
                            f"Each value at lag L is correlate(region_1, region_2) at lag L, divided by the "
                            f"per-trial peak absolute value."
                        ),
                        data=cross_correlation_dataframe[trial_column].to_numpy(dtype=np.float64),
                    )
                )

            cross_correlation_table = DynamicTable(
                name=cross_correlation_metadata["name"],
                description=cross_correlation_metadata["description"],
                columns=columns,
            )
            processing_module.add(cross_correlation_table)
