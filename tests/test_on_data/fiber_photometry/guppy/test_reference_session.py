"""The GuPPy reference session: the one module in this directory whose inputs GuPPy itself produced.

``guppy_example_1`` is a synthetic CSV session that a stock GuPPy 2.0.0a9 run processed end to end,
so its ``guppy_example_1_output_1`` folder is genuine GuPPy output. Every other module here pairs a
real acquisition file with ``mock_guppy``, a hand-written replica of GuPPy's on-disk format.

Two rules keep this module an independent check on that replica.

* Do not add the reference session to the acquisition-format modules, and do not add ``mock_guppy``
  here.
* Every expectation is read straight off disk with plain ``h5py``/``pandas``/``numpy`` calls, or is a
  hard-coded literal. Nothing in this module may import from
  ``neuroconv.datainterfaces.fiber_photometry.guppy``.

The subject is the public ``GuppyConverter``, not ``GuppyInterface``.

The session's own parameters complement what the mock covers. GuPPy ran here with
``use_time_or_trials="Time (min)"`` (decimal ``bin_(0.0-1.0)`` labels), ``artifactsRemovalMethod="replace
with NaN"``, and an artifact window drawn on one recording site only; the mock emits integer
``bin_(0-3)`` labels, ``concatenate``, and a window on every site.
"""

from copy import deepcopy
from datetime import datetime, timezone

import h5py
import numpy as np
import pandas
import pytest
from pynwb import NWBHDF5IO

from neuroconv.converters import GuppyConverter
from neuroconv.utils import dict_deep_update

from ._metadata import (
    build_device_metadata,
    build_fiber_photometry_metadata,
    build_series_metadata,
)
from ...setup_paths import OPHYS_DATA_PATH

SESSION_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "Guppy" / "guppy_example_1"
GUPPY_OUTPUT_FOLDER = SESSION_FOLDER / "guppy_example_1_output_1"
# GuPPy prefixes every peak-AUC row label with the session name, which it takes from the folder name.
SESSION_NAME = "guppy_example_1"

# storesList.csv pairs six raw stores with the labels GuPPy gave them:
#     dms_control_channel,dms_signal_channel,nac_control_channel,nac_signal_channel,poke_ttl,reward_ttl
#     control_dms,signal_dms,control_nac,signal_nac,nose_poke,reward_delivery
RECORDING_SITES = ["dms", "nac"]
EVENT_NAMES = ["nose_poke", "reward_delivery"]
TRACE_PREFIXES = ["cntrl_sig_fit", "dff", "z_score"]
FEATURES = ["dff", "z_score"]
# Each role series column-stacks that role's store from every recording site, in storesList order.
ROLE_TO_STORE_IDS = {
    "signal": ["dms_signal_channel", "nac_signal_channel"],
    "control": ["dms_control_channel", "nac_control_channel"],
}
ROLE_TO_SERIES_NAME = {
    "signal": "FiberPhotometryResponseSeriesSignal",
    "control": "FiberPhotometryResponseSeriesControl",
}
# build_fiber_photometry_metadata lays the table out site-major, signal before control.
RECORDING_SITE_TO_TABLE_ROWS = {"dms": [0, 1], "nac": [2, 3]}

SAMPLING_RATE = 25.0
NUM_SAMPLES = 3750  # 150 s at 25 Hz
SESSION_START_TIME = datetime(2024, 1, 1, tzinfo=timezone.utc)

MERGED_EVENTS_TABLE_NAME = "BehavioralEvents"
# What the raw event CSVs carry, which is what the acquisition side writes into the merged table.
RAW_EVENT_ONSETS = {
    "nose_poke": [20.0, 58.0, 100.0, 128.0],
    "reward_delivery": [3.0, 15.0, 35.0, 36.0, 55.0, 75.0, 95.0, 125.0],
}
# What GuPPy kept, per <event>_<recording_site>.hdf5 -- the onsets it actually built trials around.
ANALYZED_EVENT_ONSETS = {
    "nose_poke": [20.0, 58.0, 100.0, 128.0],
    "reward_delivery": [15.0, 35.0, 55.0, 75.0, 95.0, 125.0],
}

