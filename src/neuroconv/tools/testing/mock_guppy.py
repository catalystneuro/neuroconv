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
from collections.abc import Sequence
from pathlib import Path

import h5py
import numpy as np
import pandas

# Default topology mirrors the ``Photo_249_391-200721-120136_stubbed`` TDT tank: two recording_sites, three
# behavioral events, two transient features, one cross-correlation pair. The store ids
# (Dv1A/Dv2A/Dv3B/Dv4B) and event epocs (LNRW/LNnR/PrtR) are the ones that tank actually exposes, so
# ``GuppyConverter`` can be driven against it with these defaults unchanged.
_DEFAULT_RECORDING_SITE_TO_STORES = {
    "dms": {"signal": "Dv2A", "control": "Dv1A"},
    "dls": {"signal": "Dv4B", "control": "Dv3B"},
}
_DEFAULT_EVENT_STORE_TO_NAME = {
    "LNRW": "rewarded_nose_pokes",
    "LNnR": "unrewarded_nose_pokes",
    "PrtR": "port_entries",
}
_SESSION_ID = "mock_guppy_session"
# Detected transient times, shared by transientsOccurrences_* and the spontaneous-mode event trains.
# One behavioral covariate scored four times inside the default recording. The third bin holds no
# score, so the empty-bin case (NaN mean, count 0) is covered by the defaults.
_DEFAULT_COVARIATES = {"akinesia": ((1.1, 1.6, 1.7, 2.6), (2.0, 3.0, 4.0, 5.0))}
# Detected transient times shared by transientsOccurrences_* and the per-bin counts.
_TRANSIENT_PEAK_TIMES = (1.2, 1.5, 1.8, 2.5)
# Seconds of raw recording GuPPy's lights-on trim discards before analysis (its default).
_TIME_FOR_LIGHTS_TURN_ON = 1.0


