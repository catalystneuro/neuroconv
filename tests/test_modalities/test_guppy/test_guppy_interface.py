"""Data-free unit tests for ``GuppyInterface``.

Two kinds of test live here, and neither makes a claim about GuPPy's on-disk format. That claim is
made once, against output GuPPy itself produced, in
``tests/test_on_data/fiber_photometry/guppy/test_reference_session.py``; asserting it a second time
against ``mock_guppy`` -- a replica written from the same beliefs as the reader -- would prove nothing.

* Parsing: the two bin-label parsing sites, exercised directly on hand-built DataFrames and indexes.
* Behavior and branches: the options a caller can flip and the shapes a GuPPy folder can take, run
  against ``mock_guppy`` because they need *a* folder rather than a *faithful* one.

The mock's defaults are deliberately the complement of the reference session's: integer ``bin_(0-3)``
labels from ``use_time_or_trials="# of trials"``, ``artifactsRemovalMethod="concatenate"``, and an
artifact window on every recording site. Between the two, both binning modes are covered.
"""

import shutil

import h5py
import numpy as np
import pandas
import pytest
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces.fiber_photometry.guppy.guppydatainterface import (
    GuppyInterface,
)
from neuroconv.tools.testing import generate_mock_guppy_output_folder

SESSION = "Photo_249_391-200721-120136"

# The mock topology: two recording sites, three events, two features, num_trials=4 binned three to a bin.
RECORDING_SITES = ["dms", "dls"]
EVENT_NAMES = ["rewarded_nose_pokes", "unrewarded_nose_pokes", "port_entries"]
TRACE_PREFIXES = ["cntrl_sig_fit", "dff", "z_score"]
MOCK_SAMPLING_RATE = 200.0
MOCK_STARTING_TIME = 1.0
BIN_EDGES_PER_EVENT = [[0.0, 3.0], [3.0, 4.0]]
VALID_SIGNAL_INTERVALS = [[1.25, 1.75], [2.0, 2.5]]
# The generator's default whole-session bins: 0.5 s wide over a 1.0-2.995 s timebase, so the last is short.
BIN_EDGES = [[1.0, 1.5], [1.5, 2.0], [2.0, 2.5], [2.5, 2.995]]
# The mean of the mock's -1 to 1 ramp within each of those bins.
BIN_MEAN_ZSCORE = [-0.751880, -0.250627, 0.250627, 0.751880]
# The generator's default behavioral covariate.
COVARIATE_NAME = "akinesia"
# The generator's default tonic epoch windows, written for every recording site.
TONIC_EPOCHS = [("baseline", 1.0, 2.0), ("post_injection", 2.0, 3.0)]
# The generator's default onsets, shared by every event: they label the trial columns of every
# peri-event product and fill <event>_<recording_site>.hdf5.
MOCK_TRIAL_ONSETS = [10.0, 20.0, 30.0, 40.0]


class TestExtractBins:
    """``GuppyInterface._extract_bins`` parses ``bin_(...)`` value/error COLUMNS of a PSTH/cross-corr file."""

    def test_time_min_float_labels(self):
        # Columns deliberately out of order to confirm the result is sorted by bin start.
        dataframe = pandas.DataFrame(
            {
                "0.5": [1.0, 2.0],  # a per-trial onset column -- must be ignored
                "bin_(2.0-4.0)": [12.0, 13.0],
                "bin_err_(2.0-4.0)": [0.3, 0.4],
                "bin_(0.0-2.0)": [10.0, 11.0],
                "bin_err_(0.0-2.0)": [0.1, 0.2],
            }
        )
        result = GuppyInterface._extract_bins(dataframe)
        np.testing.assert_array_equal(result["bin_edges"], np.array([[0.0, 2.0], [2.0, 4.0]]))
        np.testing.assert_array_equal(result["binned_value"], np.array([[10.0, 12.0], [11.0, 13.0]]))
        np.testing.assert_array_equal(result["binned_error"], np.array([[0.1, 0.3], [0.2, 0.4]]))

    def test_trials_integer_labels_unchanged(self):
        dataframe = pandas.DataFrame(
            {
                "bin_(0-3)": [10.0, 11.0],
                "bin_err_(0-3)": [0.1, 0.2],
            }
        )
        result = GuppyInterface._extract_bins(dataframe)
        np.testing.assert_array_equal(result["bin_edges"], np.array([[0.0, 3.0]]))
        np.testing.assert_array_equal(result["binned_value"], np.array([[10.0], [11.0]]))
        np.testing.assert_array_equal(result["binned_error"], np.array([[0.1], [0.2]]))

    def test_returns_none_without_bin_columns(self):
        dataframe = pandas.DataFrame({"0.5": [1.0, 2.0], "mean": [3.0, 4.0]})
        assert GuppyInterface._extract_bins(dataframe) is None


