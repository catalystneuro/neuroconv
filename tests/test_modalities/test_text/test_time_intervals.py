import os
from datetime import datetime

import pandas as pd
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import (
    CsvTimeIntervalsInterface,
    ExcelTimeIntervalsInterface,
)
from neuroconv.tools.nwb_helpers import make_nwbfile_from_metadata
from neuroconv.tools.text import convert_df_to_time_intervals

trials_xls_path = os.path.join(os.path.dirname(__file__), "trials.xlsx")
trials_csv_path = os.path.join(os.path.dirname(__file__), "trials.csv")
trials_csv_path2 = os.path.join(os.path.dirname(__file__), "trials_no_start_time.csv")


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


def test_get_metadata_schema():
    interface = CsvTimeIntervalsInterface(trials_csv_path)
    interface.get_metadata_schema()
