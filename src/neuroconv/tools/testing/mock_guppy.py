"""Generate a tiny, schema-faithful GuPPy output folder for testing.

GuPPy (Guided Photometry Analysis in Python) writes a ``<session>_output_<N>`` folder full of
derived fiber-photometry products. The real folders are ~100 MB because every condition file
carries a long time/lag/sample axis. None of that bulk is needed to exercise ``GuppyInterface``'s
parsing and writing logic, so this module reproduces the *format* of each file GuPPy emits (with
tiny arrays) without any dependency on GuPPy itself.

Each private writer reproduces a documented on-disk format -- its filename pattern plus the HDF5
dataset keys / DataFrame columns / dtypes that ``GuppyInterface`` reads -- described in its own
docstring, with no dependency on GuPPy's internals. These layouts were captured from real GuPPy
output.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas

# Default topology mirrors the ``Photo_249_391-200721-120136_stubbed`` TDT tank: two regions, three
# behavioral events, two transient features, one cross-correlation pair. The store names
# (Dv1A/Dv2A/Dv3B/Dv4B) and event epocs (LNRW/LNnR/PrtR) are the ones that tank actually exposes, so
# ``TDTFiberPhotometryGuppyConverter`` can be driven against it with these defaults unchanged.
_DEFAULT_REGION_TO_STORES = {
    "dms": {"signal": "Dv2A", "control": "Dv1A"},
    "dls": {"signal": "Dv4B", "control": "Dv3B"},
}
_DEFAULT_EVENT_STORE_TO_NAME = {
    "LNRW": "rewarded_nose_pokes",
    "LNnR": "unrewarded_nose_pokes",
    "PrtR": "port_entries",
}
_SESSION_ID = "mock_guppy_session"


def generate_mock_guppy_output_folder(
    folder_path: str | Path,
    *,
    region_to_stores: dict[str, dict[str, str]] | None = None,
    event_store_to_name: dict[str, str] | None = None,
    features: tuple[str, ...] = ("z_score", "dff"),
    trace_prefixes: tuple[str, ...] = ("cntrl_sig_fit", "dff", "z_score"),
    cross_correlation_pairs: tuple[tuple[str, str], ...] = (("dls", "dms"),),
    session_start_time: datetime = datetime(2018, 10, 30, 15, 33, 54, tzinfo=timezone.utc),
    sampling_rate: float = 200.0,
    num_samples: int = 400,
    num_psth_timepoints: int = 50,
    num_trials: int = 4,
    peak_start_points: tuple[float, ...] = (-5.0, 0.0, 5.0),
    peak_end_points: tuple[float, ...] = (0.0, 3.0, 10.0),
    bin_size_in_trials: int = 3,
    guppy_version: str = "2.0.0a7",
    zscore_method: str = "standard z-score",
) -> Path:
    """Write a tiny GuPPy ``<session>_output`` folder to ``folder_path`` and return it.

    The generated folder is a faithful (but ~kilobyte-scale) replica of a real GuPPy output: the
    filenames, HDF5 keys, DataFrame columns/index labels, and dtypes match what ``GuppyInterface``
    reads. All arrays are internally consistent -- trace length equals timestamp length, transient
    peaks fall inside the trace window, and every event file for one condition shares an identical
    x-axis -- so the interface's ``*_matches_source`` assertions hold by construction.

    Parameters
    ----------
    folder_path : str or Path
        Directory to create and populate (created if missing).
    region_to_stores : dict, optional
        ``{region: {"signal": <store>, "control": <store>}}``. Defaults to the two-region
        ``dms``/``dls`` topology with the acquisition store names of the reference fixture. Override
        the store names to match a real TDT tank (for the converter test).
    event_store_to_name : dict, optional
        ``{acquisition_store: event_name}`` for the behavioral events. Defaults to the three
        ``LNRW``/``LNnR``/``PrtR`` epocs the Photo_249 tank exposes.
    features : tuple of str, optional
        Transient/PSTH/cross-correlation features to emit (``z_score``, ``dff``).
    trace_prefixes : tuple of str, optional
        Derived continuous trace prefixes to emit.
    cross_correlation_pairs : tuple of (str, str), optional
        ``(reference_region, target_region)`` pairs to emit cross-correlations for.
    session_start_time : datetime, optional
        Written into ``timeCorrection_<region>.hdf5`` as ``timeRecStart``; drives
        ``get_metadata()["NWBFile"]["session_start_time"]``.
    sampling_rate, num_samples : float, int, optional
        Shape of the derived traces and their timestamps. ``num_samples / sampling_rate`` must
        exceed ~1 s so the first timestamp is > 0.5 s and the 1-s stub window is non-empty.
    num_psth_timepoints, num_trials : int, optional
        Shape of the PSTH / cross-correlation matrices.
    peak_start_points, peak_end_points : tuple of float, optional
        Peak/AUC analysis windows; also written to the parameters file (NaN-padded like GuPPy).
    bin_size_in_trials : int, optional
        Trials per bin for the ``bin_(a-b)`` columns ("# of trials" binning mode).
    guppy_version, zscore_method : str, optional
        Provenance values written to ``GuPPyParamtersUsed.json``.

    Returns
    -------
    Path
        The populated ``folder_path``.
    """
    folder_path = Path(folder_path)
    folder_path.mkdir(parents=True, exist_ok=True)

    region_to_stores = region_to_stores if region_to_stores is not None else _DEFAULT_REGION_TO_STORES
    event_store_to_name = event_store_to_name if event_store_to_name is not None else _DEFAULT_EVENT_STORE_TO_NAME
    regions = list(region_to_stores)
    event_names = list(event_store_to_name.values())

    # Trace timebase: start ~1 s in (the lights-on delay) so the first timestamp is > 0.5 s.
    timestamps = 1.0 + np.arange(num_samples, dtype=np.float64) / sampling_rate
    # Trial onset times labeling the PSTH/peak-AUC trial columns (distinct floats).
    trial_onsets = [10.0 * (index + 1) for index in range(num_trials)]
    bin_edges = _trial_bin_edges(num_trials=num_trials, bin_size_in_trials=bin_size_in_trials)
    peri_event_time = np.linspace(-5.0, 10.0, num_psth_timepoints)
    lag_axis = np.linspace(-5.0, 5.0, num_psth_timepoints)

    _write_stores_list(folder_path, region_to_stores=region_to_stores, event_store_to_name=event_store_to_name)
    _write_parameters(
        folder_path,
        guppy_version=guppy_version,
        zscore_method=zscore_method,
        peak_start_points=peak_start_points,
        peak_end_points=peak_end_points,
        bin_size_in_trials=bin_size_in_trials,
    )

    for region in regions:
        _write_time_correction(
            folder_path,
            region=region,
            timestamps=timestamps,
            sampling_rate=sampling_rate,
            session_start_time=session_start_time,
        )
        for prefix in trace_prefixes:
            _write_trace(folder_path, prefix=prefix, region=region, num_samples=num_samples)
        for feature in features:
            _write_transients_occurrences(folder_path, feature=feature, region=region)
            _write_freq_and_amp(folder_path, feature=feature, region=region)

    for event_name in event_names:
        for region in regions:
            for feature in features:
                for baseline_corrected in (True, False):
                    _write_psth(
                        folder_path,
                        event=event_name,
                        region=region,
                        feature=feature,
                        baseline_corrected=baseline_corrected,
                        peri_event_time=peri_event_time,
                        trial_onsets=trial_onsets,
                        bin_edges=bin_edges,
                    )
                _write_peak_auc(
                    folder_path,
                    event=event_name,
                    region=region,
                    feature=feature,
                    trial_onsets=trial_onsets,
                    bin_edges=bin_edges,
                    num_windows=len(peak_start_points),
                )

    cross_correlation_folder = folder_path / "cross_correlation_output"
    cross_correlation_folder.mkdir(exist_ok=True)
    for event_name in event_names:
        for feature in features:
            for region_1, region_2 in cross_correlation_pairs:
                _write_cross_correlation(
                    cross_correlation_folder,
                    event=event_name,
                    feature=feature,
                    region_1=region_1,
                    region_2=region_2,
                    lag_axis=lag_axis,
                    trial_onsets=trial_onsets,
                    bin_edges=bin_edges,
                )

    return folder_path


def _trial_bin_edges(num_trials: int, bin_size_in_trials: int) -> list[tuple[int, int]]:
    """Consecutive ``(start, stop)`` trial-index bins, as GuPPy uses in "# of trials" mode."""
    edges = []
    start = 0
    while start < num_trials:
        edges.append((start, min(start + bin_size_in_trials, num_trials)))
        start += bin_size_in_trials
    return edges


def _write_stores_list(folder_path, region_to_stores, event_store_to_name) -> None:
    """Two-row ``storesList.csv`` (row 0 = acquisition store names, row 1 = GuPPy semantic names).

    Written via ``np.savetxt(..., delimiter=",", fmt="%s")``.
    """
    store_names, semantic_names = [], []
    for region, stores in region_to_stores.items():
        store_names.append(stores["control"])
        semantic_names.append(f"control_{region}")
        store_names.append(stores["signal"])
        semantic_names.append(f"signal_{region}")
    for store, event_name in event_store_to_name.items():
        store_names.append(store)
        semantic_names.append(event_name)
    rows = np.asarray([store_names, semantic_names], dtype=str)
    np.savetxt(folder_path / "storesList.csv", rows, delimiter=",", fmt="%s")


def _write_parameters(
    folder_path, guppy_version, zscore_method, peak_start_points, peak_end_points, bin_size_in_trials
) -> None:
    """``GuPPyParamtersUsed.json`` written via ``json.dump``.

    ``peak_startPoint``/``peak_endPoint`` are padded to length 10 with NaN exactly as GuPPy does;
    ``GuppyInterface`` strips the NaN padding back to the real windows.
    """
    pad_length = 10
    start_padded = list(peak_start_points) + [float("nan")] * (pad_length - len(peak_start_points))
    end_padded = list(peak_end_points) + [float("nan")] * (pad_length - len(peak_end_points))
    parameters = dict(
        guppy_version=guppy_version,
        isosbestic_control=True,
        filter_window=100.0,
        removeArtifacts=False,
        artifactsRemovalMethod="concatenate",
        zscore_method=zscore_method,
        baselineWindowStart=0.0,
        baselineWindowEnd=180.0,
        nSecPrev=-5.0,
        nSecPost=10.0,
        timeInterval=1.0,
        bin_psth_trials=bin_size_in_trials,
        use_time_or_trials="# of trials",
        baselineCorrectionStart=-5.0,
        baselineCorrectionEnd=0.0,
        peak_startPoint=start_padded,
        peak_endPoint=end_padded,
        moving_window=15.0,
        highAmpFilt=2.0,
        transientsThresh=2.0,
    )
    with open(folder_path / "GuPPyParamtersUsed.json", "w", encoding="utf-8") as parameters_file:
        json.dump(parameters, parameters_file, indent=4)


def _write_trace(folder_path, prefix, region, num_samples) -> None:
    """``<prefix>_<region>.hdf5`` with a single 1-D float64 dataset under key ``data``."""
    data = np.linspace(-1.0, 1.0, num_samples, dtype=np.float64)
    with h5py.File(folder_path / f"{prefix}_{region}.hdf5", "w") as trace_file:
        trace_file.create_dataset("data", data=data, maxshape=(None,), chunks=True)


def _write_time_correction(folder_path, region, timestamps, sampling_rate, session_start_time) -> None:
    """``timeCorrection_<region>.hdf5`` with four keyed datasets: ``timeRecStart``, ``timestampNew``,
    ``sampling_rate``, ``correctionIndex``.
    """
    time_rec_start = np.asarray([session_start_time.timestamp()], dtype=np.float64)
    correction_index = np.arange(timestamps.shape[0], dtype=np.int64)
    with h5py.File(folder_path / f"timeCorrection_{region}.hdf5", "w") as time_correction_file:
        time_correction_file.create_dataset("timeRecStart", data=time_rec_start)
        time_correction_file.create_dataset("timestampNew", data=timestamps, maxshape=(None,), chunks=True)
        time_correction_file.create_dataset("sampling_rate", data=np.asarray([sampling_rate], dtype=np.float32))
        time_correction_file.create_dataset("correctionIndex", data=correction_index, maxshape=(None,), chunks=True)


def _write_transients_occurrences(folder_path, feature, region) -> None:
    """``transientsOccurrences_<feature>_<region>.csv`` with columns ``timestamps``, ``amplitude``.

    Written as a DataFrame via ``to_csv`` (leading integer index column). The peaks sit inside the
    trace window; a couple fall beyond the 1-s stub window on purpose.
    """
    peaks = np.array([[1.2, 0.9], [1.5, 1.4], [1.8, 0.7], [2.5, 1.1]], dtype=np.float64)
    dataframe = pandas.DataFrame(peaks, index=np.arange(peaks.shape[0]), columns=["timestamps", "amplitude"])
    dataframe.to_csv(folder_path / f"transientsOccurrences_{feature}_{region}.csv")


def _write_freq_and_amp(folder_path, feature, region) -> None:
    """``freqAndAmp_<feature>_<region>.h5`` -- one row, columns ``freq (events/min)``, ``amplitude``.

    Written as a DataFrame via ``to_hdf(key="df")``.
    """
    dataframe = pandas.DataFrame([[28.7, 2.18]], index=[_SESSION_ID], columns=["freq (events/min)", "amplitude"])
    dataframe.to_hdf(folder_path / f"freqAndAmp_{feature}_{region}.h5", key="df", mode="w")


def _event_matrix_dataframe(axis, trial_onsets, bin_edges) -> pandas.DataFrame:
    """Build the shared PSTH / cross-correlation DataFrame layout.

    Columns: one float-named column per trial onset, then ``bin_(a-b)``/``bin_err_(a-b)`` pairs,
    then ``timestamps``, ``mean``, ``err`` -- all float32.
    """
    num_points = axis.shape[0]
    data = {}
    trial_columns = np.linspace(-0.5, 0.5, num_points, dtype=np.float32)
    for index, onset in enumerate(trial_onsets):
        data[repr(float(onset))] = trial_columns + 0.01 * index
    for start, stop in bin_edges:
        data[f"bin_({start}-{stop})"] = np.full(num_points, 0.1 * (start + 1), dtype=np.float32)
        data[f"bin_err_({start}-{stop})"] = np.full(num_points, 0.01, dtype=np.float32)
    data["timestamps"] = axis.astype(np.float32)
    data["mean"] = trial_columns
    data["err"] = np.full(num_points, 0.05, dtype=np.float32)
    return pandas.DataFrame(data)


def _write_psth(
    folder_path, event, region, feature, baseline_corrected, peri_event_time, trial_onsets, bin_edges
) -> None:
    """PSTH ``.h5`` -- ``<event>_<region>_<feature>_<region>.h5`` (+ ``baselineUncorrected`` variant).

    Written as a DataFrame via ``to_hdf(key="df")``.
    """
    suffix = "" if baseline_corrected else "baselineUncorrected_"
    filename = f"{event}_{region}_{suffix}{feature}_{region}.h5"
    dataframe = _event_matrix_dataframe(peri_event_time, trial_onsets, bin_edges)
    dataframe.to_hdf(folder_path / filename, key="df", mode="w")


def _write_cross_correlation(
    folder_path, event, feature, region_1, region_2, lag_axis, trial_onsets, bin_edges
) -> None:
    """Cross-correlation ``.h5`` -- ``corr_<event>_<feature>_<region_1>_<region_2>.h5``.

    Written as a DataFrame via ``to_hdf(key="df")``.
    """
    filename = f"corr_{event}_{feature}_{region_1}_{region_2}.h5"
    dataframe = _event_matrix_dataframe(lag_axis, trial_onsets, bin_edges)
    dataframe.to_hdf(folder_path / filename, key="df", mode="w")


def _write_peak_auc(folder_path, event, region, feature, trial_onsets, bin_edges, num_windows) -> None:
    """Peak/AUC ``.h5`` -- ``peak_AUC_<event>_<region>_<feature>_<region>.h5``.

    Columns are ``peak_pos_<w>``/``peak_neg_<w>``/``area_<w>`` per window; index rows are
    ``<session>_<onset>`` per trial, ``<session>_bin_(a-b)``, and ``<session>_mean``. Written as a
    DataFrame via ``to_hdf(key="df")``.
    """
    columns = []
    for window in range(1, num_windows + 1):
        columns.extend([f"peak_pos_{window}", f"peak_neg_{window}", f"area_{window}"])

    index = [f"{_SESSION_ID}_{repr(float(onset))}" for onset in trial_onsets]
    index += [f"{_SESSION_ID}_bin_({start}-{stop})" for start, stop in bin_edges]
    index += [f"{_SESSION_ID}_mean"]

    values = np.arange(len(index) * len(columns), dtype=np.float64).reshape(len(index), len(columns))
    dataframe = pandas.DataFrame(values, index=index, columns=columns)
    dataframe.to_hdf(folder_path / f"peak_AUC_{event}_{region}_{feature}_{region}.h5", key="df", mode="w")