def generate_mock_guppy_output_folder(
    folder_path: str | Path,
    *,
    recording_site_to_stores: dict[str, dict[str, str]] | None = None,
    event_store_to_name: dict[str, str] | None = None,
    features: tuple[str, ...] = ("z_score", "dff"),
    trace_prefixes: tuple[str, ...] = ("cntrl_sig_fit", "dff", "z_score"),
    cross_correlation_pairs: tuple[tuple[str, str], ...] = (("dls", "dms"),),
    sampling_rate: float = 200.0,
    num_samples: int = 400,
    num_psth_timepoints: int = 50,
    num_trials: int = 4,
    event_onsets: dict[str, Sequence[float]] | None = None,
    peak_start_points: tuple[float, ...] = (-5.0, 0.0, 5.0),
    peak_end_points: tuple[float, ...] = (0.0, 3.0, 10.0),
    valid_signal_intervals: tuple[tuple[float, float], ...] = ((1.25, 1.75), (2.0, 2.5)),
    bin_width: float | None = 0.5,
    covariates: dict[str, tuple[Sequence[float], Sequence[float]]] | None = None,
    tonic_epochs: tuple[tuple[str, float, float], ...] = (("baseline", 1.0, 2.0), ("post_injection", 2.0, 3.0)),
    bin_size_in_trials: int = 3,
    use_transients_as_events: bool = False,
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
    recording_site_to_stores : dict, optional
        ``{recording_site: {"signal": <store>, "control": <store>}}``. Defaults to the two-recording_site
        ``dms``/``dls`` topology with the acquisition store ids of the reference fixture. Override
        the store ids to match a real TDT tank (for the converter test).
    event_store_to_name : dict, optional
        ``{acquisition_store: event_name}`` for the behavioral events. Defaults to the three
        ``LNRW``/``LNnR``/``PrtR`` epocs the Photo_249 tank exposes.
    features : tuple of str, optional
        Transient/PSTH/cross-correlation features to emit (``z_score``, ``dff``).
    trace_prefixes : tuple of str, optional
        Derived continuous trace prefixes to emit.
    cross_correlation_pairs : tuple of (str, str), optional
        ``(reference_recording_site, target_recording_site)`` pairs to emit cross-correlations for.
    sampling_rate, num_samples : float, int, optional
        Shape of the derived traces and their timestamps, counted *after* the lights-on trim.
        ``num_samples / sampling_rate`` must exceed ~1 s so the first timestamp is > 0.5 s and the
        1-s stub window is non-empty.
    num_psth_timepoints, num_trials : int, optional
        Shape of the PSTH / cross-correlation matrices. ``num_trials`` builds the default onsets, so it
        is ignored for any event named in ``event_onsets``.
    event_onsets : dict of str to sequence of float, optional
        The onsets GuPPy analyzed, keyed by event name; one entry per event is required when given.
        These label the trial columns of every peri-event product and fill
        ``<event>_<recording_site>.hdf5``, so a caller pairing this folder with a real acquisition file
        must draw them from that file -- a converter matches them against the events table it builds.
        Defaults to ``num_trials`` evenly spaced onsets shared by every event.
    peak_start_points, peak_end_points : tuple of float, optional
        Peak/AUC analysis windows; also written to the parameters file (NaN-padded like GuPPy).
    valid_signal_intervals : tuple of (float, float), optional
        ``[start, stop]`` valid-signal (artifact-free) windows written to
        ``coordsForPreProcessing_<recording_site>.npy`` for every recording_site, and reflected by ``removeArtifacts``
        in the parameters file. Pass an empty tuple to emit no coords files (the no-artifact-removal
        case). The windows must fall inside the trace timebase.
    bin_width : float, optional
        Width (s) of the whole-session time bins, written to the parameters file and used for
        ``binned_metrics_<recording_site>.h5``. Pass ``None`` to emit no binned tables at all (the case
        where **Compute Binned Metrics?** was off), which also suppresses the covariate tables.
    covariates : dict of str to (sequence of float, sequence of float), optional
        Behavioral covariates as ``{name: (timestamps, values)}``, each written as an ordinary store and
        labeled ``covariate_<name>`` in ``storesList.csv``, plus its binned means and correlations.
        Defaults to one covariate scored at four times inside the recording, one of the bins holding no
        score. Pass an empty dict for a session carrying no covariate.
    tonic_epochs : tuple of (str, float, float), optional
        ``(label, start, end)`` tonic epoch windows written to ``tonic_epochs_<recording_site>.csv`` for
        every recording_site, with their per-epoch means in ``tonic_<recording_site>.h5``. Pass an empty
        tuple to emit neither file (the case where GuPPy's optional tonic analysis was not run). A window
        may run past the last sample, which is how GuPPy records an epoch ending at the nominal recording
        duration; it is clamped to the samples available when averaged.
    bin_size_in_trials : int, optional
        Trials per bin for the ``bin_(a-b)`` columns ("# of trials" binning mode).
    use_transients_as_events : bool, optional
        Whether to emit GuPPy's spontaneous mode, off by default as it is in GuPPy. When on, each
        recording site's own detected transients stand in for external TTLs: a
        ``transients_<feature>_<recording_site>.hdf5`` event train is written per (feature, recording
        site), holding a *subset* of that site's detected transients, since trial rejection drops some;
        the two recording sites keep different subsets, as two sites detecting their own transients
        would. Every peri-event product is then emitted for those events as well.
    guppy_version, zscore_method : str, optional
        Provenance values written to ``GuPPyParamtersUsed.json``.

    Returns
    -------
    Path
        The populated ``folder_path``.

    Notes
    -----
    The three timebase datasets in ``timeCorrection_<recording_site>.hdf5`` are all derived from one
    raw timestamp array, the way a real GuPPy output derives them: ``timeRecStart`` is the raw store's
    first timestamp, ``correctionIndex`` is the samples surviving the lights-on trim, and
    ``timestampNew`` is the raw timestamps at those indices. The mock's raw timebase is
    session-relative (it starts at ``0.0``), so ``timeRecStart`` is ``0.0`` -- matching what GuPPy
    writes whenever the acquisition's own timestamps are session-relative rather than absolute.
    """
    folder_path = Path(folder_path)
    folder_path.mkdir(parents=True, exist_ok=True)

    recording_site_to_stores = (
        recording_site_to_stores if recording_site_to_stores is not None else _DEFAULT_RECORDING_SITE_TO_STORES
    )
    event_store_to_name = event_store_to_name if event_store_to_name is not None else _DEFAULT_EVENT_STORE_TO_NAME
    covariates = covariates if covariates is not None else _DEFAULT_COVARIATES
    recording_sites = list(recording_site_to_stores)
    event_names = list(event_store_to_name.values())

    # Raw store timebase, session-relative and starting at 0.0. The lights-on trim drops its leading
    # second; ``num_samples`` counts what survives, so every downstream array keeps that length.
    num_trimmed_samples = int(np.ceil(_TIME_FOR_LIGHTS_TURN_ON * sampling_rate))
    raw_timestamps = np.arange(num_trimmed_samples + num_samples, dtype=np.float64) / sampling_rate
    correction_index = np.flatnonzero(raw_timestamps >= _TIME_FOR_LIGHTS_TURN_ON)
    timestamps = raw_timestamps[correction_index]
    # The onsets GuPPy analyzed for each event. These are the single source of truth: they label the
    # PSTH/peak-AUC/cross-correlation trial columns AND fill <event>_<recording_site>.hdf5, the way a
    # real GuPPy output derives both from one surviving-onset list. Callers pairing this mock with a
    # real acquisition file must pass onsets drawn from that file, or the converter will not be able to
    # match them against the events table it builds.
    if event_onsets is None:
        default_onsets = [10.0 * (index + 1) for index in range(num_trials)]
        event_name_to_onsets = {event_name: list(default_onsets) for event_name in event_names}
    else:
        missing = set(event_names) - set(event_onsets)
        assert not missing, f"event_onsets is missing an entry for {sorted(missing)}."
        event_name_to_onsets = {event_name: list(event_onsets[event_name]) for event_name in event_names}
    event_name_to_bin_edges = {
        event_name: _trial_bin_edges(num_trials=len(onsets), bin_size_in_trials=bin_size_in_trials)
        for event_name, onsets in event_name_to_onsets.items()
    }
    peri_event_time = np.linspace(-5.0, 10.0, num_psth_timepoints)
    lag_axis = np.linspace(-5.0, 5.0, num_psth_timepoints)

    _write_stores_list(
        folder_path,
        recording_site_to_stores=recording_site_to_stores,
        event_store_to_name=event_store_to_name,
        covariates=covariates,
    )
    for covariate_name, (covariate_timestamps, covariate_values) in covariates.items():
        _write_covariate_store(
            folder_path, covariate_name=covariate_name, timestamps=covariate_timestamps, values=covariate_values
        )
    _write_parameters(
        folder_path,
        guppy_version=guppy_version,
        zscore_method=zscore_method,
        peak_start_points=peak_start_points,
        peak_end_points=peak_end_points,
        bin_size_in_trials=bin_size_in_trials,
        remove_artifacts=bool(valid_signal_intervals),
        use_transients_as_events=use_transients_as_events,
        bin_width=bin_width,
    )

    for recording_site in recording_sites:
        _write_time_correction(
            folder_path,
            recording_site=recording_site,
            raw_timestamps=raw_timestamps,
            correction_index=correction_index,
            sampling_rate=sampling_rate,
        )
        if valid_signal_intervals:
            _write_valid_signal_intervals(folder_path, recording_site=recording_site, intervals=valid_signal_intervals)
        if tonic_epochs:
            _write_tonic_epochs(folder_path, recording_site=recording_site, tonic_epochs=tonic_epochs)
            _write_tonic_means(
                folder_path,
                recording_site=recording_site,
                tonic_epochs=tonic_epochs,
                timestamps=timestamps,
                trace=_trace_data(num_samples),
            )
        for prefix in trace_prefixes:
            _write_trace(folder_path, prefix=prefix, recording_site=recording_site, num_samples=num_samples)
        for feature in features:
            _write_transients_occurrences(folder_path, feature=feature, recording_site=recording_site)
            _write_freq_and_amp(folder_path, feature=feature, recording_site=recording_site)
        if bin_width is not None:
            bin_edges = _bin_edges(timestamps=timestamps, bin_width=bin_width)
            _write_binned_metrics(
                folder_path,
                recording_site=recording_site,
                bin_edges=bin_edges,
                timestamps=timestamps,
                trace=_trace_data(num_samples),
                features=features,
            )
            if covariates:
                _write_binned_covariates(
                    folder_path, recording_site=recording_site, bin_edges=bin_edges, covariates=covariates
                )
                _write_covariate_correlations(
                    folder_path, recording_site=recording_site, features=features, covariates=covariates
                )

    for event_name in event_names:
        trial_onsets = event_name_to_onsets[event_name]
        bin_edges = event_name_to_bin_edges[event_name]
        for recording_site in recording_sites:
            _write_event_onsets(folder_path, event=event_name, recording_site=recording_site, onsets=trial_onsets)
            for feature in features:
                for baseline_corrected in (True, False):
                    _write_psth(
                        folder_path,
                        event=event_name,
                        recording_site=recording_site,
                        feature=feature,
                        baseline_corrected=baseline_corrected,
                        peri_event_time=peri_event_time,
                        trial_onsets=trial_onsets,
                        bin_edges=bin_edges,
                    )
                _write_peak_auc(
                    folder_path,
                    event=event_name,
                    recording_site=recording_site,
                    feature=feature,
                    trial_onsets=trial_onsets,
                    bin_edges=bin_edges,
                    num_windows=len(peak_start_points),
                )

    if use_transients_as_events:
        # Each recording site stands its own detected transients in for the TTLs, keeping the subset that
        # survived trial rejection. The two sites keep different subsets, so a row mix-up cannot pass.
        for recording_site_index, recording_site in enumerate(recording_sites):
            kept_transients = list(_TRANSIENT_PEAK_TIMES[recording_site_index :: len(recording_sites)])
            transient_bin_edges = _trial_bin_edges(
                num_trials=len(kept_transients), bin_size_in_trials=bin_size_in_trials
            )
            for detected_feature in features:
                event_name = "transients_" + detected_feature
                _write_event_onsets(
                    folder_path, event=event_name, recording_site=recording_site, onsets=kept_transients
                )
                for feature in features:
                    for baseline_corrected in (True, False):
                        _write_psth(
                            folder_path,
                            event=event_name,
                            recording_site=recording_site,
                            feature=feature,
                            baseline_corrected=baseline_corrected,
                            peri_event_time=peri_event_time,
                            trial_onsets=kept_transients,
                            bin_edges=transient_bin_edges,
                        )
                    _write_peak_auc(
                        folder_path,
                        event=event_name,
                        recording_site=recording_site,
                        feature=feature,
                        trial_onsets=kept_transients,
                        bin_edges=transient_bin_edges,
                        num_windows=len(peak_start_points),
                    )

    cross_correlation_folder = folder_path / "cross_correlation_output"
    cross_correlation_folder.mkdir(exist_ok=True)
    for event_name in event_names:
        for feature in features:
            for recording_site_1, recording_site_2 in cross_correlation_pairs:
                _write_cross_correlation(
                    cross_correlation_folder,
                    event=event_name,
                    feature=feature,
                    recording_site_1=recording_site_1,
                    recording_site_2=recording_site_2,
                    lag_axis=lag_axis,
                    trial_onsets=event_name_to_onsets[event_name],
                    bin_edges=event_name_to_bin_edges[event_name],
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


def _write_stores_list(folder_path, recording_site_to_stores, event_store_to_name, covariates=None) -> None:
    """Two-row ``storesList.csv`` (row 0 = acquisition store ids, row 1 = GuPPy store labels).

    Written via ``np.savetxt(..., delimiter=",", fmt="%s")``. A behavioral covariate is listed like any
    other store, under the label ``covariate_<name>``; its store id is the name of the CSV it came in
    as, which is the covariate name.
    """
    store_ids, store_labels = [], []
    for recording_site, stores in recording_site_to_stores.items():
        store_ids.append(stores["control"])
        store_labels.append(f"control_{recording_site}")
        store_ids.append(stores["signal"])
        store_labels.append(f"signal_{recording_site}")
    for store, event_name in event_store_to_name.items():
        store_ids.append(store)
        store_labels.append(event_name)
    for covariate_name in covariates or {}:
        store_ids.append(covariate_name)
        store_labels.append("covariate_" + covariate_name)
    rows = np.asarray([store_ids, store_labels], dtype=str)
    np.savetxt(folder_path / "storesList.csv", rows, delimiter=",", fmt="%s")


def _write_valid_signal_intervals(folder_path, recording_site, intervals) -> None:
    """``coordsForPreProcessing_<recording_site>.npy`` -- the artifact-removal boundary coordinates.

    A 2-D float array whose column 0 is a flat, even-length sequence of interval boundaries
    ``[start, stop, start, stop, ...]`` (seconds). ``GuppyInterface`` reads column 0, checks it is
    even-length, and reshapes it to ``(num_intervals, 2)`` ``[start, stop]`` pairs. Column 1 mirrors
    the boundary amplitudes GuPPy stores alongside each coordinate (unread by the interface).
    """
    boundaries = np.asarray(intervals, dtype=np.float64).reshape(-1)
    coords = np.column_stack([boundaries, np.zeros_like(boundaries)])
    np.save(folder_path / f"coordsForPreProcessing_{recording_site}.npy", coords)


def _write_parameters(
    folder_path,
    guppy_version,
    zscore_method,
    peak_start_points,
    peak_end_points,
    bin_size_in_trials,
    remove_artifacts,
    use_transients_as_events,
    bin_width,
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
        # Real runs record the acquisition channel count here. Nothing reads it for TDT/CSV/Doric, but
        # it is the only record of how many channels a header-less NPM recording interleaved.
        noChannels=2,
        filter_window=100.0,
        removeArtifacts=remove_artifacts,
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
        useTransientsAsEvents=use_transients_as_events,
        computeBinnedMetrics=bin_width is not None,
        binnedMetricsWidth=bin_width if bin_width is not None else 60.0,
    )
    with open(folder_path / "GuPPyParamtersUsed.json", "w", encoding="utf-8") as parameters_file:
        json.dump(parameters, parameters_file, indent=4)


def _trace_data(num_samples) -> np.ndarray:
    """The sample values every derived trace carries, shared so the binned and tonic means derive from them."""
    return np.linspace(-1.0, 1.0, num_samples, dtype=np.float64)


def _write_trace(folder_path, prefix, recording_site, num_samples) -> None:
    """``<prefix>_<recording_site>.hdf5`` with a single 1-D float64 dataset under key ``data``."""
    data = _trace_data(num_samples)
    with h5py.File(folder_path / f"{prefix}_{recording_site}.hdf5", "w") as trace_file:
        trace_file.create_dataset("data", data=data, maxshape=(None,), chunks=True)


def _write_event_onsets(folder_path, event, recording_site, onsets) -> None:
    """``<event>_<recording_site>.hdf5`` with a single 1-D float64 dataset under key ``ts``.

    GuPPy writes this file per event per recording site while preprocessing, then rewrites it with the
    onsets that survived trial rejection once PSTHs are computed. Its contents are therefore the onsets
    every peri-event product was built from.
    """
    with h5py.File(folder_path / f"{event}_{recording_site}.hdf5", "w") as onsets_file:
        onsets_file.create_dataset("ts", data=np.asarray(onsets, dtype=np.float64))


def _write_time_correction(folder_path, recording_site, raw_timestamps, correction_index, sampling_rate) -> None:
    """``timeCorrection_<recording_site>.hdf5`` with four keyed datasets: ``timeRecStart``, ``timestampNew``,
    ``sampling_rate``, ``correctionIndex``.

    ``timeRecStart`` is the raw store's first timestamp, the clock origin the rest of the session is
    measured against; ``timestampNew`` is the raw timestamps that survived the lights-on trim, indexed
    by ``correctionIndex``.
    """
    time_rec_start = np.asarray([raw_timestamps[0]], dtype=np.float64)
    timestamps = raw_timestamps[correction_index]
    correction_index = correction_index.astype(np.int64)
    with h5py.File(folder_path / f"timeCorrection_{recording_site}.hdf5", "w") as time_correction_file:
        time_correction_file.create_dataset("timeRecStart", data=time_rec_start)
        time_correction_file.create_dataset("timestampNew", data=timestamps, maxshape=(None,), chunks=True)
        time_correction_file.create_dataset("sampling_rate", data=np.asarray([sampling_rate], dtype=np.float32))
        time_correction_file.create_dataset("correctionIndex", data=correction_index, maxshape=(None,), chunks=True)


def _write_transients_occurrences(folder_path, feature, recording_site) -> None:
    """``transientsOccurrences_<feature>_<recording_site>.csv`` with columns ``timestamps``, ``amplitude``.

    Written as a DataFrame via ``to_csv`` (leading integer index column). The peaks sit inside the
    trace window; a couple fall beyond the 1-s stub window on purpose.
    """
    amplitudes = (0.9, 1.4, 0.7, 1.1)
    peaks = np.column_stack([np.asarray(_TRANSIENT_PEAK_TIMES, dtype=np.float64), np.asarray(amplitudes)])
    dataframe = pandas.DataFrame(peaks, index=np.arange(peaks.shape[0]), columns=["timestamps", "amplitude"])
    dataframe.to_csv(folder_path / f"transientsOccurrences_{feature}_{recording_site}.csv")


def _write_tonic_epochs(folder_path, recording_site, tonic_epochs) -> None:
    """``tonic_epochs_<recording_site>.csv`` with columns ``label``, ``start``, ``end``.

    Written as a DataFrame via ``to_csv(index=False)``, so the file has a header row and no index
    column. ``start`` and ``end`` are seconds on the same timebase as ``timestampNew``.
    """
    dataframe = pandas.DataFrame(list(tonic_epochs), columns=["label", "start", "end"])
    dataframe.to_csv(folder_path / f"tonic_epochs_{recording_site}.csv", index=False)


def _write_tonic_means(folder_path, recording_site, tonic_epochs, timestamps, trace) -> None:
    """``tonic_<recording_site>.h5`` -- one row per epoch, columns ``mean_zscore``, ``mean_dff``.

    Written as a DataFrame via ``to_hdf(key="df")``, indexed by the epoch labels of
    ``tonic_epochs_<recording_site>.csv`` (index name ``epoch``). ``mean_zscore`` is the mean of the
    trace over the window, clamped to the samples available; ``mean_dff`` is that value scaled down,
    since the real dF/F and z-score traces differ and a reader must not be able to confuse the two
    columns.
    """
    labels = []
    mean_zscore = []
    for label, start, end in tonic_epochs:
        window = trace[(timestamps >= start) & (timestamps <= end)]
        labels.append(label)
        mean_zscore.append(float(window.mean()))
    dataframe = pandas.DataFrame(
        {"mean_zscore": mean_zscore, "mean_dff": [value / 10.0 for value in mean_zscore]},
        index=pandas.Index(labels, name="epoch"),
    )
    dataframe.to_hdf(folder_path / f"tonic_{recording_site}.h5", key="df", mode="w")


def _write_freq_and_amp(folder_path, feature, recording_site) -> None:
    """``freqAndAmp_<feature>_<recording_site>.h5`` -- one row, columns ``freq (events/min)``, ``amplitude``.

    Written as a DataFrame via ``to_hdf(key="df")``.
    """
    dataframe = pandas.DataFrame([[28.7, 2.18]], index=[_SESSION_ID], columns=["freq (events/min)", "amplitude"])
    dataframe.to_hdf(folder_path / f"freqAndAmp_{feature}_{recording_site}.h5", key="df", mode="w")


def _write_covariate_store(folder_path, covariate_name, timestamps, values) -> None:
    """``<store_id>.hdf5`` for a behavioral covariate, with ``timestamps``, ``data`` and ``sampling_rate``.

    A covariate arrives as an ordinary GuPPy CSV and is carried into the run folder as an ordinary store,
    under the store id ``storesList.csv`` row 0 gives it, with its scored values untouched.
    """
    with h5py.File(folder_path / f"{covariate_name}.hdf5", "w") as store_file:
        store_file.create_dataset(
            "timestamps", data=np.asarray(timestamps, dtype=np.float64), maxshape=(None,), chunks=True
        )
        store_file.create_dataset("data", data=np.asarray(values, dtype=np.float64), maxshape=(None,), chunks=True)
        store_file.create_dataset("sampling_rate", data=np.asarray([1 / 120], dtype=np.float64))


def _bin_edges(timestamps, bin_width) -> np.ndarray:
    """The bin edges a recording of these timestamps is tiled into.

    Bins start at the first timestamp and run in ``bin_width`` steps, with the last edge snapped back to
    the final timestamp, so a session that does not divide evenly keeps a short final bin.
    """
    start = float(timestamps[0])
    end = float(timestamps[-1])
    edges = start + bin_width * np.arange(int(np.ceil((end - start) / bin_width)) + 1, dtype=np.float64)
    edges[-1] = end
    return edges


def _bin_index(timestamps, bin_edges) -> np.ndarray:
    """Index of the bin each timestamp falls in, the final bin including its own end."""
    return np.clip(np.searchsorted(bin_edges, timestamps, side="right") - 1, 0, bin_edges.shape[0] - 2)


def _write_binned_metrics(folder_path, recording_site, bin_edges, timestamps, trace, features) -> None:
    """``binned_metrics_<recording_site>.h5`` and ``.csv`` -- one row per fixed-width time bin.

    Written as a DataFrame via ``to_hdf(key="df")`` and ``to_csv``, indexed ``0..n_bins-1`` (index name
    ``bin``), with columns ``bin_start``, ``bin_end``, ``n_samples``, ``mean_zscore``, ``mean_dff`` and a
    ``transient_count_<feature>`` per feature the detector ran on. ``mean_dff`` is the z-score mean scaled
    down, since the real traces differ and a reader must not be able to confuse the two columns.
    """
    bin_index = _bin_index(np.asarray(timestamps, dtype=np.float64), bin_edges)
    n_bins = bin_edges.shape[0] - 1
    n_samples = np.bincount(bin_index, minlength=n_bins)
    mean_zscore = np.bincount(bin_index, weights=np.asarray(trace, dtype=np.float64), minlength=n_bins) / n_samples

    binned = pandas.DataFrame(
        {
            "bin_start": bin_edges[:-1],
            "bin_end": bin_edges[1:],
            "n_samples": n_samples,
            "mean_zscore": mean_zscore,
            "mean_dff": mean_zscore / 10.0,
        },
        index=pandas.RangeIndex(n_bins, name="bin"),
    )
    for feature in sorted(features):
        binned["transient_count_" + feature] = np.histogram(_TRANSIENT_PEAK_TIMES, bins=bin_edges)[0]
    binned.to_hdf(folder_path / f"binned_metrics_{recording_site}.h5", key="df", mode="w")
    binned.to_csv(folder_path / f"binned_metrics_{recording_site}.csv")


def _write_binned_covariates(folder_path, recording_site, bin_edges, covariates) -> None:
    """``binned_covariates_<recording_site>.h5`` and ``.csv`` -- the covariate means on the metrics' bins.

    Written as a DataFrame via ``to_hdf(key="df")`` and ``to_csv``, indexed ``0..n_bins-1`` (index name
    ``bin``), with columns ``bin_start``, ``bin_end``, one ``<covariate>`` mean column and one
    ``n_samples_<covariate>`` count column per covariate. A bin holding no score reads NaN with a count
    of 0.
    """
    n_bins = bin_edges.shape[0] - 1
    columns = {"bin_start": bin_edges[:-1], "bin_end": bin_edges[1:]}
    for covariate_name, (covariate_timestamps, covariate_values) in covariates.items():
        covariate_timestamps = np.asarray(covariate_timestamps, dtype=np.float64)
        covariate_values = np.asarray(covariate_values, dtype=np.float64)
        inside = (covariate_timestamps >= bin_edges[0]) & (covariate_timestamps <= bin_edges[-1])
        bin_index = _bin_index(covariate_timestamps[inside], bin_edges)
        counts = np.bincount(bin_index, minlength=n_bins)
        sums = np.bincount(bin_index, weights=covariate_values[inside], minlength=n_bins)
        columns[covariate_name] = np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)
        columns["n_samples_" + covariate_name] = counts

    binned = pandas.DataFrame(columns, index=pandas.RangeIndex(n_bins, name="bin"))
    binned.to_hdf(folder_path / f"binned_covariates_{recording_site}.h5", key="df", mode="w")
    binned.to_csv(folder_path / f"binned_covariates_{recording_site}.csv")


def _write_covariate_correlations(folder_path, recording_site, features, covariates) -> None:
    """``covariate_correlations_<recording_site>.h5`` and ``.csv`` -- one row per (metric, covariate) pair.

    Written as a DataFrame via ``to_hdf(key="df")`` and ``to_csv``, indexed ``0..n_pairs-1`` (index name
    ``pair``), with columns ``metric``, ``covariate``, ``pearson_r``, ``spearman_rho`` and ``n_bins``.
    ``metric`` names a column of the binned-metrics table. There is no p-value column: GuPPy reports none,
    because per-bin photometry and a behavioral score are both autocorrelated across bins.

    The coefficients are fabricated but distinct per row, so a reader that mixes up rows fails.
    """
    metrics = ["mean_zscore", "mean_dff"] + ["transient_count_" + feature for feature in sorted(features)]
    rows = []
    for index, metric in enumerate(sorted(metrics)):
        for covariate_name in covariates:
            rows.append(
                {
                    "metric": metric,
                    "covariate": covariate_name,
                    "pearson_r": round(0.5 - 0.1 * index, 4),
                    "spearman_rho": round(0.4 - 0.1 * index, 4),
                    "n_bins": 3,
                }
            )
    correlations = pandas.DataFrame(rows, index=pandas.RangeIndex(len(rows), name="pair"))
    correlations.to_hdf(folder_path / f"covariate_correlations_{recording_site}.h5", key="df", mode="w")
    correlations.to_csv(folder_path / f"covariate_correlations_{recording_site}.csv")


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
    folder_path, event, recording_site, feature, baseline_corrected, peri_event_time, trial_onsets, bin_edges
) -> None:
    """PSTH ``.h5`` -- ``<event>_<recording_site>_<feature>_<recording_site>.h5`` (+ ``baselineUncorrected`` variant).

    Written as a DataFrame via ``to_hdf(key="df")``.
    """
    suffix = "" if baseline_corrected else "baselineUncorrected_"
    filename = f"{event}_{recording_site}_{suffix}{feature}_{recording_site}.h5"
    dataframe = _event_matrix_dataframe(peri_event_time, trial_onsets, bin_edges)
    dataframe.to_hdf(folder_path / filename, key="df", mode="w")


def _write_cross_correlation(
    folder_path, event, feature, recording_site_1, recording_site_2, lag_axis, trial_onsets, bin_edges
) -> None:
    """Cross-correlation ``.h5`` -- ``corr_<event>_<feature>_<recording_site_1>_<recording_site_2>.h5``.

    Written as a DataFrame via ``to_hdf(key="df")``.
    """
    filename = f"corr_{event}_{feature}_{recording_site_1}_{recording_site_2}.h5"
    dataframe = _event_matrix_dataframe(lag_axis, trial_onsets, bin_edges)
    dataframe.to_hdf(folder_path / filename, key="df", mode="w")


def _write_peak_auc(folder_path, event, recording_site, feature, trial_onsets, bin_edges, num_windows) -> None:
    """Peak/AUC ``.h5`` -- ``peak_AUC_<event>_<recording_site>_<feature>_<recording_site>.h5``.

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
    dataframe.to_hdf(
        folder_path / f"peak_AUC_{event}_{recording_site}_{feature}_{recording_site}.h5", key="df", mode="w"
    )
