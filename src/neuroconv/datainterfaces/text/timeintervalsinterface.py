from abc import abstractmethod

import numpy as np
from pynwb import NWBFile
from pynwb.epoch import TimeIntervals

from ...basedatainterface import BaseDataInterface
from ...utils.types import FilePathType, Optional
from ...tools.nwb_helpers import make_or_load_nwbfile


def convert_df_to_time_intervals(df, name, description=None):
    if description is None:
        description = name
    time_intervals = TimeIntervals(name, description)
    if "start_time" not in df:
        raise ValueError(f"df must contain a column named 'start_time'. Existing columns: {df.columns.to_list()}")
    if "stop_time" not in df:
        df["stop_time"] = np.nan
    for col in df:
        if col not in ("start_time", "stop_time"):
            time_intervals.add_column(col, col)
    for i, row in df.iterrows():
        time_intervals.add_row(row.to_dict())

    return time_intervals


class TimeIntervalsInterface(BaseDataInterface):
    def __init__(
        self,
        file_path: FilePathType,
        read_kwargs: Optional[dict] = None,
        verbose: bool = True,
        name: str = "trials",
        description: Optional[str] = None,
    ):
        if read_kwargs is None:
            read_kwargs = {}
        super().__init__(file_path=file_path)
        self.verbose = verbose

        self.df = self._read_file(file_path, **read_kwargs)
        self.time_intervals = convert_df_to_time_intervals(self.df, name=name, description=description)

    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        **conversion_options,
    ):
        with make_or_load_nwbfile(
                nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=self.verbose
        ) as nwbfile_out:
            nwbfile_out.add_time_intervals(self.time_intervals)

        return nwbfile_out

    @abstractmethod
    def _read_file(self, file_path: FilePathType, **read_kwargs):
        pass
