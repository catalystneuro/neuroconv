import json
import re
import shutil
from datetime import datetime, timezone

import h5py
import numpy as np
import pandas
import pytest
from ndx_events import Events
from ndx_fiber_photometry import (
    FiberPhotometry,
    FiberPhotometryIndicators,
    FiberPhotometryTable,
)
from ndx_ophys_devices import (
    ExcitationSource,
    FiberInsertion,
    Indicator,
    OpticalFiber,
    Photodetector,
)
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import GuppyInterface

from ..setup_paths import OPHYS_DATA_PATH


def _column_parses_as_float(column: str) -> bool:
    try:
        float(column)
    except ValueError:
        return False
    return True


_BIN_COLUMN_PATTERN = re.compile(r"^bin_\((\d+)-(\d+)\)$")
_PREFIX_TO_TRACE_TYPE = dict(cntrl_sig_fit="control_fit", dff="dff", z_score="z_score")

GUPPY_DATA_PATH = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT" / "Photo_63_207-181030-103332"


def _resolve_regions(module, dynamic_table_region) -> list[str]:
    """Resolve a region DynamicTableRegion's row indices to GuPPy region names."""
    region_names = list(module["regions"]["region"].data)
    return [region_names[index] for index in dynamic_table_region.data]


def _resolve_events(module, dynamic_table_region) -> list[str]:
    """Resolve an event DynamicTableRegion's row indices to GuPPy event names."""
    event_names = list(module["events"]["event_name"].data)
    return [event_names[index] for index in dynamic_table_region.data]


