from abc import abstractmethod
import os
from typing import Dict, Optional

import numpy as np
from pynwb import NWBFile

from ...basedatainterface import BaseDataInterface
from ...tools.nwb_helpers import make_or_load_nwbfile
from ...tools.text import convert_df_to_time_intervals
from ...utils.dict import load_dict_from_file
from ...utils.types import FilePathType


class TimeIntervalsInterface(BaseDataInterface):
    """
    Abstract Interface for time intervals.
    """

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
        verbose : bool, default: True
        """
        read_kwargs = read_kwargs or dict()
        super().__init__(file_path=file_path)
        self.verbose = verbose

        self._read_kwargs = read_kwargs
        self.df = self._read_file(file_path, **read_kwargs)
        self.time_intervals = None

    def get_metadata(self):
        return dict(
            TimeIntervals=dict(
                trials=dict(
                    table_name="trials",
                    table_description=f"experimental trials generated from {self.source_data['file_path']}",
                )
            )
        )

    def get_metadata_schema(self):
        fpath = os.path.join(os.path.split(__file__)[0], "timeintervals.schema.json")
        return load_dict_from_file(fpath)

    def get_original_timestamps(self, column: str) -> np.ndarray:
        return self._read_file(**self.source_data, **self._read_kwargs)[column]

    def get_timestamps(self, column: str) -> np.ndarray:
        if not column.endswith("_time"):
            raise ValueError("Timing columns on a TimeIntervals table need to end with '_time'!")

        return self.df[column]

    def align_starting_time(self, starting_time: float):
        timing_columns = [column for column in self.df.columns if column.endswith("_time")]

        for column in timing_columns:
            self.df[column] += starting_time

    def align_timestamps(self, aligned_timestamps: np.ndarray, column: str):
        if not column.endswith("_time"):
            raise ValueError("Timing columns on a TimeIntervals table need to end with '_time'!")

        self.df[column] = aligned_timestamps

    def run_conversion(
        self,
        nwbfile_path: Optional[FilePathType] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        tag: str = "trials",
        column_name_mapping: Dict[str, str] = None,
        column_descriptions: Dict[str, str] = None,
    ):
        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=self.verbose
        ) as nwbfile_out:
            self.time_intervals = convert_df_to_time_intervals(
                self.df,
                column_name_mapping=column_name_mapping,
                column_descriptions=column_descriptions,
                **metadata["TimeIntervals"][tag],
            )
            nwbfile_out.add_time_intervals(self.time_intervals)

        return nwbfile_out

    @abstractmethod
    def _read_file(self, file_path: FilePathType, **read_kwargs):
        pass
