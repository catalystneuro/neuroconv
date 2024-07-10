import pandas as pd

from ..timeintervalsinterface import TimeIntervalsInterface
from ....utils.types import FilePathType


class CsvTimeIntervalsInterface(TimeIntervalsInterface):
    """Interface for adding data from a .csv file as a TimeIntervals object."""

    display_name = "CSV time interval table"
    associated_suffixes = (".csv",)
    info = "Interface for writing a time intervals table from a comma separated value (CSV) file."

    def _read_file(self, file_path: FilePathType, **read_kwargs):
        return pd.read_csv(file_path, **read_kwargs)