class TestPartitionPeakAucIndex:
    """``GuppyInterface._partition_peak_auc_index`` splits a peak_AUC file's INDEX into trial/bin/mean rows."""

    def test_time_min_float_rows_route_to_bins(self):
        # Float bin rows used to crash the trial-onset parse (ValueError: '(0.0-2.0)'); they must route to bins.
        index = [
            f"{SESSION}_12.5",
            f"{SESSION}_3.0",
            f"{SESSION}_bin_(2.0-4.0)",
            f"{SESSION}_bin_(0.0-2.0)",
            f"{SESSION}_mean",
        ]
        trial_rows, bin_rows, mean_row = GuppyInterface._partition_peak_auc_index(index)
        assert trial_rows == [(3.0, f"{SESSION}_3.0"), (12.5, f"{SESSION}_12.5")]
        assert bin_rows == [
            (0.0, 2.0, f"{SESSION}_bin_(0.0-2.0)"),
            (2.0, 4.0, f"{SESSION}_bin_(2.0-4.0)"),
        ]
        assert mean_row == f"{SESSION}_mean"

    def test_trials_integer_rows(self):
        index = [
            f"{SESSION}_7.0",
            f"{SESSION}_bin_(0-3)",
            f"{SESSION}_bin_(3-6)",
            f"{SESSION}_mean",
        ]
        trial_rows, bin_rows, mean_row = GuppyInterface._partition_peak_auc_index(index)
        assert trial_rows == [(7.0, f"{SESSION}_7.0")]
        assert bin_rows == [
            (0.0, 3.0, f"{SESSION}_bin_(0-3)"),
            (3.0, 6.0, f"{SESSION}_bin_(3-6)"),
        ]
        assert mean_row == f"{SESSION}_mean"

    def test_unbinned_index(self):
        index = [f"{SESSION}_3.0", f"{SESSION}_12.5", f"{SESSION}_mean"]
        trial_rows, bin_rows, mean_row = GuppyInterface._partition_peak_auc_index(index)
        assert trial_rows == [(3.0, f"{SESSION}_3.0"), (12.5, f"{SESSION}_12.5")]
        assert bin_rows == []
        assert mean_row == f"{SESSION}_mean"


