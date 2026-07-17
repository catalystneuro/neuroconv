import re
import shutil
from datetime import datetime, timezone

import h5py
import numpy as np
import pandas
import pytest
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import _GuppyInterface
from neuroconv.tools.testing import generate_mock_guppy_output_folder


def _column_parses_as_float(column: str) -> bool:
    try:
        float(column)
    except ValueError:
        return False
    return True


_BIN_COLUMN_PATTERN = re.compile(r"^bin_\((\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\)$")
_PREFIX_TO_TRACE_TYPE = dict(cntrl_sig_fit="control_fit", dff="dff", z_score="z_score")


def _resolve_recording_sites(module, dynamic_table_region) -> list[str]:
    """Resolve a recording_site DynamicTableRegion's row indices to GuPPy recording_site names."""
    recording_site_names = list(module["recording_sites"]["recording_site"].data)
    return [recording_site_names[index] for index in dynamic_table_region.data]


def _resolve_events(module, dynamic_table_region) -> list[str]:
    """Resolve an event DynamicTableRegion's row indices to GuPPy event names."""
    event_names = list(module["events"]["event_name"].data)
    return [event_names[index] for index in dynamic_table_region.data]


def _group_by_condition(entries, key_fields, event_order):
    """Group per-event discovery entries by condition, ordering each group by event.

    Mirrors ``_GuppyInterface._group_by_condition``: the event-bearing products emit one object per
    condition with trials concatenated across events in ``event_order`` order, so the tests compare
    against the same grouping.
    """
    groups = {}
    for entry in entries:
        key = tuple(entry[field] for field in key_fields)
        groups.setdefault(key, []).append(entry)
    for entry_list in groups.values():
        entry_list.sort(key=lambda entry: event_order[entry["event"]])
    return groups


