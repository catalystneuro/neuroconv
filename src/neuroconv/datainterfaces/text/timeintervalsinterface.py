from abc import abstractmethod
from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ...basedatainterface import BaseDataInterface
from ...tools.text import convert_df_to_time_intervals
from ...utils.dict import DeepDict, load_dict_from_file


class TimeIntervalsInterface(BaseDataInterface):
    """Abstract Interface for time intervals."""

    keywords = ("table", "trials", "epochs", "time intervals")

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        read_kwargs: dict | None = None,
        verbose: bool = False,
    ):
        """
        Initialize the TimeIntervalsInterface.

        Parameters
        ----------
        file_path : FilePath
            The path to the file containing time intervals data (CSV, Excel, etc.).
        read_kwargs : dict, optional
            Additional keyword arguments passed to the file reading function.
            For CSV files, these are passed to pandas.read_csv().
            For Excel files, these are passed to pandas.read_excel().
            Examples: {"sep": ";", "encoding": "utf-8", "skiprows": 1}
            Default is None.
        verbose : bool, default: False
            Controls verbosity of the interface output.
        """
        read_kwargs = read_kwargs or dict()
        super().__init__(file_path=file_path)
        self.verbose = verbose
        self._read_kwargs = read_kwargs
        self.dataframe = self._read_file(file_path, **read_kwargs)
        self.time_intervals = None

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        metadata["TimeIntervals"] = dict(
            trials=dict(
                table_name="trials",
                table_description=f"experimental trials generated from {self.source_data['file_path']}",
            )
        )

        return metadata

    def get_metadata_schema(self) -> dict:
        """
        Get the metadata schema for the time intervals.

        Returns
        -------
        dict
            The schema dictionary for time intervals metadata.
        """
        fpath = Path(__file__).parent.parent.parent / "schemas" / "timeintervals_schema.json"
        return load_dict_from_file(fpath)

    def get_original_timestamps(self, column: str) -> np.ndarray:
        """
        Get the original timestamps for a given column.

        Parameters
        ----------
        column : str
            The name of the column containing timestamps.

        Returns
        -------
        np.ndarray
            The original timestamps from the specified column.

        Raises
        ------
        ValueError
            If the column name does not end with '_time'.
        """
        if not column.endswith("_time"):
            raise ValueError("Timing columns on a TimeIntervals table need to end with '_time'!")

        return self._read_file(**self.source_data, **self._read_kwargs)[column].values

    def get_timestamps(self, column: str) -> np.ndarray:
        """
        Get the current timestamps for a given column.

        Parameters
        ----------
        column : str
            The name of the column containing timestamps.

        Returns
        -------
        np.ndarray
            The current timestamps from the specified column.

        Raises
        ------
        ValueError
            If the column name does not end with '_time'.
        """
        if not column.endswith("_time"):
            raise ValueError("Timing columns on a TimeIntervals table need to end with '_time'!")

        return self.dataframe[column].values

    def set_aligned_starting_time(self, aligned_starting_time: float):
        """
        Align the starting time by shifting all timestamps by the given value.

        Parameters
        ----------
        aligned_starting_time : float
            The aligned starting time to shift all timestamps by.
        """
        timing_columns = [column for column in self.dataframe.columns if column.endswith("_time")]

        for column in timing_columns:
            self.dataframe[column] += aligned_starting_time

    def set_aligned_timestamps(
        self, aligned_timestamps: np.ndarray, column: str, interpolate_other_columns: bool = False
    ):
        """
        Set aligned timestamps for the given column and optionally interpolate other columns.

        Parameters
        ----------
        aligned_timestamps : np.ndarray
            The aligned timestamps to set for the given column.
        column : str
            The name of the column to update with the aligned timestamps.
        interpolate_other_columns : bool, optional
            If True, interpolate the timestamps in other columns, by default False.

        Raises
        ------
        ValueError
            If the column name does not end with '_time'.
        """
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
        """
        Align timestamps using linear interpolation.

        Parameters
        ----------
        unaligned_timestamps : np.ndarray
            The original unaligned timestamps that map to the aligned timestamps.
        aligned_timestamps : np.ndarray
            The target aligned timestamps corresponding to the unaligned timestamps.
        column : str
            The name of the column containing the timestamps to be aligned.
        """
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
        metadata: dict | None = None,
        tag: str = "trials",
        column_name_mapping: dict[str, str] = None,
        column_descriptions: dict[str, str] = None,
    ) -> NWBFile:
        """
        Add time intervals data from the CSV/Excel file to an NWBFile object.

        Parameters
        ----------
        nwbfile : NWBFile
            An in-memory NWBFile object to add the time intervals data to.
        metadata : dict, optional
            Metadata dictionary containing time intervals configuration.
            If not provided, uses default metadata from get_metadata().

            Expected structure under metadata["TimeIntervals"][tag]:

            - table_name : str
                Name of the time intervals table. Determines storage location in NWB:
                * "trials" → nwbfile.trials
                * "epochs" → nwbfile.epochs
                * Other names → nwbfile.intervals[table_name]
            - table_description : str
                Description of the time intervals data.

            Example:
                metadata = {
                    "TimeIntervals": {
                        "tag": {
                            "table_name": "trials",
                            "table_description": "Experimental trials"
                        }
                    }
                }

            To add as epochs instead:
                metadata["TimeIntervals"]["tag"]["table_name"] = "epochs"

        tag : str, default: "trials"
            Key to use when looking up time intervals metadata in metadata["TimeIntervals"][tag].
            By default, looks for metadata["TimeIntervals"]["trials"].
        column_name_mapping : dict of str to str, optional
            Dictionary to rename columns from the source file.
            Keys are original column names, values are new names.
            Example: {"condition": "trial_type", "start": "start_time"}
        column_descriptions : dict of str to str, optional
            Dictionary providing descriptions for columns (after any renaming).
            Keys are column names (after mapping), values are descriptions.
            If not provided, column names are used as descriptions.
            Example: {"trial_type": "Type of trial", "correct": "Response accuracy"}

        Returns
        -------
        NWBFile
            The NWBFile object with time intervals data added.

        Notes
        -----
        - The time intervals are added to nwbfile.intervals and also set as direct properties
          for "trials" and "epochs" to enable in-memory access (e.g., nwbfile.trials).
        - All timing columns must be in seconds.
        - The 'start_time' column is required; 'stop_time' is auto-generated if missing.

        """
        metadata = metadata or self.get_metadata()
        self.time_intervals = convert_df_to_time_intervals(
            self.dataframe,
            column_name_mapping=column_name_mapping,
            column_descriptions=column_descriptions,
            **metadata["TimeIntervals"][tag],
        )
        nwbfile.add_time_intervals(self.time_intervals)

        # For trials and epochs, also set them as direct properties for in-memory access
        # This makes nwbfile.trials and nwbfile.epochs work before save/load
        table_name = self.time_intervals.name
        if table_name == "trials":
            nwbfile.trials = self.time_intervals
        elif table_name == "epochs":
            nwbfile.epochs = self.time_intervals

        return nwbfile

    @abstractmethod
    def _read_file(self, file_path: FilePath, **read_kwargs):
        pass