class TestGuppyInterfaceBehavior:
    """The caller-visible options and the folder shapes the reference session cannot express."""

    @pytest.fixture(scope="class")
    @classmethod
    def guppy_output_folder(cls, tmp_path_factory):
        """One mock folder per class: the interface only reads it, and mutation tests copy it first."""
        return generate_mock_guppy_output_folder(tmp_path_factory.mktemp("guppy") / "guppy_output")

    @pytest.fixture
    def interface(self, guppy_output_folder):
        return GuppyInterface(folder_path=str(guppy_output_folder))

    @pytest.fixture
    def nwbfile(self):
        """A plain NWBFile. ``GuppyInterface`` is standalone: it needs no acquisition or events tables
        to write, since it writes its own events and the fiber link is populated later by a converter."""
        return mock_NWBFile()

    def add_to_nwbfile(self, interface, nwbfile, *, stub_test):
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile, metadata, stub_test=stub_test)
        return nwbfile.processing["guppy"]

    # ------------------------------------------------------------------ metadata as an editing surface

    def test_metadata_entries_expose_name_and_description_only(self, interface):
        """Every product entry carries exactly the editable name and description, name defaulting to the key.

        No internal handles (recording site, trace basename, trace type, site pair, event lists) and no
        derived unit ever leak into the metadata.
        """
        guppy_metadata = interface.get_metadata()["FiberPhotometry"]["Guppy"][interface.metadata_key]
        for family in ("Traces", "Transients", "CrossCorrelations", "PSTHs", "PeakAUCs", "Covariates"):
            for name, entry in guppy_metadata[family].items():
                assert set(entry.keys()) == {"name", "description"}, (family, entry)
                assert entry["name"] == name

    def test_metadata_key_defaults_to_output_folder_name(self, interface, guppy_output_folder):
        """With no explicit metadata_key, the block is scoped by the GuPPy output folder's name."""
        assert interface.metadata_key == guppy_output_folder.name
        assert set(interface.get_metadata()["FiberPhotometry"]["Guppy"]) == {guppy_output_folder.name}

    def test_metadata_key_scopes_block_and_edits_propagate(self, guppy_output_folder, nwbfile):
        """A non-default metadata_key scopes the whole block, and editing an object's name and
        description propagates to the written object -- including an event-bearing product (PSTH)."""
        interface = GuppyInterface(folder_path=str(guppy_output_folder), metadata_key="GuppyB")
        metadata = interface.get_metadata()
        guppy_namespace = metadata["FiberPhotometry"]["Guppy"]
        assert set(guppy_namespace) == {"GuppyB"}

        guppy_block = guppy_namespace["GuppyB"]
        trace_tag = next(iter(guppy_block["Traces"]))
        guppy_block["Traces"][trace_tag]["name"] = "renamed_trace"
        guppy_block["Traces"][trace_tag]["description"] = "custom trace description"
        psth_tag = next(iter(guppy_block["PSTHs"]))
        guppy_block["PSTHs"][psth_tag]["description"] = "custom psth description"

        interface.add_to_nwbfile(nwbfile, metadata, stub_test=True)
        module = nwbfile.processing["guppy"]
        assert "renamed_trace" in module.data_interfaces
        assert module["renamed_trace"].description == "custom trace description"
        assert module[psth_tag].description == "custom psth description"

    # ------------------------------------------------------------------ standalone writing

    def test_standalone_recording_sites_registry_carries_no_outward_link(self, interface, nwbfile):
        """Run without a converter, the recording sites registry is names only.

        The fiber link requires a converter that owns the FiberPhotometryTable, or an NWBFile already
        holding it; the interface has no acquisition provenance of its own to write.
        """
        module = self.add_to_nwbfile(interface, nwbfile, stub_test=True)

        recording_sites_table = module["recording_sites"]
        assert recording_sites_table.neurodata_type == "GuppyRecordingSitesTable"
        assert list(recording_sites_table["recording_site"].data) == RECORDING_SITES
        assert "fiber_photometry_table_region" not in recording_sites_table.colnames

    def test_standalone_events_registry_links_to_guppys_own_events(self, interface, nwbfile):
        """The events registry links even with nothing to link to: the onsets are GuPPy's own output.

        The written table is chronological across every event, so the three events' shared onsets
        interleave, and each registry row's region selects its own event's four occurrences.
        """
        module = self.add_to_nwbfile(interface, nwbfile, stub_test=True)

        written_events = nwbfile.events["GuppyEvents"]
        assert list(written_events["timestamp"].data) == [
            onset for onset in MOCK_TRIAL_ONSETS for _ in sorted(EVENT_NAMES)
        ]
        assert list(written_events["event_type"].data) == sorted(EVENT_NAMES) * len(MOCK_TRIAL_ONSETS)

        events_table = module["events"]
        assert events_table.neurodata_type == "GuppyEventsTable"
        registry_event_names = list(events_table["event_name"].data)
        assert registry_event_names == sorted(EVENT_NAMES)
        assert events_table["events"].target.table is written_events
        for row_index, event_name in enumerate(registry_event_names):
            linked = events_table["events"][row_index]
            assert list(linked["event_type"]) == [event_name] * len(MOCK_TRIAL_ONSETS)
            assert list(linked["timestamp"]) == MOCK_TRIAL_ONSETS

    def test_nothing_is_written_to_acquisition(self, interface, nwbfile):
        """GuPPy outputs are derived data; the raw acquisition belongs to a separate interface."""
        self.add_to_nwbfile(interface, nwbfile, stub_test=True)
        assert "guppy" in nwbfile.processing
        assert not nwbfile.acquisition

    def test_round_trip_write_read(self, interface, nwbfile, tmp_path):
        """The standalone object set is self-contained, so it can be written and read back directly."""
        self.add_to_nwbfile(interface, nwbfile, stub_test=True)

        nwbfile_path = tmp_path / "test_guppy.nwb"
        with NWBHDF5IO(str(nwbfile_path), "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            module = io.read().processing["guppy"]
            assert module["recording_sites"].neurodata_type == "GuppyRecordingSitesTable"
            for recording_site in RECORDING_SITES:
                for prefix in TRACE_PREFIXES:
                    series = module.data_interfaces[f"{prefix}_{recording_site}"]
                    assert series.neurodata_type == "GuppyDerivedResponseSeries"
                    assert series.fiber_photometry_table_region is None

    # ------------------------------------------------------------------ caller options

    def test_stub_test_truncates_the_traces(self, interface, nwbfile):
        """stub_test keeps roughly the first second of each derived trace."""
        module = self.add_to_nwbfile(interface, nwbfile, stub_test=True)
        for recording_site in RECORDING_SITES:
            for prefix in TRACE_PREFIXES:
                series = module[f"{prefix}_{recording_site}"]
                assert float(series.data.shape[0] - 1) / series.rate <= 1.01

    def test_regular_timebase_is_written_as_starting_time_and_rate(self, interface, nwbfile):
        module = self.add_to_nwbfile(interface, nwbfile, stub_test=False)
        for recording_site in RECORDING_SITES:
            for prefix in TRACE_PREFIXES:
                series = module[f"{prefix}_{recording_site}"]
                assert series.timestamps is None
                assert float(series.starting_time) == pytest.approx(MOCK_STARTING_TIME)
                assert float(series.rate) == pytest.approx(MOCK_SAMPLING_RATE)

    def test_always_write_timestamps_forces_explicit_timestamps(self, interface, nwbfile):
        """always_write_timestamps=True writes the explicit vector even for a regular timebase."""
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile, metadata, stub_test=False, always_write_timestamps=True)
        series = nwbfile.processing["guppy"]["dff_dms"]
        assert series.rate is None
        np.testing.assert_allclose(series.timestamps[:3], [1.0, 1.005, 1.01])

    # ------------------------------------------------------------------ folder shapes and failures

    def test_trials_binning_mode_yields_integer_bin_edges(self, interface, nwbfile):
        """ "# of trials" binning writes bin_(0-3)-style labels, the complement of the reference session.

        The mock bins four trials three to a bin, so each event contributes a full bin and a short one.
        """
        module = self.add_to_nwbfile(interface, nwbfile, stub_test=False)
        psth = module["psth_dms_dff"]
        np.testing.assert_array_equal(psth.bin_edges[:], BIN_EDGES_PER_EVENT * len(EVENT_NAMES))

    def test_artifact_windows_on_every_site_yield_one_interval_row_each(self, interface, nwbfile):
        """The mock writes the same coords for every site, so each contributes both interval rows."""
        module = self.add_to_nwbfile(interface, nwbfile, stub_test=False)
        intervals = module["valid_signal_intervals"]
        assert intervals.neurodata_type == "GuppyValidSignalIntervals"

        recording_site_names = list(module["recording_sites"]["recording_site"].data)
        grouped = {}
        for start, stop, site_index in zip(
            intervals["start_time"].data, intervals["stop_time"].data, intervals["recording_site"].data
        ):
            grouped.setdefault(recording_site_names[site_index], []).append([start, stop])
        for recording_site in RECORDING_SITES:
            np.testing.assert_allclose(grouped[recording_site], VALID_SIGNAL_INTERVALS)

        # The removal method is recorded once, on GuppyParameters.
        assert nwbfile.lab_meta_data["guppy_parameters"].artifacts_removal_method == "concatenate"

    # ------------------------------------------------------------------ whole-session binning

    def test_binned_metrics_yield_one_row_per_site_bin_and_trace_type(self, interface, nwbfile):
        """Each bin contributes a z-score row and a dF/F row, with the bin's own sample count on both."""
        module = self.add_to_nwbfile(interface, nwbfile, stub_test=False)
        binned = module["binned_metrics"]
        assert binned.neurodata_type == "GuppyBinnedMetrics"
        assert len(binned) == len(RECORDING_SITES) * len(BIN_EDGES) * 2

        recording_site_names = list(module["recording_sites"]["recording_site"].data)
        for recording_site in RECORDING_SITES:
            rows = [
                (label, start, stop, mean, count, n_samples)
                for site_index, label, start, stop, mean, count, n_samples in zip(
                    binned["recording_site"].data,
                    binned["trace_type"].data,
                    binned["start_time"].data,
                    binned["stop_time"].data,
                    binned["mean"].data,
                    binned["transient_count"].data,
                    binned["n_samples"].data,
                )
                if recording_site_names[site_index] == recording_site
            ]
            assert [row[0] for row in rows] == ["z_score", "dff"] * len(BIN_EDGES)
            # The four bins, the last one short because the session does not divide evenly.
            np.testing.assert_allclose([row[1] for row in rows[::2]], [1.0, 1.5, 2.0, 2.5])
            np.testing.assert_allclose([row[2] for row in rows[::2]], [1.5, 2.0, 2.5, 2.995])
            # The mock's trace ramps linearly from -1 to 1 over 400 samples, so a 100-sample bin's mean
            # is the value at its middle sample; dF/F is that scaled by a tenth.
            np.testing.assert_allclose([row[3] for row in rows[::2]], BIN_MEAN_ZSCORE, atol=1e-6)
            np.testing.assert_allclose([row[3] for row in rows[1::2]], np.array(BIN_MEAN_ZSCORE) / 10.0, atol=1e-6)
            # Peaks at 1.2 / 1.5 / 1.8 / 2.5 s, binned half-open with the last bin inclusive.
            np.testing.assert_allclose([row[4] for row in rows[::2]], [1.0, 2.0, 0.0, 1.0])
            assert [row[5] for row in rows[::2]] == [100, 100, 100, 100]

        # The bin width is recorded once, on GuppyParameters.
        assert nwbfile.lab_meta_data["guppy_parameters"].compute_binned_metrics is True
        assert nwbfile.lab_meta_data["guppy_parameters"].binned_metrics_width == 0.5

    def test_binned_covariates_are_on_the_metrics_bins_and_reference_their_series(self, interface, nwbfile):
        """A covariate is averaged onto the metrics' own bins and points at the series it was scored in."""
        module = self.add_to_nwbfile(interface, nwbfile, stub_test=False)
        binned_covariates = module["binned_covariates"]
        assert binned_covariates.neurodata_type == "GuppyBinnedCovariates"
        assert len(binned_covariates) == len(RECORDING_SITES) * len(BIN_EDGES)

        recording_site_names = list(module["recording_sites"]["recording_site"].data)
        for recording_site in RECORDING_SITES:
            rows = [
                (start, stop, mean, n_samples)
                for site_index, start, stop, mean, n_samples in zip(
                    binned_covariates["recording_site"].data,
                    binned_covariates["start_time"].data,
                    binned_covariates["stop_time"].data,
                    binned_covariates["mean"].data,
                    binned_covariates["n_samples"].data,
                )
                if recording_site_names[site_index] == recording_site
            ]
            np.testing.assert_allclose([row[0] for row in rows], [1.0, 1.5, 2.0, 2.5])
            np.testing.assert_allclose([row[1] for row in rows], [1.5, 2.0, 2.5, 2.995])
            # Scores 2.0 / 3.0 / 4.0 / 5.0 at 1.1 / 1.6 / 1.7 / 2.6 s: the third bin holds none.
            np.testing.assert_allclose([row[2] for row in rows], [2.0, 3.5, np.nan, 5.0])
            assert [row[3] for row in rows] == [1, 2, 0, 1]

        # Every row references the one TimeSeries the covariate's scores were written to.
        covariate_series = module[COVARIATE_NAME]
        assert {series.name for series in binned_covariates["covariate"].data} == {COVARIATE_NAME}
        np.testing.assert_allclose(covariate_series.data[:], [2.0, 3.0, 4.0, 5.0])
        np.testing.assert_allclose(covariate_series.timestamps[:], [1.1, 1.6, 1.7, 2.6])

    def test_covariate_correlations_split_guppys_composite_metric_name(self, interface, nwbfile):
        """GuPPy's one metric string becomes the trace_type and metric naming the binned-metrics rows."""
        module = self.add_to_nwbfile(interface, nwbfile, stub_test=False)
        correlations = module["covariate_correlations"]
        assert correlations.neurodata_type == "GuppyCovariateCorrelations"

        recording_site_names = list(module["recording_sites"]["recording_site"].data)
        rows = [
            (trace_type, metric, pearson_r, spearman_rho, n_bins)
            for site_index, trace_type, metric, pearson_r, spearman_rho, n_bins in zip(
                correlations["recording_site"].data,
                correlations["trace_type"].data,
                correlations["metric"].data,
                correlations["pearson_r"].data,
                correlations["spearman_rho"].data,
                correlations["n_bins"].data,
            )
            if recording_site_names[site_index] == RECORDING_SITES[0]
        ]
        # The mock writes the four metric columns in sorted order, with descending coefficients.
        assert [(row[0], row[1]) for row in rows] == [
            ("dff", "mean"),
            ("z_score", "mean"),
            ("dff", "transient_count"),
            ("z_score", "transient_count"),
        ]
        np.testing.assert_allclose([row[2] for row in rows], [0.5, 0.4, 0.3, 0.2])
        np.testing.assert_allclose([row[3] for row in rows], [0.4, 0.3, 0.2, 0.1])
        assert [row[4] for row in rows] == [3, 3, 3, 3]
        assert {series.name for series in correlations["covariate"].data} == {COVARIATE_NAME}
        # GuPPy reports no p-value, so neither does the interface.
        assert "p_value" not in correlations.colnames

    def test_covariate_store_is_not_read_as_an_event(self, interface):
        """A covariate is a store like any other, and must not be taken for a behavioral event."""
        assert interface.event_names == sorted(EVENT_NAMES)
        assert COVARIATE_NAME not in interface.event_names
        assert f"covariate_{COVARIATE_NAME}" not in interface.event_store_to_event_name.values()

    def test_unknown_correlated_metric_fails_loudly(self, guppy_output_folder, tmp_path, nwbfile):
        """A metric the interface cannot map onto a (trace_type, metric) pair is an error, not a guess."""
        copied_folder = tmp_path / "guppy_output_copy"
        shutil.copytree(guppy_output_folder, copied_folder)
        correlations_path = copied_folder / f"covariate_correlations_{RECORDING_SITES[0]}.h5"
        correlations = pandas.read_hdf(correlations_path)
        correlations.loc[0, "metric"] = "median_zscore"
        correlations_path.unlink()
        correlations.to_hdf(correlations_path, key="df", mode="w")

        interface = GuppyInterface(folder_path=str(copied_folder))
        with pytest.raises(AssertionError, match="not a binned-metrics column"):
            self.add_to_nwbfile(interface, nwbfile, stub_test=False)

    def test_no_binning_and_no_covariate_writes_none_of_the_tables(self, tmp_path, nwbfile):
        """A session that ran neither optional step carries neither the tables nor their metadata."""
        folder_path = generate_mock_guppy_output_folder(
            tmp_path / "guppy_output_unbinned", bin_width=None, covariates={}
        )
        interface = GuppyInterface(folder_path=str(folder_path))

        guppy_metadata = interface.get_metadata()["FiberPhotometry"]["Guppy"][interface.metadata_key]
        for key in ("BinnedMetrics", "Covariates", "BinnedCovariates", "CovariateCorrelations"):
            assert key not in guppy_metadata

        module = self.add_to_nwbfile(interface, nwbfile, stub_test=True)
        for name in ("binned_metrics", "binned_covariates", "covariate_correlations", COVARIATE_NAME):
            assert name not in module.data_interfaces
        assert nwbfile.lab_meta_data["guppy_parameters"].compute_binned_metrics is False

    def test_tonic_epochs_yield_one_row_per_site_epoch_and_trace_type(self, interface, nwbfile):
        """Every (recording site, epoch, trace type) is a row carrying that trace's mean over the window."""
        module = self.add_to_nwbfile(interface, nwbfile, stub_test=False)
        tonic_epochs = module["tonic_epochs"]
        assert tonic_epochs.neurodata_type == "GuppyTonicEpochs"
        assert len(tonic_epochs) == len(RECORDING_SITES) * len(TONIC_EPOCHS) * 2

        recording_site_names = list(module["recording_sites"]["recording_site"].data)
        rows = [
            (recording_site_names[site_index], label, start, stop, trace_type, mean)
            for site_index, label, start, stop, trace_type, mean in zip(
                tonic_epochs["recording_site"].data,
                tonic_epochs["label"].data,
                tonic_epochs["start_time"].data,
                tonic_epochs["stop_time"].data,
                tonic_epochs["trace_type"].data,
                tonic_epochs["mean"].data,
            )
        ]
        # The mock writes the same windows for every site, over a trace that ramps linearly from -1 to 1
        # across its 400 samples: the baseline window covers samples 0-200 (mean = the value at sample
        # 100) and post_injection covers samples 200-399 (mean = the value at sample 299.5). dF/F is the
        # z-score mean scaled by a tenth.
        for recording_site in RECORDING_SITES:
            site_rows = [row[1:] for row in rows if row[0] == recording_site]
            assert [row[0] for row in site_rows] == ["baseline"] * 2 + ["post_injection"] * 2
            np.testing.assert_allclose([row[1] for row in site_rows], [1.0, 1.0, 2.0, 2.0])
            np.testing.assert_allclose([row[2] for row in site_rows], [2.0, 2.0, 3.0, 3.0])
            assert [row[3] for row in site_rows] == ["z_score", "dff", "z_score", "dff"]
            np.testing.assert_allclose(
                [row[4] for row in site_rows],
                [-0.498747, -0.0498747, 0.501253, 0.0501253],
                atol=1e-6,
            )

    def test_no_tonic_analysis_writes_no_tonic_epochs(self, tmp_path, nwbfile):
        """A session that never ran the optional tonic analysis has no tonic files, so no object."""
        folder_path = generate_mock_guppy_output_folder(tmp_path / "guppy_output_no_tonic", tonic_epochs=())
        interface = GuppyInterface(folder_path=str(folder_path))

        guppy_metadata = interface.get_metadata()["FiberPhotometry"]["Guppy"][interface.metadata_key]
        assert "TonicEpochs" not in guppy_metadata

        module = self.add_to_nwbfile(interface, nwbfile, stub_test=True)
        assert "tonic_epochs" not in module.data_interfaces

    def test_tonic_outputs_missing_their_pair_is_an_incomplete_folder(self, guppy_output_folder, tmp_path):
        """The epoch windows and their means are written together; one without the other is an error."""
        copied_folder = tmp_path / "guppy_output_copy"
        shutil.copytree(guppy_output_folder, copied_folder)
        (copied_folder / f"tonic_{RECORDING_SITES[0]}.h5").unlink()

        with pytest.raises(AssertionError, match="tonic outputs for recording site"):
            GuppyInterface(folder_path=str(copied_folder))

    def test_cross_correlation_without_bin_columns(self, guppy_output_folder, tmp_path, nwbfile):
        """A GuPPy run with binning disabled writes no bin_ columns, so the bin fields stay unset."""
        copied_folder = tmp_path / "guppy_output_copy"
        shutil.copytree(guppy_output_folder, copied_folder)
        for h5_path in sorted((copied_folder / "cross_correlation_output").glob("corr_*.h5")):
            dataframe = pandas.read_hdf(h5_path)
            dataframe = dataframe.drop(columns=[column for column in dataframe.columns if column.startswith("bin_")])
            h5_path.unlink()
            dataframe.to_hdf(h5_path, key="df", mode="w")

        interface = GuppyInterface(folder_path=str(copied_folder))
        module = self.add_to_nwbfile(interface, nwbfile, stub_test=False)
        for feature in ("dff", "z_score"):
            cross_correlation = module[f"cross_correlation_{feature}_dls_dms"]
            assert cross_correlation.bin_edges is None
            assert cross_correlation.binned_mean is None
            assert cross_correlation.bin_event is None

    def test_missing_parameters_file_raises(self, guppy_output_folder, tmp_path):
        copied_folder = tmp_path / "guppy_output_copy"
        shutil.copytree(guppy_output_folder, copied_folder)
        (copied_folder / "GuPPyParamtersUsed.json").unlink()
        with pytest.raises(AssertionError, match="GuPPyParamtersUsed.json not found"):
            GuppyInterface(folder_path=str(copied_folder))

    # ------------------------------------------------------------------ the onsets GuPPy analyzed

    def test_analyzed_event_onsets_are_read_per_event(self, interface):
        """``<event>_<recording_site>.hdf5`` holds the onsets GuPPy built trials around."""
        assert set(interface.analyzed_event_onsets) == set(EVENT_NAMES)
        for onsets in interface.analyzed_event_onsets.values():
            np.testing.assert_array_equal(onsets, MOCK_TRIAL_ONSETS)

    def test_analyzed_event_onsets_are_a_copy(self, interface):
        """Mutating the returned arrays must not reach back into the interface's own state."""
        interface.analyzed_event_onsets[EVENT_NAMES[0]][0] = -1.0
        np.testing.assert_array_equal(interface.analyzed_event_onsets[EVENT_NAMES[0]], MOCK_TRIAL_ONSETS)

    def test_missing_event_onsets_file_raises(self, guppy_output_folder, tmp_path):
        """GuPPy writes one per event per recording site, so a folder lacking one is incomplete."""
        copied_folder = tmp_path / "guppy_output_copy"
        shutil.copytree(guppy_output_folder, copied_folder)
        (copied_folder / f"{EVENT_NAMES[0]}_{RECORDING_SITES[0]}.hdf5").unlink()
        with pytest.raises(AssertionError, match=f"{EVENT_NAMES[0]}_{RECORDING_SITES[0]}.hdf5 not found"):
            GuppyInterface(folder_path=str(copied_folder))

    def test_recording_sites_disagreeing_on_onsets_raises(self, guppy_output_folder, tmp_path):
        """GuppyEventsTable has one row per event, so a per-site onset list cannot be represented.

        The filter GuPPy applies depends on each site's own recordingStart, so divergence is possible in
        principle; it must surface rather than have the converter silently pick one site's answer.
        """
        copied_folder = tmp_path / "guppy_output_copy"
        shutil.copytree(guppy_output_folder, copied_folder)
        diverging_path = copied_folder / f"{EVENT_NAMES[0]}_{RECORDING_SITES[1]}.hdf5"
        diverging_path.unlink()
        with h5py.File(diverging_path, "w") as onsets_file:
            onsets_file.create_dataset("ts", data=np.array(MOCK_TRIAL_ONSETS[:-1], dtype=np.float64))

        with pytest.raises(AssertionError, match=f"different onsets for event '{EVENT_NAMES[0]}'"):
            GuppyInterface(folder_path=str(copied_folder))
