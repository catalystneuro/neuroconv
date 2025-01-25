import numpy as np
import pandas as pd
from pynwb.epoch import TimeIntervals


def convert_df_to_time_intervals(
    df: pd.DataFrame,
    table_name: str = "trials",
    table_description: str = "experimental trials",
    column_name_mapping: dict[str, str] = None,
    column_descriptions: dict[str, str] = None,
) -> TimeIntervals:
    """
    Convert a dataframe to a TimeIntervals object.

    Parameters
    ----------
    df : pandas.DataFrame
        The dataframe to convert.
    table_name : str, optional
        The name of the TimeIntervals object.
    table_description : str, optional
        The description of the TimeIntervals object.
    column_name_mapping: dict, optional
        If passed, rename subset of columns from key to value.
    column_descriptions: dict, optional
        Keys are the names of the columns (after renaming) and values are the descriptions. If not passed,
        the names of the columns are used as descriptions.

    Returns
    -------
    TimeIntervals

    """
    if column_name_mapping is not None:
        df.rename(columns=column_name_mapping, inplace=True)

    default_column_descriptions = dict(
        start_time="Start time of epoch, in seconds.",
        stop_time="Stop time of epoch, in seconds.",
    )

    if column_descriptions is None:
        column_descriptions = default_column_descriptions
    else:
        column_descriptions = dict(default_column_descriptions, **column_descriptions)

    time_intervals = TimeIntervals(name=table_name, description=table_description)
    if "start_time" not in df:
        raise ValueError(f"df must contain a column named 'start_time'. Existing columns: {df.columns.to_list()}")
    if "stop_time" not in df:
        df["stop_time"] = np.r_[df["start_time"][1:].to_numpy(), np.nan]
    for col in df:
        if col not in ("start_time", "stop_time"):
            time_intervals.add_column(col, column_descriptions.get(col, col))
    for i, row in df.iterrows():
        time_intervals.add_row(row.to_dict())

    return time_intervals
