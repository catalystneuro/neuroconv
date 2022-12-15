from datetime import datetime
import os

import pandas as pd

from neuroconv.datainterfaces import ExcelTimeIntervalsInterface, CsvTimeIntervalsInterface
from neuroconv.datainterfaces.text.timeintervalsinterface import convert_df_to_time_intervals


trials_xls_path = os.path.join(os.path.dirname(__file__), "trials.xlsx")
trials_csv_path = os.path.join(os.path.dirname(__file__), "trials.csv")


def test_convert_df_to_time_intervals():
    df = pd.read_excel(trials_xls_path)
    time_intervals = convert_df_to_time_intervals(df)


def test_convert_df_to_time_intervals_colname_mapping():
    df = pd.read_excel(trials_xls_path)
    time_intervals = convert_df_to_time_intervals(df, column_name_mapping=dict(condition="cond"))
    assert time_intervals.colnames == ("start_time", "stop_time", "cond")


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
    nwbfile = interface.run_conversion(metadata=metadata)
    assert nwbfile.intervals["trials"].colnames == ("start_time", "stop_time", "condition")


def test_excel_column_name_mapping():
    interface = ExcelTimeIntervalsInterface(trials_xls_path)
    metadata = interface.get_metadata()
    metadata["NWBFile"] = dict(session_start_time=datetime.now().astimezone())
    nwbfile = interface.run_conversion(metadata=metadata, column_name_mapping=dict(condition="cond"))
    assert nwbfile.intervals["trials"].colnames == ("start_time", "stop_time", "cond")


def test_csv():
    interface = CsvTimeIntervalsInterface(trials_csv_path)
    metadata = interface.get_metadata()
    metadata["NWBFile"] = dict(session_start_time=datetime.now().astimezone())
    nwbfile = interface.run_conversion(metadata=metadata)
    assert nwbfile.intervals["trials"]
