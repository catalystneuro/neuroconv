import json
import re
import shutil
from datetime import datetime, timezone

import h5py
import numpy as np
import pandas
import pytest
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import GuppyInterface


def _column_parses_as_float(column: str) -> bool:
    try:
        float(column)
    except ValueError:
        return False
    return True


_BIN_COLUMN_PATTERN = re.compile(r"^bin_\((\d+)-(\d+)\)$")

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH


GUPPY_DATA_PATH = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT" / "Photo_63_207-181030-103332"


class TestGuppyInterface:
    """Tests for the GuppyInterface against the standard GuPPy fixture set."""

    @pytest.fixture(
        params=[
            pytest.param(
                dict(
                    folder_path=GUPPY_DATA_PATH / "Photo_63_207-181030-103332_output_1",
                    parameters_file_path=GUPPY_DATA_PATH / "GuPPyParamtersUsed1.json",
                    expected_regions=["dms", "dls"],
                    expected_traces={
                        "dms": ["cntrl_sig_fit", "dff", "z_score"],
                        "dls": ["cntrl_sig_fit", "dff", "z_score"],
                    },
                    expected_transients={"dms": ["z_score", "dff"], "dls": ["z_score", "dff"]},
                    expected_cross_correlations=[
                        {"event_name": "port_entries", "feature": "dff", "region_1": "dls", "region_2": "dms"},
                        {"event_name": "port_entries", "feature": "z_score", "region_1": "dls", "region_2": "dms"},
                        {"event_name": "rewarded_nose_pokes", "feature": "dff", "region_1": "dls", "region_2": "dms"},
                        {
                            "event_name": "rewarded_nose_pokes",
                            "feature": "z_score",
                            "region_1": "dls",
                            "region_2": "dms",
                        },
                        {"event_name": "unrewarded_nose_pokes", "feature": "dff", "region_1": "dls", "region_2": "dms"},
                        {
                            "event_name": "unrewarded_nose_pokes",
                            "feature": "z_score",
                            "region_1": "dls",
                            "region_2": "dms",
                        },
                    ],
                    expected_session_start_time=datetime(2018, 10, 30, 15, 33, 54, tzinfo=timezone.utc),
                    expected_valid_signal_intervals=[],
                ),
                id="tdt_isosbestic_two_regions",
            ),
            pytest.param(
                dict(
                    folder_path=GUPPY_DATA_PATH / "Photo_63_207-181030-103332_output_1",
                    parameters_file_path=None,
                    expected_regions=["dms", "dls"],
                    expected_traces={
                        "dms": ["cntrl_sig_fit", "dff", "z_score"],
                        "dls": ["cntrl_sig_fit", "dff", "z_score"],
                    },
                    expected_transients={"dms": ["z_score", "dff"], "dls": ["z_score", "dff"]},
                    expected_cross_correlations=[
                        {"event_name": "port_entries", "feature": "dff", "region_1": "dls", "region_2": "dms"},
                        {"event_name": "port_entries", "feature": "z_score", "region_1": "dls", "region_2": "dms"},
                        {"event_name": "rewarded_nose_pokes", "feature": "dff", "region_1": "dls", "region_2": "dms"},
                        {
                            "event_name": "rewarded_nose_pokes",
                            "feature": "z_score",
                            "region_1": "dls",
                            "region_2": "dms",
                        },
                        {"event_name": "unrewarded_nose_pokes", "feature": "dff", "region_1": "dls", "region_2": "dms"},
                        {
                            "event_name": "unrewarded_nose_pokes",
                            "feature": "z_score",
                            "region_1": "dls",
                            "region_2": "dms",
                        },
                    ],
                    expected_session_start_time=datetime(2018, 10, 30, 15, 33, 54, tzinfo=timezone.utc),
                    expected_valid_signal_intervals=[],
                ),
                id="tdt_isosbestic_two_regions_no_parameters_file",
            ),
            pytest.param(
                dict(
                    folder_path=GUPPY_DATA_PATH / "Photo_63_207-181030-103332_output_2",
                    parameters_file_path=GUPPY_DATA_PATH / "GuPPyParamtersUsed2.json",
                    expected_regions=["dms"],
                    expected_traces={"dms": ["cntrl_sig_fit", "dff", "z_score"]},
                    expected_transients={"dms": ["z_score"]},
                    expected_cross_correlations=[],
                    expected_session_start_time=datetime(2018, 10, 30, 15, 33, 54, tzinfo=timezone.utc),
                    expected_valid_signal_intervals=[
                        ("dms", 2.43144319, 20.71505607),
                        ("dms", 40.04014057, 154.71773782),
                    ],
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
        if case["parameters_file_path"] is not None:
            assert case["parameters_file_path"].is_file(), f"Parameters file missing at {case['parameters_file_path']}."
        return case

    @pytest.fixture
    def interface(self, case):
        kwargs = dict(folder_path=str(case["folder_path"]))
        if case["parameters_file_path"] is not None:
            kwargs["parameters_file_path"] = str(case["parameters_file_path"])
        return GuppyInterface(**kwargs)

    def test_discovery(self, interface, case):
        assert interface.regions == case["expected_regions"]
        assert interface.traces_by_region == case["expected_traces"]
        assert interface.transients_by_region == case["expected_transients"]

    def test_metadata_session_start_time(self, interface, case):
        metadata = interface.get_metadata()
        if case["expected_session_start_time"] is None:
            # CSV-input fixtures lack timeRecStart; session_start_time must be set by the user.
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
                    "feature": entry["feature"],
                    "region_1": entry["region_1"],
                    "region_2": entry["region_2"],
                }
                for entry in interface.cross_correlations
            ),
            key=lambda entry: (entry["event_name"], entry["feature"]),
        )
        expected = sorted(
            case["expected_cross_correlations"], key=lambda entry: (entry["event_name"], entry["feature"])
        )
        assert actual == expected

    def test_metadata_cross_correlations(self, interface, case):
        metadata = interface.get_metadata()
        cross_correlations_metadata = metadata["Ophys"]["Guppy"]["CrossCorrelations"]
        expected_names = {
            f"cross_correlation_{entry['event_name']}_{entry['feature']}_{entry['region_1']}_{entry['region_2']}"
            for entry in case["expected_cross_correlations"]
        }
        assert {entry["name"] for entry in cross_correlations_metadata} == expected_names

    def test_cross_correlation_table_matches_source(self, interface, case):
        metadata = interface.get_metadata()
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile, metadata, stub_test=False)
        module = nwbfile.processing["fiber_photometry"]
        for entry in case["expected_cross_correlations"]:
            source_path = (
                case["folder_path"]
                / "cross_correlation_output"
                / f"corr_{entry['event_name']}_{entry['feature']}_{entry['region_1']}_{entry['region_2']}.h5"
            )
            source_dataframe = pandas.read_hdf(source_path)
            entry_name = (
                f"cross_correlation_{entry['event_name']}_{entry['feature']}"
                f"_{entry['region_1']}_{entry['region_2']}"
            )
            trial_table = module[entry_name]
            mean_table = module[f"{entry_name}_mean"]

            trial_columns = [column for column in source_dataframe.columns if _column_parses_as_float(column)]
            bin_columns = sorted(
                (int(match.group(1)), int(match.group(2)), column)
                for column, match in (
                    (column, _BIN_COLUMN_PATTERN.match(column)) for column in source_dataframe.columns
                )
                if match is not None
            )
            expected_lag = source_dataframe["timestamps"].to_numpy(dtype=np.float64)

            assert len(trial_table) == len(trial_columns)
            for i, trial_column in enumerate(trial_columns):
                assert trial_table["trial_onset_in_seconds"][i] == float(trial_column)
                np.testing.assert_array_equal(
                    np.asarray(trial_table["lag_in_seconds"][i]),
                    expected_lag,
                )
                np.testing.assert_array_equal(
                    np.asarray(trial_table["cross_correlation"][i]),
                    source_dataframe[trial_column].to_numpy(dtype=np.float64),
                )

            np.testing.assert_array_equal(
                np.asarray(mean_table["lag_in_seconds"][:]),
                expected_lag,
            )
            np.testing.assert_array_equal(
                np.asarray(mean_table["mean"][:]),
                source_dataframe["mean"].to_numpy(dtype=np.float64),
            )

            psth_bins_table = module[f"{entry_name}_psth_bins"]
            assert len(psth_bins_table) == len(bin_columns)
            for i, (bin_start, bin_end, value_column) in enumerate(bin_columns):
                assert psth_bins_table["bin_start_trial_index"][i] == bin_start
                assert psth_bins_table["bin_end_trial_index"][i] == bin_end
                np.testing.assert_array_equal(
                    np.asarray(psth_bins_table["lag_in_seconds"][i]),
                    expected_lag,
                )
                np.testing.assert_array_equal(
                    np.asarray(psth_bins_table["cross_correlation"][i]),
                    source_dataframe[value_column].to_numpy(dtype=np.float64),
                )
                np.testing.assert_array_equal(
                    np.asarray(psth_bins_table["cross_correlation_error"][i]),
                    source_dataframe[f"bin_err_({bin_start}-{bin_end})"].to_numpy(dtype=np.float64),
                )

    def test_cross_correlation_without_psth_bin_columns(self, case, tmp_path):
        copied_folder = tmp_path / "guppy_output"
        shutil.copytree(case["folder_path"], copied_folder)
        for h5_path in sorted((copied_folder / "cross_correlation_output").glob("corr_*.h5")):
            dataframe = pandas.read_hdf(h5_path)
            bin_columns = [column for column in dataframe.columns if column.startswith("bin_")]
            dataframe = dataframe.drop(columns=bin_columns)
            h5_path.unlink()
            dataframe.to_hdf(h5_path, key="df", mode="w")

        kwargs = dict(folder_path=str(copied_folder))
        if case["parameters_file_path"] is not None:
            kwargs["parameters_file_path"] = str(case["parameters_file_path"])
        interface = GuppyInterface(**kwargs)
        metadata = interface.get_metadata()
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile, metadata, stub_test=False)

        module = nwbfile.processing["fiber_photometry"]
        for entry in case["expected_cross_correlations"]:
            entry_name = (
                f"cross_correlation_{entry['event_name']}_{entry['feature']}"
                f"_{entry['region_1']}_{entry['region_2']}"
            )
            assert entry_name in module.data_interfaces
            assert f"{entry_name}_mean" in module.data_interfaces
            assert f"{entry_name}_psth_bins" not in module.data_interfaces

    def test_valid_signal_intervals_match_source(self, interface, case):
        metadata = interface.get_metadata()
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile, metadata, stub_test=False)
        module = nwbfile.processing["fiber_photometry"]

        expected = case["expected_valid_signal_intervals"]
        if not expected:
            assert "valid_signal_intervals" not in module.data_interfaces
            return

        table = module["valid_signal_intervals"]
        assert "Method:" in table.description
        assert interface.artifact_removal_method in table.description
        actual_regions = list(table["region"][:])
        actual_starts = list(table["start_time"][:])
        actual_stops = list(table["stop_time"][:])
        assert len(actual_regions) == len(expected)
        for (region, start, stop), (expected_region, expected_start, expected_stop) in zip(
            zip(actual_regions, actual_starts, actual_stops), expected
        ):
            assert region == expected_region
            assert start == pytest.approx(expected_start)
            assert stop == pytest.approx(expected_stop)

    def test_remove_artifacts_flag_npy_mismatch_warns(self, tmp_path):
        source_folder = GUPPY_DATA_PATH / "Photo_63_207-181030-103332_output_2"
        copied_folder = tmp_path / "guppy_output"
        shutil.copytree(source_folder, copied_folder)
        for npy_path in copied_folder.glob("coordsForPreProcessing_*.npy"):
            npy_path.unlink()

        with pytest.warns(UserWarning, match="no coordsForPreProcessing"):
            GuppyInterface(
                folder_path=str(copied_folder),
                parameters_file_path=str(GUPPY_DATA_PATH / "GuPPyParamtersUsed2.json"),
            )

    def test_missing_artifacts_removal_method_warns_and_defaults(self):
        with pytest.warns(UserWarning, match="artifactsRemovalMethod"):
            interface = GuppyInterface(
                folder_path=str(GUPPY_DATA_PATH / "Photo_63_207-181030-103332_output_2"),
                parameters_file_path=str(GUPPY_DATA_PATH / "GuPPyParamtersUsed2.json"),
            )
        assert interface.artifact_removal_method == "concatenate"

    def test_artifacts_removal_method_read_from_json(self, tmp_path):
        source_folder = GUPPY_DATA_PATH / "Photo_63_207-181030-103332_output_2"
        copied_folder = tmp_path / "guppy_output"
        shutil.copytree(source_folder, copied_folder)
        params_source = json.loads((GUPPY_DATA_PATH / "GuPPyParamtersUsed2.json").read_text())
        params_source["artifactsRemovalMethod"] = "replace with NaN"
        params_path = tmp_path / "GuPPyParamtersUsed_with_method.json"
        params_path.write_text(json.dumps(params_source))

        interface = GuppyInterface(
            folder_path=str(copied_folder),
            parameters_file_path=str(params_path),
        )
        assert interface.artifact_removal_method == "replace with NaN"

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

    def test_add_to_nwbfile_lands_in_processing_module(self, interface, case):
        metadata = interface.get_metadata()
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile, metadata, stub_test=True)

        assert "fiber_photometry" in nwbfile.processing
        assert not nwbfile.acquisition, "GuPPy interface must not write to /acquisition/."

        module = nwbfile.processing["fiber_photometry"]
        for region, prefixes in case["expected_traces"].items():
            for prefix in prefixes:
                series = module[f"{prefix}_{region}"]
                assert series.data.shape[0] > 0
                assert series.data.shape[0] <= int(np.ceil(series.rate)) + 1
        for region, features in case["expected_transients"].items():
            for feature in features:
                table = module[f"transients_{region}_{feature}"]
                assert "timestamp" in table.colnames
                assert "amplitude" in table.colnames
        assert "transient_summary" in module.data_interfaces
        for entry in case["expected_cross_correlations"]:
            entry_name = (
                f"cross_correlation_{entry['event_name']}_{entry['feature']}_{entry['region_1']}_{entry['region_2']}"
            )
            assert entry_name in module.data_interfaces
            trial_table = module[entry_name]
            assert "trial_onset_in_seconds" in trial_table.colnames
            assert "lag_in_seconds" in trial_table.colnames
            assert "cross_correlation" in trial_table.colnames
            assert len(np.asarray(trial_table["lag_in_seconds"][0])) <= 100

            mean_name = f"{entry_name}_mean"
            assert mean_name in module.data_interfaces
            mean_table = module[mean_name]
            assert "lag_in_seconds" in mean_table.colnames
            assert "mean" in mean_table.colnames
            assert len(mean_table["lag_in_seconds"]) <= 100

            psth_bins_name = f"{entry_name}_psth_bins"
            assert psth_bins_name in module.data_interfaces
            psth_bins_table = module[psth_bins_name]
            assert "bin_start_trial_index" in psth_bins_table.colnames
            assert "bin_end_trial_index" in psth_bins_table.colnames
            assert "lag_in_seconds" in psth_bins_table.colnames
            assert "cross_correlation" in psth_bins_table.colnames
            assert "cross_correlation_error" in psth_bins_table.colnames
            assert len(np.asarray(psth_bins_table["lag_in_seconds"][0])) <= 100

    def test_transients_table_row_count_matches_csv(self, interface, case):
        metadata = interface.get_metadata()
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile, metadata, stub_test=False)
        module = nwbfile.processing["fiber_photometry"]
        for region, features in case["expected_transients"].items():
            for feature in features:
                csv_path = case["folder_path"] / f"transientsOccurrences_{feature}_{region}.csv"
                expected_count = len(pandas.read_csv(csv_path))
                table = module[f"transients_{region}_{feature}"]
                assert len(table["timestamp"]) == expected_count
                assert len(table["amplitude"]) == expected_count

    def test_transient_summary_matches_freq_amp(self, interface, case):
        metadata = interface.get_metadata()
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile, metadata, stub_test=False)
        summary = nwbfile.processing["fiber_photometry"]["transient_summary"]

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
                summary["region"].data,
                summary["feature"].data,
                summary["frequency_per_min"].data,
                summary["mean_amplitude"].data,
            )
        )
        assert actual_rows == expected_rows

    def test_aligned_starting_time_shifts_traces_and_transients(self, interface, case):
        original_starting_time_and_rate = interface.get_original_starting_time_and_rate()
        first_region = case["expected_regions"][0]
        original_start, _ = original_starting_time_and_rate[first_region]

        offset = 12.34
        interface.set_aligned_starting_time_and_rate(
            {region: (start + offset, rate) for region, (start, rate) in original_starting_time_and_rate.items()}
        )

        metadata = interface.get_metadata()
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(
            nwbfile,
            metadata,
            stub_test=False,
            timing_source="aligned_starting_time_and_rate",
        )
        module = nwbfile.processing["fiber_photometry"]
        first_trace_name = f"{case['expected_traces'][first_region][0]}_{first_region}"
        assert module[first_trace_name].starting_time == pytest.approx(original_start + offset)

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
                    list(interval_table["region"][:]),
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

    def test_round_trip_write_read(self, interface, case, tmp_path):
        metadata = interface.get_metadata()
        if metadata["NWBFile"].get("session_start_time") in (None, ""):
            metadata["NWBFile"]["session_start_time"] = datetime(2024, 1, 1, tzinfo=timezone.utc)

        nwbfile_path = tmp_path / "test_guppy.nwb"
        interface.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
        )
        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            assert "fiber_photometry" in nwbfile.processing
            module = nwbfile.processing["fiber_photometry"]
            for region, prefixes in case["expected_traces"].items():
                for prefix in prefixes:
                    assert f"{prefix}_{region}" in module.data_interfaces
            for entry in case["expected_cross_correlations"]:
                cross_correlation_name = (
                    f"cross_correlation_{entry['event_name']}_{entry['feature']}"
                    f"_{entry['region_1']}_{entry['region_2']}"
                )
                assert cross_correlation_name in module.data_interfaces
