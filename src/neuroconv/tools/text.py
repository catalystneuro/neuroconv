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
    Convert a pandas DataFrame containing time interval data to a PyNWB TimeIntervals object.

    This function creates a PyNWB TimeIntervals object from tabular data where each row represents
    a time interval (e.g., trial, epoch, or event). The DataFrame must contain a 'start_time' column,
    and optionally a 'stop_time' column (which will be auto-generated if missing).

    Parameters
    ----------
    df : pandas.DataFrame
        The dataframe to convert. Must contain at least a 'start_time' column.
        If 'stop_time' is not present, it will be automatically generated from the next row's 'start_time'.
        Additional columns will be added as custom columns to the TimeIntervals object.
    table_name : str, default: "trials"
        The name of the TimeIntervals object. This name determines how the data is stored in NWB:
        - "trials" → accessible as nwbfile.trials
        - "epochs" → accessible as nwbfile.epochs
        - Any other name → accessible as nwbfile.intervals[table_name]
    table_description : str, default: "experimental trials"
        A human-readable description of the time intervals data.
    column_name_mapping : dict of str to str, optional
        Dictionary to rename columns before adding to TimeIntervals.
        Keys are original column names, values are new names.
        Example: {"condition": "trial_type", "start": "start_time"}
    column_descriptions : dict of str to str, optional
        Dictionary providing descriptions for each column (after renaming).
        Keys are column names (after mapping), values are descriptions.
        If not provided, column names will be used as descriptions.
        Default descriptions are provided for 'start_time' and 'stop_time'.
        Example: {"trial_type": "Type of trial presented", "correct": "Whether response was correct"}

    Returns
    -------
    TimeIntervals
        A PyNWB TimeIntervals object containing the data from the DataFrame.

    Raises
    ------
    ValueError
        If the DataFrame does not contain a 'start_time' column.

    Examples
    --------
    Basic usage with minimal DataFrame:

    >>> import pandas as pd
    >>> df = pd.DataFrame({
    ...     'start_time': [0.0, 1.0, 2.0],
    ...     'stop_time': [0.5, 1.5, 2.5],
    ...     'condition': [1, 2, 1]
    ... })
    >>> time_intervals = convert_df_to_time_intervals(df)

    With column renaming and descriptions:

    >>> time_intervals = convert_df_to_time_intervals(
    ...     df,
    ...     table_name="epochs",
    ...     table_description="Behavioral epochs",
    ...     column_name_mapping={"condition": "epoch_type"},
    ...     column_descriptions={"epoch_type": "Type of behavioral epoch"}
    ... )

    Notes
    -----
    - All times should be in seconds
    - If 'stop_time' is missing, it is automatically generated as the next row's 'start_time'
    - The last row's 'stop_time' will be NaN if not provided
    - Column names ending with '_time' are treated as timing columns

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
