import pandas as pd

from ..timeintervalsinterface import TimeIntervalsInterface
from ....utils.types import FilePathType


class ExcelTimeIntervalsInterface(TimeIntervalsInterface):
    def _read_file(self, file_path: FilePathType, **read_kwargs):
        return pd.read_excel(file_path, **read_kwargs)
