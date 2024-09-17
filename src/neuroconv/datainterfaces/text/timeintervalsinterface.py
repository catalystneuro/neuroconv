from abc import abstractmethod
from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ...basedatainterface import BaseDataInterface
from ...tools.text import convert_df_to_time_intervals
from ...utils.dict import load_dict_from_file


class TimeIntervalsInterface(BaseDataInterface):
    """Abstract Interface for time intervals."""

    keywords = ("table", "trials", "epochs", "time intervals")

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
        verbose : bool, default: True
        """
        read_kwargs = read_kwargs or dict()
        super().__init__(file_path=file_path)
        self.verbose = verbose

        self._read_kwargs = read_kwargs
        self.dataframe = self._read_file(file_path, **read_kwargs)
        self.time_intervals = None

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        metadata["TimeIntervals"] = dict(
            trials=dict(
                table_name="trials",
                table_description=f"experimental trials generated from {self.source_data['file_path']}",
            )
        )

        return metadata

    def get_metadata_schema(self) -> dict:
        fpath = Path(__file__).parent.parent.parent / "schemas" / "timeintervals_schema.json"
        return load_dict_from_file(fpath)

    def get_original_timestamps(self, column: str) -> np.ndarray:
        if not column.endswith("_time"):
            raise ValueError("Timing columns on a TimeIntervals table need to end with '_time'!")

        return self._read_file(**self.source_data, **self._read_kwargs)[column].values

    def get_timestamps(self, column: str) -> np.ndarray:
        if not column.endswith("_time"):
            raise ValueError("Timing columns on a TimeIntervals table need to end with '_time'!")

        return self.dataframe[column].values

    def set_aligned_starting_time(self, aligned_starting_time: float):
        timing_columns = [column for column in self.dataframe.columns if column.endswith("_time")]

        for column in timing_columns:
            self.dataframe[column] += aligned_starting_time

    def set_aligned_timestamps(
        self, aligned_timestamps: np.ndarray, column: str, interpolate_other_columns: bool = False
    ):
        if not column.endswith("_time"):
            raise ValueError("Timing columns on a TimeIntervals table need to end with '_time'!")

        unaligned_timestamps = np.array(self.dataframe[column])
        self.dataframe[column] = aligned_timestamps

        if not interpolate_other_columns:
            return

        other_timing_columns = [
            other_column
            for other_column in self.dataframe.columns
            if other_column.endswith("_time") and other_column != column
        ]
        for other_timing_column in other_timing_columns:
            self.align_by_interpolation(
                unaligned_timestamps=unaligned_timestamps,
                aligned_timestamps=aligned_timestamps,
                column=other_timing_column,
            )

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray, column: str):
        current_timestamps = self.get_timestamps(column=column)
        assert (
            current_timestamps[1] >= unaligned_timestamps[0]
        ), "All current timestamps except for the first must be strictly within the unaligned mapping."
        assert (
            current_timestamps[-2] <= unaligned_timestamps[-1]
        ), "All current timestamps except for the last must be strictly within the unaligned mapping."
        # Assume timing column is ascending otherwise

        self.set_aligned_timestamps(
            aligned_timestamps=np.interp(
                x=current_timestamps,
                xp=unaligned_timestamps,
                fp=aligned_timestamps,
                left=2 * aligned_timestamps[0] - aligned_timestamps[1],  # If first or last values are outside alignment
                right=2 * aligned_timestamps[-1] - aligned_timestamps[-2],  # then use the most recent diff to regress
            ),
            column=column,
        )

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        tag: str = "trials",
        column_name_mapping: dict[str, str] = None,
        column_descriptions: dict[str, str] = None,
    ) -> NWBFile:
        """
        Run the NWB conversion for the instantiated data interface.

        Parameters
        ----------
        nwbfile : NWBFile, optional
            An in-memory NWBFile object to write to the location.
        metadata : dict, optional
            Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
        tag : str, default: "trials"
        column_name_mapping: dict, optional
            If passed, rename subset of columns from key to value.
        column_descriptions: dict, optional
            Keys are the names of the columns (after renaming) and values are the descriptions. If not passed,
            the names of the columns are used as descriptions.

        """
        metadata = metadata or self.get_metadata()
        self.time_intervals = convert_df_to_time_intervals(
            self.dataframe,
            column_name_mapping=column_name_mapping,
            column_descriptions=column_descriptions,
            **metadata["TimeIntervals"][tag],
        )
        nwbfile.add_time_intervals(self.time_intervals)

        return nwbfile

    @abstractmethod
    def _read_file(self, file_path: FilePath, **read_kwargs):
        pass