# Trials are concatenated across events in storesList order: nose_poke's four, then reward_delivery's six.
# These are ten of the twelve onsets the raw event CSVs carry, because GuPPy drops an onset earlier than
# abs(baselineCorrectionStart) = 5 s (reward at 3.0) and the later of any pair closer than
# timeInterval = 2 s (reward at 36.0, against 35.0).
PSTH_TRIAL_ONSETS = [20.0, 58.0, 100.0, 128.0, 15.0, 35.0, 55.0, 75.0, 95.0, 125.0]
PSTH_TRIALS_PER_EVENT = [4, 6]
NUM_PSTH_TRIALS = 10
NUM_PERI_EVENT_SAMPLES = 751  # the -10/+20 s window at 25 Hz
NUM_LAGS = 1501  # the +/-30 s cross-correlation window at 25 Hz

# bin_psth_trials=1 with "Time (min)" binning, over a 150 s session -> three one-minute bins per event.
BIN_EDGES_PER_EVENT = [[0.0, 1.0], [1.0, 2.0], [2.0, 3.0]]

# peak_startPoint/peak_endPoint in GuPPyParamtersUsed.json, with the trailing NaN slots dropped.
PEAK_WINDOW_STARTS = [-5.0, 0.0, 5.0]
PEAK_WINDOW_STOPS = [0.0, 3.0, 10.0]

# Detected transients per (recording site, feature). nac lost one to its artifact window.
TRANSIENT_COUNTS = {("dms", "dff"): 10, ("dms", "z_score"): 10, ("nac", "dff"): 9, ("nac", "z_score"): 9}

# Only nac has a coordsForPreProcessing file -- the artifact window was drawn on that site alone -- so
# the valid-signal intervals object carries exactly one row.
VALID_SIGNAL_INTERVALS = {"nac": [[2.0, 149.0]]}

# The full manifest of what a GuPPy run of this shape lands in /processing/guppy/.
EXPECTED_MODULE_CONTENTS = {
    "recording_sites": "GuppyRecordingSitesTable",
    "events": "GuppyEventsTable",
    "valid_signal_intervals": "GuppyValidSignalIntervals",
    "transient_summary": "GuppyTransientSummaryTable",
    "cntrl_sig_fit_dms": "GuppyDerivedResponseSeries",
    "cntrl_sig_fit_nac": "GuppyDerivedResponseSeries",
    "dff_dms": "GuppyDerivedResponseSeries",
    "dff_nac": "GuppyDerivedResponseSeries",
    "z_score_dms": "GuppyDerivedResponseSeries",
    "z_score_nac": "GuppyDerivedResponseSeries",
    "transients_dms_dff": "GuppyTransientsTable",
    "transients_dms_z_score": "GuppyTransientsTable",
    "transients_nac_dff": "GuppyTransientsTable",
    "transients_nac_z_score": "GuppyTransientsTable",
    "cross_correlation_dff_dms_nac": "GuppyCrossCorrelation",
    "cross_correlation_z_score_dms_nac": "GuppyCrossCorrelation",
    "psth_dms_dff": "GuppyPSTH",
    "psth_dms_dff_baseline_uncorrected": "GuppyPSTH",
    "psth_dms_z_score": "GuppyPSTH",
    "psth_dms_z_score_baseline_uncorrected": "GuppyPSTH",
    "psth_nac_dff": "GuppyPSTH",
    "psth_nac_dff_baseline_uncorrected": "GuppyPSTH",
    "psth_nac_z_score": "GuppyPSTH",
    "psth_nac_z_score_baseline_uncorrected": "GuppyPSTH",
    "peak_auc_dms_dff": "GuppyPeakAUC",
    "peak_auc_dms_z_score": "GuppyPeakAUC",
    "peak_auc_nac_dff": "GuppyPeakAUC",
    "peak_auc_nac_z_score": "GuppyPeakAUC",
}


def read_hdf5_dataset(file_path, dataset_name):
    """Read one dataset out of a GuPPy ``.hdf5`` file (raw h5py, not a pandas store)."""
    with h5py.File(file_path, "r") as file:
        return np.asarray(file[dataset_name][:])