class TestGuppyInterface:
    """Tests for the GuppyInterface against the standard GuPPy fixture set."""

    @pytest.fixture(
        params=[
            pytest.param(
                dict(
                    folder_path=GUPPY_DATA_PATH / "Photo_63_207-181030-103332_output_1",
                    expected_regions=["dms", "dls"],
                    expected_traces={
                        "dms": ["cntrl_sig_fit", "dff", "z_score"],
                        "dls": ["cntrl_sig_fit", "dff", "z_score"],
                    },
                    expected_transients={"dms": ["z_score", "dff"], "dls": ["z_score", "dff"]},
                    expected_cross_correlations=[
                        {"event_name": "port_entries", "trace_type": "dff", "region_1": "dls", "region_2": "dms"},
                        {"event_name": "port_entries", "trace_type": "z_score", "region_1": "dls", "region_2": "dms"},
                        {
                            "event_name": "rewarded_nose_pokes",
                            "trace_type": "dff",
                            "region_1": "dls",
                            "region_2": "dms",
                        },
                        {
                            "event_name": "rewarded_nose_pokes",
                            "trace_type": "z_score",
                            "region_1": "dls",
                            "region_2": "dms",
                        },
                        {
                            "event_name": "unrewarded_nose_pokes",
                            "trace_type": "dff",
                            "region_1": "dls",
                            "region_2": "dms",
                        },
                        {
                            "event_name": "unrewarded_nose_pokes",
                            "trace_type": "z_score",
                            "region_1": "dls",
                            "region_2": "dms",
                        },
                    ],
                    expected_psth_count=24,  # 3 events x 2 regions x 2 features x {corrected, uncorrected}
                    expected_peak_auc_count=12,  # 3 events x 2 regions x 2 features
                    expected_session_start_time=datetime(2018, 10, 30, 15, 33, 54, tzinfo=timezone.utc),
                    expected_valid_signal_intervals=[],
                    expected_event_store_to_event_name={
                        "LNRW": "rewarded_nose_pokes",
                        "LNnR": "unrewarded_nose_pokes",
                        "PrtN": "port_entries",
                    },
                ),
                id="tdt_isosbestic_two_regions",
            ),
            pytest.param(
                dict(
                    folder_path=GUPPY_DATA_PATH / "Photo_63_207-181030-103332_output_2",
                    expected_regions=["dms"],
                    expected_traces={"dms": ["cntrl_sig_fit", "dff", "z_score"]},
                    expected_transients={"dms": ["z_score"]},
                    expected_cross_correlations=[],
                    expected_psth_count=0,
                    expected_peak_auc_count=0,
                    expected_session_start_time=datetime(2018, 10, 30, 15, 33, 54, tzinfo=timezone.utc),
                    expected_valid_signal_intervals=[
                        ("dms", 3.93579108, 18.51639376),
                        ("dms", 40.04014057, 154.60201876),
                    ],
                    expected_event_store_to_event_name={},
                ),
                id="tdt_isosbestic_one_region_artifacts_removed",
            ),
        ]
    )
    def case(self, request):
        case = dict(request.param)
        assert case[
            "folder_path"
        ].is_dir(), f"Test data missing at {case['folder_path']}. Place the GuPPy fixture set under {GUPPY_DATA_PATH}."
        return case

    @pytest.fixture
    def interface(self, case):
        return GuppyInterface(folder_path=str(case["folder_path"]))

    @pytest.fixture
    def region_to_indices(self, case):
        """Two acquisition table rows per region (signal + isosbestic control), in region order."""
        return {region: [2 * i, 2 * i + 1] for i, region in enumerate(case["expected_regions"])}

    @pytest.fixture
    def linked_nwbfile(self, case):
        """A mock NWBFile pre-populated with an acquisition ``FiberPhotometryTable``.

        ``GuppyInterface`` is non-standalone: the derived traces are ``FiberPhotometryResponseSeries``
        whose ``fiber_photometry_table_region`` is their defining provenance, so tests must supply that
        table. Two rows per region mirror the signal + isosbestic control fibers a region is computed
        from.
        """
        nwbfile = mock_NWBFile()
        indicator = Indicator(name="indicator", label="GCaMP")
        optical_fiber = OpticalFiber(name="optical_fiber", fiber_insertion=FiberInsertion(name="fiber_insertion"))
        excitation_source = ExcitationSource(name="excitation_source")
        photodetector = Photodetector(name="photodetector")
        for device in (optical_fiber, excitation_source, photodetector):
            nwbfile.add_device(device)
        table = FiberPhotometryTable(name="fiber_photometry_table", description="Acquisition fiber photometry table.")
        for region in case["expected_regions"]:
            for excitation_wavelength_in_nm in (465.0, 405.0):  # signal then isosbestic-control row
                table.add_row(
                    location=region.upper(),
                    excitation_wavelength_in_nm=excitation_wavelength_in_nm,
                    emission_wavelength_in_nm=525.0,
                    indicator=indicator,
                    optical_fiber=optical_fiber,
                    excitation_source=excitation_source,
                    photodetector=photodetector,
                )
        nwbfile.add_lab_meta_data(
            FiberPhotometry(
                name="fiber_photometry",
                fiber_photometry_table=table,
                fiber_photometry_indicators=FiberPhotometryIndicators(indicators=[indicator]),
            )
        )
        return nwbfile

    def _add(self, interface, nwbfile, region_to_indices, *, stub_test):
        metadata = interface.get_metadata()
        interface.add_to_nwbfile(
            nwbfile, metadata, fiber_photometry_table_region_indices=region_to_indices, stub_test=stub_test
        )
        return nwbfile.processing["fiber_photometry"]

    # ----------------------------------------------------------------- discovery / metadata

    def test_discovery(self, interface, case):
        assert interface.regions == case["expected_regions"]
        assert interface.traces_by_region == case["expected_traces"]
        assert interface.transients_by_region == case["expected_transients"]

    def test_discovery_event_store_to_event_name(self, interface, case):
        assert interface.event_store_to_event_name == case["expected_event_store_to_event_name"]

    def test_discovery_psths_and_peak_aucs(self, interface, case):
        assert len(interface.psths) == case["expected_psth_count"]
        assert len(interface.peak_aucs) == case["expected_peak_auc_count"]

    def test_metadata_session_start_time(self, interface, case):
        metadata = interface.get_metadata()
        if case["expected_session_start_time"] is None:
            assert metadata["NWBFile"].get("session_start_time") in (None, "")
        else:
            assert metadata["NWBFile"]["session_start_time"] == case["expected_session_start_time"]

    def test_metadata_session_start_time_unset_when_time_rec_start_absent(self, case, tmp_path):
        copied_folder = tmp_path / "guppy_output"
        shutil.copytree(case["folder_path"], copied_folder)
        for region in case["expected_regions"]:
            with h5py.File(copied_folder / f"timeCorrection_{region}.hdf5", "r+") as time_correction_file:
                del time_correction_file["timeRecStart"]

        interface = GuppyInterface(folder_path=str(copied_folder))
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") in (None, "")

    def test_discovery_cross_correlations(self, interface, case):
        actual = sorted(
            (
                {
                    "event_name": entry["event"],
                    "trace_type": entry["feature"],
                    "region_1": entry["region_1"],
                    "region_2": entry["region_2"],
                }
                for entry in interface.cross_correlations
            ),
            key=lambda entry: (entry["event_name"], entry["trace_type"]),
        )
        expected = sorted(
            case["expected_cross_correlations"], key=lambda entry: (entry["event_name"], entry["trace_type"])
        )
        assert actual == expected

    def test_metadata_cross_correlations(self, interface, case):
        metadata = interface.get_metadata()
        cross_correlations_metadata = metadata["Ophys"]["Guppy"]["CrossCorrelations"]
        expected_names = {
            f"cross_correlation_{entry['event_name']}_{entry['trace_type']}_{entry['region_1']}_{entry['region_2']}"
            for entry in case["expected_cross_correlations"]
        }
        assert {entry["name"] for entry in cross_correlations_metadata} == expected_names

    def test_metadata_processing_module_includes_guppy_version(self, interface):
        metadata = interface.get_metadata()
        description = metadata["Ophys"]["Guppy"]["ProcessingModule"]["description"]
        assert "(GuPPy version 2.0.0a7)" in description

    def test_metadata_traces_and_transients(self, interface, case):
        metadata = interface.get_metadata()
        guppy_metadata = metadata["Ophys"]["Guppy"]

        expected_trace_names = {
            f"{prefix}_{region}" for region, prefixes in case["expected_traces"].items() for prefix in prefixes
        }
        assert {trace["name"] for trace in guppy_metadata["Traces"]} == expected_trace_names

        expected_transient_names = {
            f"transients_{region}_{feature}"
            for region, features in case["expected_transients"].items()
            for feature in features
        }
        assert {transient["name"] for transient in guppy_metadata["Transients"]} == expected_transient_names

    # ----------------------------------------------------------------- registries / parameters

    def test_registries(self, interface, case, linked_nwbfile, region_to_indices):
        module = self._add(interface, linked_nwbfile, region_to_indices, stub_test=True)

        regions_table = module["regions"]
        assert regions_table.neurodata_type == "GuppyRegionsTable"
        assert list(regions_table["region"].data) == case["expected_regions"]
        # The ragged fiber link (a VectorIndex over a DynamicTableRegion) stores, in region order,
        # each region's acquisition table rows. Check the flat stored indices.
        flat_fiber_indices = list(regions_table["fiber_photometry_table_region"].target.data[:])
        expected_flat = [index for region in case["expected_regions"] for index in region_to_indices[region]]
        assert flat_fiber_indices == expected_flat

        events_table = module["events"]
        assert events_table.neurodata_type == "GuppyEventsTable"
        assert sorted(events_table["event_name"].data) == sorted(case["expected_event_store_to_event_name"].values())

    def test_parameters(self, interface, case, linked_nwbfile, region_to_indices):
        self._add(interface, linked_nwbfile, region_to_indices, stub_test=True)
        parameters = linked_nwbfile.lab_meta_data["guppy_parameters"]
        assert parameters.neurodata_type == "GuppyParameters"
        assert parameters.guppy_version == "2.0.0a7"
        # zscore_method is present in the fixture parameters file.
        assert parameters.zscore_method is not None

    def test_events_registry_references_behavior_objects(self, interface, case, linked_nwbfile, region_to_indices):
        """When behavioral event objects exist in the file, the events registry resolves to them by name.

        Uses the ``ndx_events.Events`` type the converter writes; the registry holds a generic object
        reference, so the lookup is by name.
        """
        if not interface.event_names:
            module = self._add(interface, linked_nwbfile, region_to_indices, stub_test=True)
            assert "events" not in module["events"].colnames  # no optional object-reference column
            return

        behavior_module = linked_nwbfile.create_processing_module(name="behavior", description="behavioral events")
        event_objects = {}
        for event_name in interface.event_names:
            events = Events(name=event_name, description=event_name, timestamps=[0.0, 1.0])
            behavior_module.add(events)
            event_objects[event_name] = events

        module = self._add(interface, linked_nwbfile, region_to_indices, stub_test=True)
        events_table = module["events"]
        for row_index, event_name in enumerate(events_table["event_name"].data):
            assert events_table["events"][row_index] is event_objects[event_name]

    # ----------------------------------------------------------------- products land as ndx-guppy types

    def test_add_to_nwbfile_lands_in_processing_module(self, interface, case, linked_nwbfile, region_to_indices):
        module = self._add(interface, linked_nwbfile, region_to_indices, stub_test=True)
        assert "fiber_photometry" in linked_nwbfile.processing
        assert not linked_nwbfile.acquisition, "GuPPy interface must not write to /acquisition/."

        for region, prefixes in case["expected_traces"].items():
            for prefix in prefixes:
                series = module[f"{prefix}_{region}"]
                assert series.neurodata_type == "GuppyDerivedResponseSeries"
                assert series.trace_type == _PREFIX_TO_TRACE_TYPE[prefix]
                assert list(series.fiber_photometry_table_region.data[:]) == region_to_indices[region]
                assert _resolve_regions(module, series.region) == [region]
                assert series.data.shape[0] == len(series.timestamps)
                assert float(series.timestamps[-1] - series.timestamps[0]) <= 1.01  # stub keeps ~1 s

        for region, features in case["expected_transients"].items():
            for feature in features:
                table = module[f"transients_{region}_{feature}"]
                assert table.neurodata_type == "GuppyTransientsTable"
                assert table.trace_type == feature
                assert "timestamp" in table.colnames and "amplitude" in table.colnames
                if len(table) > 0:
                    assert set(_resolve_regions(module, table["region"])) == {region}

        assert module["transient_summary"].neurodata_type == "GuppyTransientSummaryTable"

        for entry in case["expected_cross_correlations"]:
            name = (
                f"cross_correlation_{entry['event_name']}_{entry['trace_type']}"
                f"_{entry['region_1']}_{entry['region_2']}"
            )
            cross_correlation = module[name]
            assert cross_correlation.neurodata_type == "GuppyCrossCorrelation"
            assert cross_correlation.trace_type == entry["trace_type"]
            assert cross_correlation.trials.shape[0] == cross_correlation.lag.shape[0]  # lag-first
            assert cross_correlation.trials.shape[1] == cross_correlation.trial_onset_times.shape[0]
            assert _resolve_regions(module, cross_correlation.region) == [entry["region_1"], entry["region_2"]]
            assert _resolve_events(module, cross_correlation.event) == [entry["event_name"]]

        for entry in interface.psths:
            suffix = "" if entry["baseline_corrected"] else "_baseline_uncorrected"
            psth = module[f"psth_{entry['event']}_{entry['region']}_{entry['feature']}{suffix}"]
            assert psth.neurodata_type == "GuppyPSTH"
            assert psth.trace_type == entry["feature"]
            assert bool(psth.baseline_corrected) == entry["baseline_corrected"]
            assert psth.traces.shape[0] == psth.peri_event_time.shape[0]  # time-first
            assert _resolve_regions(module, psth.region) == [entry["region"]]
            assert _resolve_events(module, psth.event) == [entry["event"]]

        for entry in interface.peak_aucs:
            peak_auc = module[f"peak_auc_{entry['event']}_{entry['region']}_{entry['feature']}"]
            assert peak_auc.neurodata_type == "GuppyPeakAUC"
            assert peak_auc.peak_positive.shape[0] == peak_auc.window_start.shape[0]  # window-first
            assert peak_auc.peak_positive.shape[1] == peak_auc.trial_onset_times.shape[0]
            assert _resolve_regions(module, peak_auc.region) == [entry["region"]]

    # ----------------------------------------------------------------- products match their source files

    def test_transients_table_row_count_matches_csv(self, interface, case, linked_nwbfile, region_to_indices):
        module = self._add(interface, linked_nwbfile, region_to_indices, stub_test=False)
        for region, features in case["expected_transients"].items():
            for feature in features:
                csv_path = case["folder_path"] / f"transientsOccurrences_{feature}_{region}.csv"
                expected_count = len(pandas.read_csv(csv_path))
                table = module[f"transients_{region}_{feature}"]
                assert len(table["timestamp"]) == expected_count
                assert len(table["amplitude"]) == expected_count

    def test_transient_summary_matches_freq_amp(self, interface, case, linked_nwbfile, region_to_indices):
        module = self._add(interface, linked_nwbfile, region_to_indices, stub_test=False)
        summary = module["transient_summary"]

        expected_rows = []
        for region, features in case["expected_transients"].items():
            for feature in features:
                freq_amp_path = case["folder_path"] / f"freqAndAmp_{feature}_{region}.h5"
                if not freq_amp_path.is_file():
                    continue
                dataframe = pandas.read_hdf(freq_amp_path)
                expected_rows.append(
                    (
                        region,
                        feature,
                        float(dataframe["freq (events/min)"].iloc[0]),
                        float(dataframe["amplitude"].iloc[0]),
                    )
                )

        actual_rows = list(
            zip(
                _resolve_regions(module, summary["region"]),
                summary["trace_type"].data,
                summary["frequency_per_min"].data,
                summary["mean_amplitude"].data,
            )
        )
        assert actual_rows == expected_rows

    def test_cross_correlation_matches_source(self, interface, case, linked_nwbfile, region_to_indices):
        module = self._add(interface, linked_nwbfile, region_to_indices, stub_test=False)
        for entry in case["expected_cross_correlations"]:
            source_path = (
                case["folder_path"]
                / "cross_correlation_output"
                / f"corr_{entry['event_name']}_{entry['trace_type']}_{entry['region_1']}_{entry['region_2']}.h5"
            )
            source = pandas.read_hdf(source_path)
            name = (
                f"cross_correlation_{entry['event_name']}_{entry['trace_type']}"
                f"_{entry['region_1']}_{entry['region_2']}"
            )
            cross_correlation = module[name]

            trial_columns = [column for column in source.columns if _column_parses_as_float(column)]
            np.testing.assert_array_equal(cross_correlation.lag[:], source["timestamps"].to_numpy(dtype=np.float64))
            np.testing.assert_array_equal(cross_correlation.trials[:], source[trial_columns].to_numpy(dtype=np.float64))
            np.testing.assert_array_equal(
                cross_correlation.trial_onset_times[:], np.array([float(column) for column in trial_columns])
            )
            np.testing.assert_array_equal(cross_correlation.mean[:], source["mean"].to_numpy(dtype=np.float64))
            np.testing.assert_array_equal(cross_correlation.error[:], source["err"].to_numpy(dtype=np.float64))

            bin_columns = sorted(
                (int(match.group(1)), int(match.group(2)))
                for match in (_BIN_COLUMN_PATTERN.match(column) for column in source.columns)
                if match is not None
            )
            if bin_columns:
                np.testing.assert_array_equal(
                    cross_correlation.bin_edges[:], np.array([[start, stop] for start, stop in bin_columns])
                )
                np.testing.assert_array_equal(
                    cross_correlation.binned_mean[:],
                    np.stack([source[f"bin_({a}-{b})"].to_numpy(dtype=np.float64) for a, b in bin_columns], axis=1),
                )

    def test_psth_matches_source(self, interface, case, linked_nwbfile, region_to_indices):
        module = self._add(interface, linked_nwbfile, region_to_indices, stub_test=False)
        for entry in interface.psths:  # no-op for fixtures without PSTH files
            source = pandas.read_hdf(entry["path"])
            suffix = "" if entry["baseline_corrected"] else "_baseline_uncorrected"
            psth = module[f"psth_{entry['event']}_{entry['region']}_{entry['feature']}{suffix}"]
            trial_columns = [column for column in source.columns if _column_parses_as_float(column)]
            np.testing.assert_array_equal(psth.peri_event_time[:], source["timestamps"].to_numpy(dtype=np.float64))
            np.testing.assert_array_equal(psth.traces[:], source[trial_columns].to_numpy(dtype=np.float64))
            np.testing.assert_array_equal(psth.mean[:], source["mean"].to_numpy(dtype=np.float64))
            np.testing.assert_array_equal(psth.error[:], source["err"].to_numpy(dtype=np.float64))

    def test_peak_auc_matches_source(self, interface, case, linked_nwbfile, region_to_indices):
        module = self._add(interface, linked_nwbfile, region_to_indices, stub_test=False)
        for entry in interface.peak_aucs:
            source = pandas.read_hdf(entry["path"])
            peak_auc = module[f"peak_auc_{entry['event']}_{entry['region']}_{entry['feature']}"]
            window_count = sum(1 for column in source.columns if str(column).startswith("peak_pos_"))
            mean_row = next(str(index) for index in source.index if str(index).endswith("mean"))
            expected_mean_peak_positive = np.array(
                [float(source.loc[mean_row, f"peak_pos_{window + 1}"]) for window in range(window_count)]
            )
            np.testing.assert_array_equal(peak_auc.mean_peak_positive[:], expected_mean_peak_positive)
            start_points = np.asarray(interface.guppy_parameters["peak_startPoint"], dtype=np.float64)
            np.testing.assert_array_equal(peak_auc.window_start[:], start_points[~np.isnan(start_points)])

    def test_valid_signal_intervals_match_source(self, interface, case, linked_nwbfile, region_to_indices):
        module = self._add(interface, linked_nwbfile, region_to_indices, stub_test=False)

        expected = case["expected_valid_signal_intervals"]
        if not expected:
            assert "valid_signal_intervals" not in module.data_interfaces
            return

        table = module["valid_signal_intervals"]
        assert table.neurodata_type == "GuppyValidSignalIntervals"
        assert interface.artifact_removal_method in table.description
        actual_regions = _resolve_regions(module, table["region"])
        actual_starts = list(table["start_time"][:])
        actual_stops = list(table["stop_time"][:])
        assert len(actual_regions) == len(expected)
        for (region, start, stop), (expected_region, expected_start, expected_stop) in zip(
            zip(actual_regions, actual_starts, actual_stops), expected
        ):
            assert region == expected_region
            assert start == pytest.approx(expected_start)
            assert stop == pytest.approx(expected_stop)

    def test_cross_correlation_without_psth_bin_columns(self, case, tmp_path, linked_nwbfile, region_to_indices):
        copied_folder = tmp_path / "guppy_output"
        shutil.copytree(case["folder_path"], copied_folder)
        cross_correlation_folder = copied_folder / "cross_correlation_output"
        if cross_correlation_folder.is_dir():
            for h5_path in sorted(cross_correlation_folder.glob("corr_*.h5")):
                dataframe = pandas.read_hdf(h5_path)
                bin_columns = [column for column in dataframe.columns if column.startswith("bin_")]
                dataframe = dataframe.drop(columns=bin_columns)
                h5_path.unlink()
                dataframe.to_hdf(h5_path, key="df", mode="w")

        interface = GuppyInterface(folder_path=str(copied_folder))
        module = self._add(interface, linked_nwbfile, region_to_indices, stub_test=False)
        for entry in case["expected_cross_correlations"]:
            name = (
                f"cross_correlation_{entry['event_name']}_{entry['trace_type']}"
                f"_{entry['region_1']}_{entry['region_2']}"
            )
            cross_correlation = module[name]
            assert cross_correlation.bin_edges is None
            assert cross_correlation.binned_mean is None

    # ----------------------------------------------------------------- alignment / roundtrip / errors

    def test_aligned_starting_time_shifts_traces_and_transients(
        self, interface, case, linked_nwbfile, region_to_indices
    ):
        first_region = case["expected_regions"][0]
        original_first_timestamp = float(interface.get_original_timestamps()[first_region][0])

        offset = 12.34
        interface.set_aligned_starting_time(offset)
        module = self._add(interface, linked_nwbfile, region_to_indices, stub_test=False)

        first_trace_name = f"{case['expected_traces'][first_region][0]}_{first_region}"
        assert float(module[first_trace_name].timestamps[0]) == pytest.approx(original_first_timestamp + offset)

        for region, features in case["expected_transients"].items():
            for feature in features:
                csv_path = case["folder_path"] / f"transientsOccurrences_{feature}_{region}.csv"
                expected_first_peak = float(pandas.read_csv(csv_path)["timestamps"].iloc[0]) + offset
                table = module[f"transients_{region}_{feature}"]
                assert table["timestamp"][0] == pytest.approx(expected_first_peak)

        if case["expected_valid_signal_intervals"]:
            interval_table = module["valid_signal_intervals"]
            actual = list(
                zip(
                    _resolve_regions(module, interval_table["region"]),
                    list(interval_table["start_time"][:]),
                    list(interval_table["stop_time"][:]),
                )
            )
            for (region, start, stop), (expected_region, expected_start, expected_stop) in zip(
                actual, case["expected_valid_signal_intervals"]
            ):
                assert region == expected_region
                assert start == pytest.approx(expected_start + offset)
                assert stop == pytest.approx(expected_stop + offset)

    def test_round_trip_write_read(self, interface, case, linked_nwbfile, region_to_indices, tmp_path):
        # GuppyInterface is non-standalone: add its products to an acquisition-linked NWBFile and
        # write that file directly (run_conversion alone would build a fresh file with no table).
        self._add(interface, linked_nwbfile, region_to_indices, stub_test=True)

        nwbfile_path = tmp_path / "test_guppy.nwb"
        with NWBHDF5IO(str(nwbfile_path), "w") as io:
            io.write(linked_nwbfile)
        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            module = nwbfile.processing["fiber_photometry"]
            assert module["regions"].neurodata_type == "GuppyRegionsTable"
            for region, prefixes in case["expected_traces"].items():
                for prefix in prefixes:
                    series = module.data_interfaces[f"{prefix}_{region}"]
                    assert series.neurodata_type == "GuppyDerivedResponseSeries"
                    assert series.trace_type == _PREFIX_TO_TRACE_TYPE[prefix]
                    assert list(series.fiber_photometry_table_region.data[:]) == region_to_indices[region]
            for entry in case["expected_cross_correlations"]:
                name = (
                    f"cross_correlation_{entry['event_name']}_{entry['trace_type']}"
                    f"_{entry['region_1']}_{entry['region_2']}"
                )
                assert module.data_interfaces[name].neurodata_type == "GuppyCrossCorrelation"
            assert nwbfile.lab_meta_data["guppy_parameters"].neurodata_type == "GuppyParameters"

    def test_add_to_nwbfile_without_table_raises(self, interface, region_to_indices):
        """Non-standalone: GuPPy fails loudly if no acquisition FiberPhotometryTable is present."""
        metadata = interface.get_metadata()
        with pytest.raises(AssertionError, match="No FiberPhotometryTable found"):
            interface.add_to_nwbfile(
                mock_NWBFile(), metadata, fiber_photometry_table_region_indices=region_to_indices, stub_test=True
            )

    def test_add_to_nwbfile_without_indices_raises(self, interface, linked_nwbfile, case):
        """Non-standalone: GuPPy fails loudly if a region has no supplied table-region indices."""
        metadata = interface.get_metadata()
        with pytest.raises(AssertionError, match="No fiber_photometry_table_region_indices supplied"):
            interface.add_to_nwbfile(linked_nwbfile, metadata, fiber_photometry_table_region_indices={}, stub_test=True)

    # ----------------------------------------------------------------- warnings / construction errors

    def test_remove_artifacts_flag_npy_mismatch_warns(self, tmp_path):
        source_folder = GUPPY_DATA_PATH / "Photo_63_207-181030-103332_output_2"
        copied_folder = tmp_path / "guppy_output"
        shutil.copytree(source_folder, copied_folder)
        for npy_path in copied_folder.glob("coordsForPreProcessing_*.npy"):
            npy_path.unlink()

        with pytest.warns(UserWarning, match="no coordsForPreProcessing"):
            GuppyInterface(folder_path=str(copied_folder))

    def test_missing_artifacts_removal_method_warns_and_defaults(self, tmp_path):
        source_folder = GUPPY_DATA_PATH / "Photo_63_207-181030-103332_output_2"
        copied_folder = tmp_path / "guppy_output"
        shutil.copytree(source_folder, copied_folder)
        params_path = copied_folder / "GuPPyParamtersUsed.json"
        params_source = json.loads(params_path.read_text())
        params_source.pop("artifactsRemovalMethod", None)
        params_path.write_text(json.dumps(params_source))

        with pytest.warns(UserWarning, match="artifactsRemovalMethod"):
            interface = GuppyInterface(folder_path=str(copied_folder))
        assert interface.artifact_removal_method == "concatenate"

    def test_artifacts_removal_method_read_from_json(self, tmp_path):
        source_folder = GUPPY_DATA_PATH / "Photo_63_207-181030-103332_output_2"
        copied_folder = tmp_path / "guppy_output"
        shutil.copytree(source_folder, copied_folder)
        params_path = copied_folder / "GuPPyParamtersUsed.json"
        params_source = json.loads(params_path.read_text())
        params_source["artifactsRemovalMethod"] = "replace with NaN"
        params_path.write_text(json.dumps(params_source))

        interface = GuppyInterface(folder_path=str(copied_folder))
        assert interface.artifact_removal_method == "replace with NaN"

    def test_missing_parameters_file_raises(self, case, tmp_path):
        copied_folder = tmp_path / "guppy_output"
        shutil.copytree(case["folder_path"], copied_folder)
        (copied_folder / "GuPPyParamtersUsed.json").unlink()
        with pytest.raises(AssertionError, match="GuPPyParamtersUsed.json not found"):
            GuppyInterface(folder_path=str(copied_folder))
