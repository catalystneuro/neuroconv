import os
from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO, read_nwb

from neuroconv.datainterfaces import (
    CsvTimeIntervalsInterface,
    ExcelTimeIntervalsInterface,
)
from neuroconv.tools.nwb_helpers import make_nwbfile_from_metadata
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin
from neuroconv.tools.text import convert_df_to_time_intervals

trials_xls_path = os.path.join(os.path.dirname(__file__), "trials.xlsx")
trials_csv_path = os.path.join(os.path.dirname(__file__), "trials.csv")
trials_csv_path2 = os.path.join(os.path.dirname(__file__), "trials_no_start_time.csv")
trials_with_response_time_csv_path = os.path.join(os.path.dirname(__file__), "trials_with_response_time.csv")


class TestCsvTimeIntervalsInterface(DataInterfaceTestMixin):
    data_interface_cls = CsvTimeIntervalsInterface
    interface_kwargs = dict(
        file_path=trials_with_response_time_csv_path, start_time_column="begin", stop_time_column="end"
    )
    expected_temporal_alignment_keys = ("start_time", "stop_time", "response_time")

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        trials = nwbfile.trials
        assert trials.colnames == ("start_time", "stop_time", "response_time", "condition")
        assert_array_equal(trials["start_time"][:], [0.1, 0.2, 0.3])
        assert_array_equal(trials["stop_time"][:], [0.2, 0.3, 0.4])
        assert_array_equal(trials["response_time"][:], [0.15, 0.25, 0.35])
        nwbfile.read_io.close()


class TestCsvTimeIntervalsInterfaceWithStopsFromTheNextStart(DataInterfaceTestMixin):
    data_interface_cls = CsvTimeIntervalsInterface
    interface_kwargs = dict(file_path=trials_csv_path2, start_time_column="start", stop_time_from_next_start=True)
    expected_temporal_alignment_keys = ("start_time",)

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        start_times = nwbfile.trials["start_time"][:]
        stop_times = nwbfile.trials["stop_time"][:]
        assert_array_equal(stop_times[:-1], start_times[1:])
        assert np.isnan(stop_times[-1])
        nwbfile.read_io.close()


def test_convert_df_to_time_intervals():
    df = pd.read_excel(trials_xls_path)
    time_intervals = convert_df_to_time_intervals(df)


def test_convert_df_to_time_intervals_colname_mapping():
    df = pd.read_excel(trials_xls_path)
    time_intervals = convert_df_to_time_intervals(df, column_name_mapping=dict(condition="cond"))
    assert time_intervals.colnames == ("start_time", "stop_time", "cond")


def test_convert_df_to_time_intervals_no_start_time():
    df = pd.read_csv(trials_csv_path2)
    time_intervals = convert_df_to_time_intervals(df, column_name_mapping=dict(start="start_time"))
    assert time_intervals.colnames == ("start_time", "stop_time", "condition")


def test_convert_df_to_time_intervals_leaves_the_dataframe_alone():
    df = pd.DataFrame({"start": [0.0, 1.0], "condition": [1, 2]})
    time_intervals = convert_df_to_time_intervals(df, column_name_mapping=dict(start="start_time"))
    assert time_intervals.colnames == ("start_time", "stop_time", "condition")
    assert list(df.columns) == ["start", "condition"]


def test_csv_add_to_nwbfile_twice_with_column_name_mapping():
    # The interface hands its own frame to the converter, so a first write must not change what the second sees.
    interface = CsvTimeIntervalsInterface(trials_csv_path)
    metadata = interface.get_metadata()
    metadata["NWBFile"] = dict(session_start_time=datetime.now().astimezone())
    for _ in range(2):
        nwbfile = make_nwbfile_from_metadata(metadata)
        interface.add_to_nwbfile(nwbfile, metadata=metadata, column_name_mapping=dict(condition="cond"))
        assert nwbfile.intervals["trials"].colnames == ("start_time", "stop_time", "cond")
    assert "condition" in interface.dataframe.columns


def test_convert_df_to_time_intervals_():
    df = pd.read_excel(trials_xls_path)
    time_intervals = convert_df_to_time_intervals(
        df, column_descriptions=dict(condition="This is a custom description")
    )
    assert time_intervals["condition"].description == "This is a custom description"


def test_excel_time_intervals():
    interface = ExcelTimeIntervalsInterface(trials_xls_path)
    metadata = interface.get_metadata()
    metadata["NWBFile"] = dict(session_start_time=datetime.now().astimezone())
    nwbfile = make_nwbfile_from_metadata(metadata)
    interface.add_to_nwbfile(nwbfile, metadata=metadata)
    assert nwbfile.intervals["trials"].colnames == ("start_time", "stop_time", "condition")


def test_excel_column_name_mapping():
    interface = ExcelTimeIntervalsInterface(trials_xls_path)
    metadata = interface.get_metadata()
    metadata["NWBFile"] = dict(session_start_time=datetime.now().astimezone())
    nwbfile = make_nwbfile_from_metadata(metadata)
    interface.add_to_nwbfile(nwbfile, metadata=metadata, column_name_mapping=dict(condition="cond"))
    assert nwbfile.intervals["trials"].colnames == ("start_time", "stop_time", "cond")


def test_csv():
    interface = CsvTimeIntervalsInterface(trials_csv_path)
    metadata = interface.get_metadata()
    metadata["NWBFile"] = dict(session_start_time=datetime.now().astimezone())
    nwbfile = make_nwbfile_from_metadata(metadata)
    interface.add_to_nwbfile(nwbfile, metadata=metadata)
    assert nwbfile.intervals["trials"]


def test_csv_round_trip(tmp_path):
    interface = CsvTimeIntervalsInterface(trials_csv_path)
    metadata = interface.get_metadata()
    metadata["NWBFile"] = dict(session_start_time=datetime.now().astimezone())
    interface.run_conversion(nwbfile_path=tmp_path / "test.nwb", metadata=metadata)

    with NWBHDF5IO(tmp_path / "test.nwb", "r") as io:
        nwb_read = io.read()
        assert nwb_read.trials.colnames == ("start_time", "stop_time", "condition")
        assert_array_equal(nwb_read.trials["condition"][:], [1, 2, 3, 1, 3, 2, 2, 3, 1, 2, 3])


def test_csv_round_trip_rename(tmp_path):
    interface = CsvTimeIntervalsInterface(trials_csv_path)
    metadata = interface.get_metadata()
    metadata["TimeIntervals"]["trials"].update(table_name="custom_name", table_description="custom description")
    metadata["NWBFile"] = dict(session_start_time=datetime.now().astimezone())
    interface.run_conversion(nwbfile_path=tmp_path / "test.nwb", metadata=metadata)

    with NWBHDF5IO(tmp_path / "test.nwb", "r") as io:
        nwb_read = io.read()
        assert nwb_read.intervals["custom_name"].description == "custom description"


def test_csv_start_time_column_missing_from_the_file():
    with pytest.raises(ValueError, match="'begin'"):
        CsvTimeIntervalsInterface(trials_csv_path, start_time_column="begin")


def test_csv_stop_time_from_next_start_with_a_stop_column():
    with pytest.raises(ValueError, match="has a stop column"):
        CsvTimeIntervalsInterface(trials_csv_path, stop_time_from_next_start=True)


def test_csv_without_a_start_time_column():
    with pytest.raises(ValueError, match=r"no `start_time` column.*\['start', 'condition'\]"):
        CsvTimeIntervalsInterface(trials_csv_path2)


def test_get_metadata_schema():
    interface = CsvTimeIntervalsInterface(trials_csv_path)
    interface.get_metadata_schema()
