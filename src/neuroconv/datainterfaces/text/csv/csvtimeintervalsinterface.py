import pandas as pd

from ..timeintervalsinterface import TimeIntervalsInterface
from ....utils.types import FilePathType


class CsvTimeIntervalsInterface(TimeIntervalsInterface):
    """Interface for adding data from a .csv file as a TimeIntervals object"""

    def _read_file(self, file_path: FilePathType, **read_kwargs):
        return pd.read_csv(file_path, **read_kwargs)
