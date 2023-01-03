import pandas as pd

from ..timeintervalsinterface import TimeIntervalsInterface
from ....utils.types import FilePathType, Optional


class CsvTimeIntervalsInterface(TimeIntervalsInterface):
    def _read_file(self, file_path: FilePathType, **read_kwargs):
        return pd.read_csv(file_path, **read_kwargs)
