from typing import Optional

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
        read_kwargs: Optional[dict] = None,
        verbose: bool = True,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
        read_kwargs : dict, optional
            Passed to pandas.read_excel()
        verbose : bool, default: True
        """
        super().__init__(file_path=file_path, read_kwargs=read_kwargs, verbose=verbose)

    def _read_file(self, file_path: FilePath, **read_kwargs):
        return pd.read_excel(file_path, **read_kwargs)
