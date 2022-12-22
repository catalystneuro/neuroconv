import pandas as pd

from ..timeintervalsinterface import TimeIntervalsInterface
from ....utils.types import FilePathType


class ExcelTimeIntervalsInterface(TimeIntervalsInterface):
    """Interface for adding data from an Excel file to NWB as a TimeIntervals object"""

    def _read_file(self, file_path: FilePathType, **read_kwargs):
        return pd.read_excel(file_path, **read_kwargs)