class Test_GuppyInterface:
    """Tests for the _GuppyInterface against a synthetically-generated GuPPy output folder.

    The fixture folder is produced on the fly by ``generate_mock_guppy_output_folder`` (a tiny,
    schema-faithful replica of a real GuPPy output), so these tests need no GIN data. The generator
    defaults reproduce the ``Photo_249_391-200721-120136`` topology -- two recording_sites, three events, two
    features -- so the expected recording_site/event/product counts match a real two-recording_site session.
    """

    @pytest.fixture(
        params=[
            pytest.param(
                dict(
                    expected_recording_sites=["dms", "dls"],
                    expected_traces={
                        "dms": ["cntrl_sig_fit", "dff", "z_score"],
                        "dls": ["cntrl_sig_fit", "dff", "z_score"],
                    },
                    expected_transients={"dms": ["z_score", "dff"], "dls": ["z_score", "dff"]},
                    expected_cross_correlations=[
                        {
                            "event_name": "port_entries",
                            "trace_type": "dff",
                            "recording_site_1": "dls",
                            "recording_site_2": "dms",
                        },
                        {
                            "event_name": "port_entries",
                            "trace_type": "z_score",
                            "recording_site_1": "dls",
                            "recording_site_2": "dms",
                        },
                        {
                            "event_name": "rewarded_nose_pokes",
                            "trace_type": "dff",
                            "recording_site_1": "dls",
                            "recording_site_2": "dms",
                        },
                        {
                            "event_name": "rewarded_nose_pokes",
                            "trace_type": "z_score",
                            "recording_site_1": "dls",
                            "recording_site_2": "dms",
                        },
                        {
                            "event_name": "unrewarded_nose_pokes",
                            "trace_type": "dff",
                            "recording_site_1": "dls",
                            "recording_site_2": "dms",
                        },
                        {
                            "event_name": "unrewarded_nose_pokes",
                            "trace_type": "z_score",
                            "recording_site_1": "dls",
                            "recording_site_2": "dms",
                        },
                    ],
                    expected_psth_count=24,  # 3 events x 2 recording_sites x 2 features x {corrected, uncorrected}
                    expected_peak_auc_count=12,  # 3 events x 2 recording_sites x 2 features
                    expected_session_start_time=datetime(2018, 10, 30, 15, 33, 54, tzinfo=timezone.utc),
                    # The mock writes the same coordsForPreProcessing windows for every recording_site; with no
                    # temporal alignment the offset is 0, so the aligned intervals equal the source.
                    expected_valid_signal_intervals={
                        "dms": [[1.25, 1.75], [2.0, 2.5]],
                        "dls": [[1.25, 1.75], [2.0, 2.5]],
                    },
                    expected_event_store_to_event_name={
                        "LNRW": "rewarded_nose_pokes",
                        "LNnR": "unrewarded_nose_pokes",
                        "PrtR": "port_entries",
                    },
                    # Signal store id per recording site, from the default mock TDT topology.
                    expected_recording_site_to_store_id={"dms": "Dv2A", "dls": "Dv4B"},
                ),
                id="mock_isosbestic_two_recording_sites",
            ),
        ]
    )
    def case(self, request, tmp_path):
        case = dict(request.param)
        case["folder_path"] = generate_mock_guppy_output_folder(tmp_path / "guppy_output")
        return case

    @pytest.fixture
    def interface(self, case):
        return _GuppyInterface(folder_path=str(case["folder_path"]))

    @pytest.fixture
    def nwbfile(self):
        """A plain NWBFile. _GuppyInterface is standalone: it needs no acquisition/events tables to write
        (the two registry links are populated later by a converter that owns those tables)."""
        return mock_NWBFile()

    def _add(self, interface, nwbfile, *, stub_test):
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile, metadata, stub_test=stub_test)
        return nwbfile.processing["fiber_photometry"]

    # ----------------------------------------------------------------- discovery / metadata

    def test_discovery(self, interface, case):
        assert interface._recording_sites == case["expected_recording_sites"]
        assert interface._traces_by_recording_site == case["expected_traces"]
        assert interface._transients_by_recording_site == case["expected_transients"]

    def test_discovery_event_store_to_event_name(self, interface, case):
        assert interface._event_store_to_event_name == case["expected_event_store_to_event_name"]

    def test_discovery_psths_and_peak_aucs(self, interface, case):
        assert len(interface._psths) == case["expected_psth_count"]
        assert len(interface._peak_aucs) == case["expected_peak_auc_count"]

    def test_metadata_session_start_time(self, interface, case):
        metadata = interface.get_metadata()
        if case["expected_session_start_time"] is None:
            assert metadata["NWBFile"].get("session_start_time") in (None, "")
        else:
            assert metadata["NWBFile"]["session_start_time"] == case["expected_session_start_time"]

    def test_metadata_session_start_time_unset_when_time_rec_start_absent(self, case, tmp_path):
        copied_folder = tmp_path / "guppy_output_copy"
        shutil.copytree(case["folder_path"], copied_folder)
        for recording_site in case["expected_recording_sites"]:
            with h5py.File(copied_folder / f"timeCorrection_{recording_site}.hdf5", "r+") as time_correction_file:
                del time_correction_file["timeRecStart"]

        interface = _GuppyInterface(folder_path=str(copied_folder))
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") in (None, "")

    def test_discovery_cross_correlations(self, interface, case):
        actual = sorted(
            (
                {
                    "event_name": entry["event"],
                    "trace_type": entry["feature"],
                    "recording_site_1": entry["recording_site_1"],
                    "recording_site_2": entry["recording_site_2"],
                }
                for entry in interface._cross_correlations
            ),
            key=lambda entry: (entry["event_name"], entry["trace_type"]),
        )
        expected = sorted(
            case["expected_cross_correlations"], key=lambda entry: (entry["event_name"], entry["trace_type"])
        )
        assert actual == expected

    def test_metadata_enumerates_all_products(self, interface, case):
        """get_metadata is a full manifest: every product family GuPPy emits appears, each a dict keyed
        by the object's default name."""
        guppy_metadata = interface.get_metadata()["FiberPhotometry"]["Guppy"]
        assert set(guppy_metadata.keys()) == {
            "ProcessingModule",
            "Traces",
            "Transients",
            "TransientSummary",
            "CrossCorrelations",
            "PSTHs",
            "PeakAUCs",
        }
        expected_cross_correlation_names = {
            f"cross_correlation_{entry['trace_type']}_{entry['recording_site_1']}_{entry['recording_site_2']}"
            for entry in case["expected_cross_correlations"]
        }
        assert set(guppy_metadata["CrossCorrelations"].keys()) == expected_cross_correlation_names
        assert len(guppy_metadata["PSTHs"]) == case["expected_psth_count"] // len(interface._event_names)
        assert len(guppy_metadata["PeakAUCs"]) == case["expected_peak_auc_count"] // len(interface._event_names)

    def test_metadata_processing_module_includes_guppy_version(self, interface):
        metadata = interface.get_metadata()
        description = metadata["FiberPhotometry"]["Guppy"]["ProcessingModule"]["description"]
        assert "(GuPPy version 2.0.0a7)" in description

    def test_metadata_traces_and_transients(self, interface, case):
        metadata = interface.get_metadata()
        guppy_metadata = metadata["FiberPhotometry"]["Guppy"]

        # Families are dicts keyed by the derived object name.
        expected_trace_names = {
            f"{prefix}_{recording_site}"
            for recording_site, prefixes in case["expected_traces"].items()
            for prefix in prefixes
        }
        assert set(guppy_metadata["Traces"].keys()) == expected_trace_names

        expected_transient_names = {
            f"transients_{recording_site}_{feature}"
            for recording_site, features in case["expected_transients"].items()
            for feature in features
        }
        assert set(guppy_metadata["Transients"].keys()) == expected_transient_names

    def test_metadata_entries_expose_name_and_description_only(self, interface):
        """Every product entry carries exactly the editable name + description (name defaults to the key).
        No internal handles (recording_site, trace_basename, trace_type, recording_site pair, event lists) and no derived
        unit ever appear in the metadata."""
        guppy_metadata = interface.get_metadata()["FiberPhotometry"]["Guppy"]
        for family in ("Traces", "Transients", "CrossCorrelations", "PSTHs", "PeakAUCs"):
            for name, entry in guppy_metadata[family].items():
                assert set(entry.keys()) == {"name", "description"}, (family, entry)
                assert entry["name"] == name  # default name is the key

    def test_metadata_key_scopes_block_and_edits_propagate(self, case, nwbfile):
        """A non-default metadata_key scopes the whole block; editing an object's name and description
        propagates to the written object -- including an event-bearing product (PSTH)."""
        interface = _GuppyInterface(folder_path=str(case["folder_path"]), metadata_key="GuppyB")
        metadata = interface.get_metadata()
        assert "GuppyB" in metadata["FiberPhotometry"]
        assert "Guppy" not in metadata["FiberPhotometry"]

        guppy_block = metadata["FiberPhotometry"]["GuppyB"]
        trace_tag = next(iter(guppy_block["Traces"]))
        guppy_block["Traces"][trace_tag]["name"] = "renamed_trace"
        guppy_block["Traces"][trace_tag]["description"] = "custom trace description"
        psth_tag = next(iter(guppy_block["PSTHs"]))
        guppy_block["PSTHs"][psth_tag]["description"] = "custom psth description"

        interface.add_to_nwbfile(nwbfile, metadata, stub_test=True)
        module = nwbfile.processing["fiber_photometry"]
        assert "renamed_trace" in module.data_interfaces  # rename took effect
        assert module["renamed_trace"].description == "custom trace description"
        assert module[psth_tag].description == "custom psth description"  # description reaches group products

    # ----------------------------------------------------------------- registries / parameters

    def test_registries(self, interface, case, nwbfile):
        module = self._add(interface, nwbfile, stub_test=True)

        # The registries are slim: names only. Their outward links (fiber rows, events rows) are left
        # unpopulated by the interface -- a converter fills them in later.
        recording_sites_table = module["recording_sites"]
        assert recording_sites_table.neurodata_type == "GuppyRecordingSitesTable"
        assert list(recording_sites_table["recording_site"].data) == case["expected_recording_sites"]
        assert "fiber_photometry_table_region" not in recording_sites_table.colnames

        events_table = module["events"]
        assert events_table.neurodata_type == "GuppyEventsTable"
        assert sorted(events_table["event_name"].data) == sorted(case["expected_event_store_to_event_name"].values())
        assert "events" not in events_table.colnames

    def test_parameters(self, interface, case, nwbfile):
        self._add(interface, nwbfile, stub_test=True)
        parameters = nwbfile.lab_meta_data["guppy_parameters"]
        assert parameters.neurodata_type == "GuppyParameters"
        assert parameters.guppy_version == "2.0.0a7"
        # zscore_method is present in the fixture parameters file.
        assert parameters.zscore_method is not None

    # ----------------------------------------------------------------- products land as ndx-guppy types

    def test_add_to_nwbfile_lands_in_processing_module(self, interface, case, nwbfile):
        module = self._add(interface, nwbfile, stub_test=True)
        assert "fiber_photometry" in nwbfile.processing
        assert not nwbfile.acquisition, "GuPPy interface must not write to /acquisition/."

        for recording_site, prefixes in case["expected_traces"].items():
            for prefix in prefixes:
                series = module[f"{prefix}_{recording_site}"]
                assert series.neurodata_type == "GuppyDerivedResponseSeries"
                assert series.trace_type == _PREFIX_TO_TRACE_TYPE[prefix]
                # Fiber provenance is reached through the recording-site row, not stamped on the series.
                assert series.fiber_photometry_table_region is None
                assert _resolve_recording_sites(module, series.recording_site) == [recording_site]
                # The regular GuPPy timebase is written as starting_time + rate, not an explicit vector.
                assert series.timestamps is None
                assert series.rate is not None
                assert float(series.data.shape[0] - 1) / series.rate <= 1.01  # stub keeps ~1 s

        for recording_site, features in case["expected_transients"].items():
            for feature in features:
                table = module[f"transients_{recording_site}_{feature}"]
                assert table.neurodata_type == "GuppyTransientsTable"
                assert table.trace_type == feature
                assert "timestamp" in table.colnames and "amplitude" in table.colnames
                if len(table) > 0:
                    assert set(_resolve_recording_sites(module, table["recording_site"])) == {recording_site}

        assert module["transient_summary"].neurodata_type == "GuppyTransientSummaryTable"

        # Each event-bearing product is one object per condition, with trials concatenated across
        # events: the per-trial 'event' reference labels every trials column, while 'summary_event'
        # has one row per event (matching the columns of 'mean'/'mean_*').
        event_order = {name: index for index, name in enumerate(interface._event_names)}

        cross_correlation_groups = _group_by_condition(
            interface._cross_correlations, ("feature", "recording_site_1", "recording_site_2"), event_order
        )
        for (feature, recording_site_1, recording_site_2), entries in cross_correlation_groups.items():
            cross_correlation = module[f"cross_correlation_{feature}_{recording_site_1}_{recording_site_2}"]
            expected_events = [entry["event"] for entry in entries]
            assert cross_correlation.neurodata_type == "GuppyCrossCorrelation"
            assert cross_correlation.trace_type == feature
            assert cross_correlation.trials.shape[0] == cross_correlation.lag.shape[0]  # lag-first
            assert cross_correlation.trials.shape[1] == cross_correlation.trial_onset_times.shape[0]
            assert cross_correlation.trials.shape[1] == len(cross_correlation.event.data)  # per-trial event labels
            assert cross_correlation.mean.shape[1] == len(expected_events)  # one summary column per event
            assert _resolve_recording_sites(module, cross_correlation.recording_site) == [
                recording_site_1,
                recording_site_2,
            ]
            assert _resolve_events(module, cross_correlation.summary_event) == expected_events
            assert set(_resolve_events(module, cross_correlation.event)) == set(expected_events)

        psth_groups = _group_by_condition(
            interface._psths, ("recording_site", "feature", "baseline_corrected"), event_order
        )
        for (recording_site, feature, baseline_corrected), entries in psth_groups.items():
            suffix = "" if baseline_corrected else "_baseline_uncorrected"
            psth = module[f"psth_{recording_site}_{feature}{suffix}"]
            expected_events = [entry["event"] for entry in entries]
            assert psth.neurodata_type == "GuppyPSTH"
            assert psth.trace_type == feature
            assert bool(psth.baseline_corrected) == baseline_corrected
            assert psth.traces.shape[0] == psth.peri_event_time.shape[0]  # time-first
            assert psth.traces.shape[1] == len(psth.event.data)  # per-trial event labels
            assert psth.mean.shape[1] == len(expected_events)  # one summary column per event
            assert _resolve_recording_sites(module, psth.recording_site) == [recording_site]
            assert _resolve_events(module, psth.summary_event) == expected_events

        peak_auc_groups = _group_by_condition(interface._peak_aucs, ("recording_site", "feature"), event_order)
        for (recording_site, feature), entries in peak_auc_groups.items():
            peak_auc = module[f"peak_auc_{recording_site}_{feature}"]
            expected_events = [entry["event"] for entry in entries]
            assert peak_auc.neurodata_type == "GuppyPeakAUC"
            assert peak_auc.peak_positive.shape[0] == peak_auc.window_start.shape[0]  # window-first
            assert peak_auc.peak_positive.shape[1] == peak_auc.trial_onset_times.shape[0]
            assert peak_auc.mean_peak_positive.shape[1] == len(expected_events)  # one summary column per event
            assert _resolve_recording_sites(module, peak_auc.recording_site) == [recording_site]
            assert _resolve_events(module, peak_auc.summary_event) == expected_events

    # ----------------------------------------------------------------- products match their source files

    def test_transients_table_row_count_matches_csv(self, interface, case, nwbfile):
        module = self._add(interface, nwbfile, stub_test=False)
        for recording_site, features in case["expected_transients"].items():
            for feature in features:
                csv_path = case["folder_path"] / f"transientsOccurrences_{feature}_{recording_site}.csv"
                expected_count = len(pandas.read_csv(csv_path))
                table = module[f"transients_{recording_site}_{feature}"]
                assert len(table["timestamp"]) == expected_count
                assert len(table["amplitude"]) == expected_count

    def test_transient_summary_matches_freq_amp(self, interface, case, nwbfile):
        module = self._add(interface, nwbfile, stub_test=False)
        summary = module["transient_summary"]

        expected_rows = []
        for recording_site, features in case["expected_transients"].items():
            for feature in features:
                freq_amp_path = case["folder_path"] / f"freqAndAmp_{feature}_{recording_site}.h5"
                if not freq_amp_path.is_file():
                    continue
                dataframe = pandas.read_hdf(freq_amp_path)
                expected_rows.append(
                    (
                        recording_site,
                        feature,
                        float(dataframe["freq (events/min)"].iloc[0]),
                        float(dataframe["amplitude"].iloc[0]),
                    )
                )

        actual_rows = list(
            zip(
                _resolve_recording_sites(module, summary["recording_site"]),
                summary["trace_type"].data,
                summary["frequency_per_min"].data,
                summary["mean_amplitude"].data,
            )
        )
        assert actual_rows == expected_rows

    def test_cross_correlation_matches_source(self, interface, case, nwbfile):
        module = self._add(interface, nwbfile, stub_test=False)
        event_order = {name: index for index, name in enumerate(interface._event_names)}
        # The object for one condition concatenates its events' trials/bins; compare against the same
        # concatenation of the per-event source files.
        for (feature, recording_site_1, recording_site_2), entries in _group_by_condition(
            interface._cross_correlations, ("feature", "recording_site_1", "recording_site_2"), event_order
        ).items():
            cross_correlation = module[f"cross_correlation_{feature}_{recording_site_1}_{recording_site_2}"]
            trials_blocks, onset_values, mean_blocks = [], [], []
            bin_edges_blocks, binned_mean_blocks = [], []
            for entry in entries:
                source = pandas.read_hdf(entry["path"])
                np.testing.assert_array_equal(cross_correlation.lag[:], source["timestamps"].to_numpy(dtype=np.float64))
                trial_columns = [column for column in source.columns if _column_parses_as_float(column)]
                trials_blocks.append(source[trial_columns].to_numpy(dtype=np.float64))
                onset_values.extend(float(column) for column in trial_columns)
                mean_blocks.append(source["mean"].to_numpy(dtype=np.float64))
                bin_columns = sorted(
                    (float(match.group(1)), float(match.group(2)), match.string)
                    for match in (_BIN_COLUMN_PATTERN.match(column) for column in source.columns)
                    if match is not None
                )
                if bin_columns:
                    bin_edges_blocks.append(
                        np.array([[start, stop] for start, stop, _ in bin_columns], dtype=np.float64)
                    )
                    binned_mean_blocks.append(
                        np.stack([source[column].to_numpy(dtype=np.float64) for _, _, column in bin_columns], axis=1)
                    )
            np.testing.assert_array_equal(cross_correlation.trials[:], np.concatenate(trials_blocks, axis=1))
            np.testing.assert_array_equal(cross_correlation.trial_onset_times[:], np.array(onset_values))
            np.testing.assert_array_equal(cross_correlation.mean[:], np.stack(mean_blocks, axis=1))
            if bin_edges_blocks:
                np.testing.assert_array_equal(cross_correlation.bin_edges[:], np.concatenate(bin_edges_blocks, axis=0))
                np.testing.assert_array_equal(
                    cross_correlation.binned_mean[:], np.concatenate(binned_mean_blocks, axis=1)
                )

    def test_psth_matches_source(self, interface, case, nwbfile):
        module = self._add(interface, nwbfile, stub_test=False)
        event_order = {name: index for index, name in enumerate(interface._event_names)}
        # no-op for fixtures without PSTH files
        for (recording_site, feature, baseline_corrected), entries in _group_by_condition(
            interface._psths, ("recording_site", "feature", "baseline_corrected"), event_order
        ).items():
            suffix = "" if baseline_corrected else "_baseline_uncorrected"
            psth = module[f"psth_{recording_site}_{feature}{suffix}"]
            traces_blocks, mean_blocks = [], []
            for entry in entries:
                source = pandas.read_hdf(entry["path"])
                np.testing.assert_array_equal(psth.peri_event_time[:], source["timestamps"].to_numpy(dtype=np.float64))
                trial_columns = [column for column in source.columns if _column_parses_as_float(column)]
                traces_blocks.append(source[trial_columns].to_numpy(dtype=np.float64))
                mean_blocks.append(source["mean"].to_numpy(dtype=np.float64))
            np.testing.assert_array_equal(psth.traces[:], np.concatenate(traces_blocks, axis=1))
            np.testing.assert_array_equal(psth.mean[:], np.stack(mean_blocks, axis=1))

    def test_peak_auc_matches_source(self, interface, case, nwbfile):
        module = self._add(interface, nwbfile, stub_test=False)
        event_order = {name: index for index, name in enumerate(interface._event_names)}
        for (recording_site, feature), entries in _group_by_condition(
            interface._peak_aucs, ("recording_site", "feature"), event_order
        ).items():
            peak_auc = module[f"peak_auc_{recording_site}_{feature}"]
            # mean_peak_positive is (num_windows, num_events): one column per event's across-trial mean.
            expected_mean_columns = []
            for entry in entries:
                source = pandas.read_hdf(entry["path"])
                window_count = sum(1 for column in source.columns if str(column).startswith("peak_pos_"))
                mean_row = next(str(index) for index in source.index if str(index).endswith("mean"))
                expected_mean_columns.append(
                    np.array([float(source.loc[mean_row, f"peak_pos_{window + 1}"]) for window in range(window_count)])
                )
            np.testing.assert_array_equal(peak_auc.mean_peak_positive[:], np.stack(expected_mean_columns, axis=1))
            start_points = np.asarray(interface._guppy_parameters["peak_startPoint"], dtype=np.float64)
            np.testing.assert_array_equal(peak_auc.window_start[:], start_points[~np.isnan(start_points)])

    def _valid_intervals_by_recording_site(self, module):
        """Group the GuppyValidSignalIntervals rows (start, stop) by their recording-site reference."""
        intervals_object = module["valid_signal_intervals"]
        assert intervals_object.neurodata_type == "GuppyValidSignalIntervals"
        recording_site_names = list(module["recording_sites"]["recording_site"].data)
        grouped = {}
        for start, stop, site_index in zip(
            intervals_object["start_time"].data,
            intervals_object["stop_time"].data,
            intervals_object["recording_site"].data,
        ):
            grouped.setdefault(recording_site_names[site_index], []).append([start, stop])
        return grouped

    def test_valid_signal_intervals_match_source(self, interface, case, nwbfile):
        module = self._add(interface, nwbfile, stub_test=False)

        expected = case["expected_valid_signal_intervals"]
        # Valid-signal intervals are their own GuppyValidSignalIntervals object, one row per interval,
        # each referencing its recording site (not a ragged column on the recording_sites registry).
        if not expected:
            assert "valid_signal_intervals" not in module.data_interfaces
            return

        actual = self._valid_intervals_by_recording_site(module)
        for recording_site, expected_intervals in expected.items():
            np.testing.assert_allclose(actual[recording_site], expected_intervals)
        # The removal method is recorded once on GuppyParameters.
        assert nwbfile.lab_meta_data["guppy_parameters"].artifacts_removal_method == "concatenate"

    def test_cross_correlation_without_psth_bin_columns(self, case, tmp_path, nwbfile):
        copied_folder = tmp_path / "guppy_output_copy"
        shutil.copytree(case["folder_path"], copied_folder)
        cross_correlation_folder = copied_folder / "cross_correlation_output"
        if cross_correlation_folder.is_dir():
            for h5_path in sorted(cross_correlation_folder.glob("corr_*.h5")):
                dataframe = pandas.read_hdf(h5_path)
                bin_columns = [column for column in dataframe.columns if column.startswith("bin_")]
                dataframe = dataframe.drop(columns=bin_columns)
                h5_path.unlink()
                dataframe.to_hdf(h5_path, key="df", mode="w")

        interface = _GuppyInterface(folder_path=str(copied_folder))
        module = self._add(interface, nwbfile, stub_test=False)
        event_order = {name: index for index, name in enumerate(interface._event_names)}
        for feature, recording_site_1, recording_site_2 in _group_by_condition(
            interface._cross_correlations, ("feature", "recording_site_1", "recording_site_2"), event_order
        ):
            cross_correlation = module[f"cross_correlation_{feature}_{recording_site_1}_{recording_site_2}"]
            assert cross_correlation.bin_edges is None
            assert cross_correlation.binned_mean is None
            assert cross_correlation.bin_event is None

    # ----------------------------------------------------------------- alignment / roundtrip / errors

    def test_aligned_starting_time_shifts_traces_and_transients(self, interface, case, nwbfile):
        first_recording_site = case["expected_recording_sites"][0]
        original_first_timestamp = float(interface.get_original_timestamps()[first_recording_site][0])

        offset = 12.34
        interface.set_aligned_starting_time(offset)
        module = self._add(interface, nwbfile, stub_test=False)

        first_trace_name = f"{case['expected_traces'][first_recording_site][0]}_{first_recording_site}"
        # The regular timebase stays regular under a constant shift, so it is written as starting_time + rate.
        assert float(module[first_trace_name].starting_time) == pytest.approx(original_first_timestamp + offset)

        for recording_site, features in case["expected_transients"].items():
            for feature in features:
                csv_path = case["folder_path"] / f"transientsOccurrences_{feature}_{recording_site}.csv"
                expected_first_peak = float(pandas.read_csv(csv_path)["timestamps"].iloc[0]) + offset
                table = module[f"transients_{recording_site}_{feature}"]
                assert table["timestamp"][0] == pytest.approx(expected_first_peak)

        if case["expected_valid_signal_intervals"]:
            actual = self._valid_intervals_by_recording_site(module)
            for recording_site, expected_intervals in case["expected_valid_signal_intervals"].items():
                expected_shifted = np.asarray(expected_intervals, dtype=float) + offset
                np.testing.assert_allclose(actual[recording_site], expected_shifted)

    def test_round_trip_write_read(self, interface, case, nwbfile, tmp_path):
        # _GuppyInterface is standalone: it writes a self-contained set of ndx-guppy objects, so the
        # mock file can be written and read directly.
        self._add(interface, nwbfile, stub_test=True)

        nwbfile_path = tmp_path / "test_guppy.nwb"
        with NWBHDF5IO(str(nwbfile_path), "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            module = nwbfile.processing["fiber_photometry"]
            recording_sites_table = module["recording_sites"]
            assert recording_sites_table.neurodata_type == "GuppyRecordingSitesTable"
            # Valid-signal intervals round-trip as their own GuppyValidSignalIntervals object.
            if case["expected_valid_signal_intervals"]:
                actual = self._valid_intervals_by_recording_site(module)
                for recording_site, expected_intervals in case["expected_valid_signal_intervals"].items():
                    np.testing.assert_allclose(actual[recording_site], expected_intervals)
            for recording_site, prefixes in case["expected_traces"].items():
                for prefix in prefixes:
                    series = module.data_interfaces[f"{prefix}_{recording_site}"]
                    assert series.neurodata_type == "GuppyDerivedResponseSeries"
                    assert series.trace_type == _PREFIX_TO_TRACE_TYPE[prefix]
                    assert series.fiber_photometry_table_region is None
            for entry in case["expected_cross_correlations"]:
                name = (
                    f"cross_correlation_{entry['trace_type']}_{entry['recording_site_1']}_{entry['recording_site_2']}"
                )
                assert module.data_interfaces[name].neurodata_type == "GuppyCrossCorrelation"
            assert nwbfile.lab_meta_data["guppy_parameters"].neurodata_type == "GuppyParameters"

    def test_derived_response_series_uses_starting_time_and_rate(self, interface, case, nwbfile):
        """The regular mock timebase (1.0 + arange(n) / 200 Hz) is written as starting_time + rate."""
        module = self._add(interface, nwbfile, stub_test=False)
        for recording_site, prefixes in case["expected_traces"].items():
            for prefix in prefixes:
                series = module[f"{prefix}_{recording_site}"]
                assert series.timestamps is None
                assert float(series.starting_time) == pytest.approx(1.0)
                assert float(series.rate) == pytest.approx(200.0)

    def test_always_write_timestamps_forces_explicit_timestamps(self, interface, case, nwbfile):
        """always_write_timestamps=True writes the explicit timestamps vector even for a regular timebase."""
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(nwbfile, metadata, stub_test=False, always_write_timestamps=True)
        module = nwbfile.processing["fiber_photometry"]
        first_recording_site = case["expected_recording_sites"][0]
        first_trace_name = f"{case['expected_traces'][first_recording_site][0]}_{first_recording_site}"
        series = module[first_trace_name]
        assert series.rate is None
        np.testing.assert_allclose(series.timestamps[:3], [1.0, 1.005, 1.01])

    # ----------------------------------------------------------------- warnings / construction errors

    def test_missing_parameters_file_raises(self, case, tmp_path):
        copied_folder = tmp_path / "guppy_output_copy"
        shutil.copytree(case["folder_path"], copied_folder)
        (copied_folder / "GuPPyParamtersUsed.json").unlink()
        with pytest.raises(AssertionError, match="GuPPyParamtersUsed.json not found"):
            _GuppyInterface(folder_path=str(copied_folder))
