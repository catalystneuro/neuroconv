from typing import Optional

import pandas as pd

from ..timeintervalsinterface import TimeIntervalsInterface
from ....utils.types import FilePathType


class ExcelTimeIntervalsInterface(TimeIntervalsInterface):
    """Interface for adding data from an Excel file to NWB as a TimeIntervals object"""

    def __init__(
        self,
        file_path: FilePathType,
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

    def _read_file(self, file_path: FilePathType, **read_kwargs):
        return pd.read_excel(file_path, **read_kwargs)
