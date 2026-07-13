"""Fixture-free unit tests for GuppyInterface bin-label parsing.

These exercise the two bin-label parsing sites directly on hand-built DataFrames/indexes, so they cover
both GuPPy binning modes -- integer ``bin_(0-3)`` ("# of trials") and decimal ``bin_(0.0-2.0)``
("Time (min)") -- without needing the large (~100 MB) GuPPy output fixtures used by the on-data tests.
"""

import numpy as np
import pandas

from neuroconv.datainterfaces.fiber_photometry.guppy.guppydatainterface import (
    GuppyInterface,
)

SESSION = "Photo_249_391-200721-120136"


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