def trial_columns(dataframe):
    """The per-trial columns of a PSTH/cross-correlation frame: GuPPy names each one after its onset."""
    columns = []
    for column in dataframe.columns:
        try:
            float(column)
        except ValueError:
            continue
        columns.append(column)
    return columns


def psth_source_path(event, recording_site, feature, *, baseline_corrected):
    correction = "" if baseline_corrected else "baselineUncorrected_"
    return GUPPY_OUTPUT_FOLDER / f"{event}_{recording_site}_{correction}{feature}_{recording_site}.h5"


class TestGuppyReferenceSession:
    @pytest.fixture(scope="class")
    def converter(self):
        return GuppyConverter(
            fiber_photometry_folder_path=SESSION_FOLDER,
            events_folder_path=SESSION_FOLDER,
            guppy_folder_path=GUPPY_OUTPUT_FOLDER,
            acquisition_format="csv",
        )

    @pytest.fixture(scope="class")
    def metadata(self, converter):
        """The converter's metadata with the user-supplied FiberPhotometry provenance chain merged in.

        A CSV session carries no clock origin, so the session start time is the caller's to supply.
        """
        metadata = converter.get_metadata()
        metadata = dict_deep_update(metadata, build_device_metadata(RECORDING_SITES))
        metadata["FiberPhotometry"] = dict_deep_update(
            metadata["FiberPhotometry"], build_fiber_photometry_metadata(RECORDING_SITES)
        )
        metadata["FiberPhotometry"] = dict_deep_update(
            metadata["FiberPhotometry"], build_series_metadata(RECORDING_SITES)
        )
        metadata["NWBFile"]["session_start_time"] = SESSION_START_TIME
        return metadata

    @pytest.fixture(scope="class")
    def nwbfile_path(self, converter, metadata, tmp_path_factory):
        """Convert the reference session once; every assertion below reads this one file."""
        nwbfile_path = tmp_path_factory.mktemp("guppy_reference") / "reference_session.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True)
        return nwbfile_path

    @pytest.fixture
    def nwbfile(self, nwbfile_path):
        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            yield io.read()

    @pytest.fixture
    def module(self, nwbfile):
        return nwbfile.processing["guppy"]

    @pytest.fixture
    def mutable_metadata(self, metadata):
        """A private copy, for the tests that break the metadata to check it fails loudly."""
        return deepcopy(metadata)

    def recording_site_names(self, module, dynamic_table_region):
        """Resolve a recording-site DynamicTableRegion's row indices to GuPPy recording site names."""
        names = list(module["recording_sites"]["recording_site"].data)
        return [names[index] for index in dynamic_table_region.data]

    def event_names(self, module, dynamic_table_region):
        """Resolve an event DynamicTableRegion's row indices to GuPPy event names."""
        names = list(module["events"]["event_name"].data)
        return [names[index] for index in dynamic_table_region.data]

    # ------------------------------------------------------------------ the manifest

    def test_processing_module_holds_every_guppy_product(self, module):
        assert {name: obj.neurodata_type for name, obj in module.data_interfaces.items()} == EXPECTED_MODULE_CONTENTS

    def test_parameters_match_the_recorded_json(self, nwbfile):
        """GuPPyParamtersUsed.json is transcribed onto GuppyParameters, names normalised to snake_case."""
        parameters = nwbfile.lab_meta_data["guppy_parameters"]
        assert parameters.guppy_version == "2.0.0a9"
        assert parameters.zscore_method == "standard z-score"
        assert parameters.artifacts_removal_method == "replace with NaN"
        assert bool(parameters.remove_artifacts) is True
        assert bool(parameters.isosbestic_control) is True
        assert float(parameters.filter_window) == 50.0
        assert int(parameters.bin_psth_trials) == 1
        assert float(parameters.n_sec_prev) == -10.0
        assert float(parameters.n_sec_post) == 20.0
        assert float(parameters.baseline_correction_start) == -5.0
        assert float(parameters.time_interval) == 2.0
        assert float(parameters.transients_thresh) == 3.0
        # The ten peak-window slots are trimmed to the three the user filled in.
        np.testing.assert_array_equal(parameters.peak_start_points[:], PEAK_WINDOW_STARTS)
        np.testing.assert_array_equal(parameters.peak_end_points[:], PEAK_WINDOW_STOPS)

    def test_registries_name_what_storeslist_named(self, module):
        """Both registries are populated from storesList.csv: its recording sites and its event labels."""
        assert list(module["recording_sites"]["recording_site"].data) == RECORDING_SITES
        assert list(module["events"]["event_name"].data) == EVENT_NAMES

    # ------------------------------------------------------------------ format-independent converter wiring
    #
    # Asserted here once for every acquisition format; test_csv/test_tdt/test_doric/test_npm cover only
    # their own seam.

    def test_acquisition_is_grouped_by_role_and_stacked_in_stores_list_order(self, nwbfile):
        """One series per excitation wavelength, column-stacking that role's store from every site.

        Each column is compared to its source file, which pins the stacking order as well as the values.
        """
        assert set(nwbfile.acquisition) == set(ROLE_TO_SERIES_NAME.values())
        for role, store_ids in ROLE_TO_STORE_IDS.items():
            series = nwbfile.acquisition[ROLE_TO_SERIES_NAME[role]]
            assert series.data.shape == (NUM_SAMPLES, len(store_ids))
            for column, store_id in enumerate(store_ids):
                expected = pandas.read_csv(SESSION_FOLDER / f"{store_id}.csv")["data"].to_numpy()
                np.testing.assert_array_equal(series.data[:, column], expected)

    def test_recording_sites_registry_links_each_site_to_its_own_fibers(self, module):
        """Each GuPPy recording site's registry row points at that site's own acquisition table rows."""
        recording_sites_table = module["recording_sites"]
        for row, recording_site in enumerate(RECORDING_SITES):
            linked = recording_sites_table["fiber_photometry_table_region"][row]
            assert set(linked["location"]) == {recording_site.upper()}
            assert sorted(linked["excitation_wavelength_in_nm"]) == [405.0, 465.0]
        flat_row_indices = list(recording_sites_table["fiber_photometry_table_region"].target.data[:])
        assert flat_row_indices == [row for rows in RECORDING_SITE_TO_TABLE_ROWS.values() for row in rows]

    def test_events_merge_into_one_table_with_registry_back_references(self, nwbfile, module):
        """Every event type lands in one EventsTable, and each registry row references its own rows."""
        assert set(nwbfile.events) == {MERGED_EVENTS_TABLE_NAME}
        events_dataframe = nwbfile.events[MERGED_EVENTS_TABLE_NAME].to_dataframe()
        assert "event_type" in nwbfile.get_events_table(MERGED_EVENTS_TABLE_NAME).colnames
        for event_name, onsets in RAW_EVENT_ONSETS.items():
            matching = events_dataframe[events_dataframe.event_type == event_name]
            np.testing.assert_array_equal(np.sort(matching.timestamp.to_numpy()), onsets)
        # The merged table is globally time-sorted, not grouped by contributing interface.
        timestamps = events_dataframe.timestamp.to_numpy()
        np.testing.assert_array_equal(timestamps, np.sort(timestamps))

    def test_registry_references_only_the_onsets_guppy_analyzed(self, module):
        """Each registry row points at the occurrences GuPPy built trials from, not every occurrence.

        GuPPy discards an onset it cannot build a trial around: reward at 3.0 s is earlier than
        abs(baselineCorrectionStart) = 5 s, and reward at 36.0 s is within timeInterval = 2 s of 35.0 s.
        Both stay in the acquisition table and neither is claimed here.
        """
        events_table = module["events"]
        for row, event_name in enumerate(EVENT_NAMES):
            referenced = events_table["events"][row]
            assert set(referenced["event_type"]) == {event_name}
            np.testing.assert_array_equal(
                np.sort(referenced["timestamp"].to_numpy()), ANALYZED_EVENT_ONSETS[event_name]
            )

        discarded = set(RAW_EVENT_ONSETS["reward_delivery"]) - set(ANALYZED_EVENT_ONSETS["reward_delivery"])
        assert discarded == {3.0, 36.0}

    def test_registry_row_count_matches_every_products_trial_count(self, module):
        """The rows referenced across the whole registry equal the trials in every peri-event product."""
        events_table = module["events"]
        total_referenced_rows = sum(len(events_table["events"][row]) for row in range(len(events_table.id)))
        assert total_referenced_rows == NUM_PSTH_TRIALS

        trial_counts = {}
        for name, product in module.data_interfaces.items():
            if product.neurodata_type == "GuppyPSTH":
                trial_counts[name] = product.traces.shape[1]
            elif product.neurodata_type == "GuppyPeakAUC":
                trial_counts[name] = product.peak_positive.shape[1]
            elif product.neurodata_type == "GuppyCrossCorrelation":
                trial_counts[name] = product.trials.shape[1]
        assert trial_counts, "No peri-event products were written, so the invariant proves nothing."
        assert set(trial_counts.values()) == {total_referenced_rows}, trial_counts

    def test_metadata_schema_includes_both_subinterfaces(self, converter):
        """The GuPPy block and the acquisition block coexist in one metadata schema."""
        schema = converter.get_metadata_schema()
        guppy_metadata_key = converter.data_interface_objects["Guppy"].metadata_key
        assert guppy_metadata_key in schema["properties"]["FiberPhotometry"]["properties"]["Guppy"]["properties"]

    def test_derive_recording_site_to_table_rows(self, converter, metadata):
        """Each recording site owns the table-row indices its series declared as their regions."""
        assert converter._derive_recording_site_to_table_rows(metadata) == RECORDING_SITE_TO_TABLE_ROWS

    def test_missing_table_row_raises(self, converter, mutable_metadata):
        """A series referencing a row key the table does not define fails loudly."""
        del mutable_metadata["FiberPhotometry"]["FiberPhotometryTable"]["rows"]["dms_signal"]
        with pytest.raises(AssertionError, match="not present"):
            converter._derive_recording_site_to_table_rows(mutable_metadata)

    def test_missing_table_region_raises(self, converter, mutable_metadata):
        """A series that declares no table region fails loudly rather than linking nothing."""
        del mutable_metadata["FiberPhotometry"]["signal"]["fiber_photometry_table_region"]
        with pytest.raises(AssertionError, match="declares no 'fiber_photometry_table_region'"):
            converter._derive_recording_site_to_table_rows(mutable_metadata)

    def test_table_region_length_mismatch_raises(self, converter, mutable_metadata):
        """A region naming fewer rows than the series stacks columns fails loudly."""
        mutable_metadata["FiberPhotometry"]["signal"]["fiber_photometry_table_region"] = ["dms_signal"]
        with pytest.raises(AssertionError, match="stacks 2 store"):
            converter._derive_recording_site_to_table_rows(mutable_metadata)

    # ------------------------------------------------------------------ products match their source files

    def test_traces_match_source(self, module):
        """Each derived trace carries the samples GuPPy wrote, on GuPPy's own regular timebase."""
        for recording_site in RECORDING_SITES:
            for prefix in TRACE_PREFIXES:
                series = module[f"{prefix}_{recording_site}"]
                expected = read_hdf5_dataset(GUPPY_OUTPUT_FOLDER / f"{prefix}_{recording_site}.hdf5", "data")
                assert expected.shape == (NUM_SAMPLES,)
                np.testing.assert_array_equal(series.data[:], expected)
                # timestampNew is 0.0, 0.04, ... so the timebase is written as starting_time + rate.
                assert series.timestamps is None
                assert float(series.starting_time) == 0.0
                assert float(series.rate) == SAMPLING_RATE
                assert self.recording_site_names(module, series.recording_site) == [recording_site]
                # Acquisition provenance is reached through the recording-site row, not stamped here.
                assert series.fiber_photometry_table_region is None

    def test_transients_match_source(self, module):
        for (recording_site, feature), expected_count in TRANSIENT_COUNTS.items():
            source = pandas.read_csv(GUPPY_OUTPUT_FOLDER / f"transientsOccurrences_{feature}_{recording_site}.csv")
            assert len(source) == expected_count

            table = module[f"transients_{recording_site}_{feature}"]
            assert len(table) == expected_count
            assert table.trace_type == feature
            np.testing.assert_array_equal(table["timestamp"].data[:], source["timestamps"].to_numpy())
            np.testing.assert_array_equal(table["amplitude"].data[:], source["amplitude"].to_numpy())
            assert set(self.recording_site_names(module, table["recording_site"])) == {recording_site}

    def test_transient_summary_matches_source(self, module):
        """One row per (recording site, feature), each carrying that pair's freqAndAmp values."""
        summary = module["transient_summary"]
        expected_rows = []
        for recording_site in RECORDING_SITES:
            # The interface discovers z_score before dff, which is the order the rows land in.
            for feature in ("z_score", "dff"):
                source = pandas.read_hdf(GUPPY_OUTPUT_FOLDER / f"freqAndAmp_{feature}_{recording_site}.h5")
                expected_rows.append(
                    (
                        recording_site,
                        feature,
                        float(source["freq (events/min)"].iloc[0]),
                        float(source["amplitude"].iloc[0]),
                    )
                )

        actual_rows = list(
            zip(
                self.recording_site_names(module, summary["recording_site"]),
                summary["trace_type"].data,
                summary["frequency_per_min"].data,
                summary["mean_amplitude"].data,
            )
        )
        assert actual_rows == expected_rows

    def test_psths_match_source(self, module):
        """One PSTH per condition, with the two events' trial columns concatenated in storesList order."""
        for recording_site in RECORDING_SITES:
            for feature in FEATURES:
                for baseline_corrected in (True, False):
                    suffix = "" if baseline_corrected else "_baseline_uncorrected"
                    psth = module[f"psth_{recording_site}_{feature}{suffix}"]
                    assert psth.trace_type == feature
                    assert bool(psth.baseline_corrected) is baseline_corrected

                    traces_blocks, mean_blocks, onsets = [], [], []
                    for event in EVENT_NAMES:
                        source = pandas.read_hdf(
                            psth_source_path(event, recording_site, feature, baseline_corrected=baseline_corrected)
                        )
                        np.testing.assert_array_equal(
                            psth.peri_event_time[:], source["timestamps"].to_numpy(dtype=np.float64)
                        )
                        columns = trial_columns(source)
                        traces_blocks.append(source[columns].to_numpy(dtype=np.float64))
                        mean_blocks.append(source["mean"].to_numpy(dtype=np.float64))
                        onsets.extend(float(column) for column in columns)

                    assert [block.shape[1] for block in traces_blocks] == PSTH_TRIALS_PER_EVENT
                    np.testing.assert_array_equal(psth.traces[:], np.concatenate(traces_blocks, axis=1))
                    np.testing.assert_array_equal(psth.mean[:], np.stack(mean_blocks, axis=1))
                    assert onsets == PSTH_TRIAL_ONSETS
                    assert psth.traces.shape == (NUM_PERI_EVENT_SAMPLES, NUM_PSTH_TRIALS)
                    assert self.recording_site_names(module, psth.recording_site) == [recording_site]
                    assert self.event_names(module, psth.summary_event) == EVENT_NAMES
                    # Every trial column keeps the label of the event it came from.
                    assert self.event_names(module, psth.event) == [
                        event for event, count in zip(EVENT_NAMES, PSTH_TRIALS_PER_EVENT) for _ in range(count)
                    ]

    def test_psth_bins_carry_the_decimal_time_labels(self, module):
        """ "Time (min)" binning writes bin_(0.0-1.0)-style labels, one set of three bins per event."""
        psth = module["psth_dms_dff"]
        np.testing.assert_array_equal(psth.bin_edges[:], BIN_EDGES_PER_EVENT * len(EVENT_NAMES))
        assert psth.binned_mean.shape == (NUM_PERI_EVENT_SAMPLES, len(BIN_EDGES_PER_EVENT) * len(EVENT_NAMES))
        assert self.event_names(module, psth.bin_event) == [event for event in EVENT_NAMES for _ in BIN_EDGES_PER_EVENT]

        source = pandas.read_hdf(psth_source_path("nose_poke", "dms", "dff", baseline_corrected=True))
        for column, (start, stop) in enumerate(BIN_EDGES_PER_EVENT):
            np.testing.assert_array_equal(
                psth.binned_mean[:, column], source[f"bin_({start}-{stop})"].to_numpy(dtype=np.float64)
            )

    def test_peak_aucs_match_source(self, module):
        for recording_site in RECORDING_SITES:
            for feature in FEATURES:
                peak_auc = module[f"peak_auc_{recording_site}_{feature}"]
                np.testing.assert_array_equal(peak_auc.window_start[:], PEAK_WINDOW_STARTS)
                np.testing.assert_array_equal(peak_auc.window_stop[:], PEAK_WINDOW_STOPS)
                assert peak_auc.peak_positive.shape == (len(PEAK_WINDOW_STARTS), NUM_PSTH_TRIALS)

                mean_columns = []
                for event in EVENT_NAMES:
                    source = pandas.read_hdf(
                        GUPPY_OUTPUT_FOLDER / f"peak_AUC_{event}_{recording_site}_{feature}_{recording_site}.h5"
                    )
                    mean_row = f"{SESSION_NAME}_mean"
                    mean_columns.append(
                        np.array(
                            [
                                float(source.loc[mean_row, f"peak_pos_{window + 1}"])
                                for window in range(len(PEAK_WINDOW_STARTS))
                            ]
                        )
                    )
                np.testing.assert_array_equal(peak_auc.mean_peak_positive[:], np.stack(mean_columns, axis=1))
                np.testing.assert_array_equal(peak_auc.trial_onset_times[:], PSTH_TRIAL_ONSETS)
                assert self.recording_site_names(module, peak_auc.recording_site) == [recording_site]
                assert self.event_names(module, peak_auc.summary_event) == EVENT_NAMES

    def test_cross_correlations_match_source(self, module):
        """GuPPy computed the one available site pair, so each feature yields a single dms-nac object."""
        for feature in FEATURES:
            cross_correlation = module[f"cross_correlation_{feature}_dms_nac"]
            assert cross_correlation.trace_type == feature
            assert self.recording_site_names(module, cross_correlation.recording_site) == ["dms", "nac"]

            trials_blocks, mean_blocks = [], []
            for event in EVENT_NAMES:
                source = pandas.read_hdf(
                    GUPPY_OUTPUT_FOLDER / "cross_correlation_output" / f"corr_{event}_{feature}_dms_nac.h5"
                )
                np.testing.assert_array_equal(cross_correlation.lag[:], source["timestamps"].to_numpy(dtype=np.float64))
                trials_blocks.append(source[trial_columns(source)].to_numpy(dtype=np.float64))
                mean_blocks.append(source["mean"].to_numpy(dtype=np.float64))

            np.testing.assert_array_equal(cross_correlation.trials[:], np.concatenate(trials_blocks, axis=1))
            np.testing.assert_array_equal(cross_correlation.mean[:], np.stack(mean_blocks, axis=1))
            assert cross_correlation.trials.shape == (NUM_LAGS, NUM_PSTH_TRIALS)
            np.testing.assert_array_equal(cross_correlation.trial_onset_times[:], PSTH_TRIAL_ONSETS)

    def test_valid_signal_intervals_cover_only_the_site_with_an_artifact_window(self, module):
        """coordsForPreProcessing exists for nac alone, so dms contributes no interval row."""
        intervals = module["valid_signal_intervals"]
        recording_site_names = self.recording_site_names(module, intervals["recording_site"])
        grouped = {}
        for recording_site, start, stop in zip(
            recording_site_names, intervals["start_time"].data, intervals["stop_time"].data
        ):
            grouped.setdefault(recording_site, []).append([start, stop])
        assert grouped == VALID_SIGNAL_INTERVALS
