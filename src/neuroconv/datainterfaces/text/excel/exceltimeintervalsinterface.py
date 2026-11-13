import pandas as pd
from pydantic import FilePath, validate_call

from ..timeintervalsinterface import TimeIntervalsInterface


class ExcelTimeIntervalsInterface(TimeIntervalsInterface):
    """Interface for adding data from an Excel file to NWB as a TimeIntervals object."""

    display_name = "Excel time interval table"
    associated_suffixes = (".xlsx", ".xls", ".xlsm")
    info = "Interface for writing a time intervals table from an excel file."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        start_time_column: str | None = None,
        stop_time_column: str | None = None,
        stop_time_from_next_start: bool = False,
        read_kwargs: dict | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
        start_time_column : str, optional
            The column of the file holding the start time of each interval, written as ``start_time``.
            By default the file's own ``start_time`` column.
        stop_time_column : str, optional
            The column of the file holding the stop time of each interval, written as ``stop_time``.
            By default the file's own ``stop_time`` column.
        stop_time_from_next_start : bool, default: False
            For a file without stop times: each interval stops at the next interval's start, and the last
            one's stop is NaN. Only for a file with no stop column.
        read_kwargs : dict, optional
            Passed to pandas.read_excel()
        verbose : bool, default: False
        """

        super().__init__(
            file_path=file_path,
            start_time_column=start_time_column,
            stop_time_column=stop_time_column,
            stop_time_from_next_start=stop_time_from_next_start,
            read_kwargs=read_kwargs,
            verbose=verbose,
        )

    def _read_file(self, file_path: FilePath, **read_kwargs):
        return pd.read_excel(file_path, **read_kwargs)
