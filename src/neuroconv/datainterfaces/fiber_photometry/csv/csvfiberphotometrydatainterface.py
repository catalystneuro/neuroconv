"""Interface for fiber photometry data stored in one or more CSV files."""

from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import FilePath, validate_call

from ..basefiberphotometryinterface import BaseFiberPhotometryInterface


class CSVFiberPhotometryInterface(BaseFiberPhotometryInterface):
    """Data Interface for converting raw fiber photometry data from CSV file(s).

    This is a general-purpose CSV fiber photometry reader: the caller points at one or more CSV files,
    names the column holding the timestamps in seconds (``timestamps_column``), and names the data
    column(s) whose fluorescence samples become this interface's single
    ``FiberPhotometryResponseSeries`` (``data_columns``). Columns are addressed by name (for a CSV
    with a header row) or by 0-based positional index (for a header-less CSV).

    The channels of the response series are ``data_columns`` read from each file, in file-then-column
    order, column-stacked into one series. This covers three layouts with the same knobs:

    - **One file, one data column** (the GuPPy acquisition format's ``<stream>.csv`` with
      ``timestamps`` and ``data`` columns) -- one single-channel series.
    - **One file, several data columns** -- one multi-channel series.
    - **Several files, each contributing its ``data_columns``** (e.g. GuPPy's per-channel CSVs, whose
      channel identity is in the *filename*) -- one multi-channel series. The channels share a single
      time axis, taken from the **first** file's ``timestamps_column``.

    To write several *separate* series (e.g. a signal and an isosbestic control) sharing one
    ``FiberPhotometryTable``, use one interface per series (with distinct ``metadata_key`` values) in
    a converter.

    Notes
    -----
    CSV recordings carry no embedded recording-start timestamp, so :meth:`get_metadata` does NOT
    populate ``NWBFile/session_start_time``. The user must supply it via editable metadata.
    """

    display_name = "CSVFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from CSV files."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        file_paths: FilePath | list[FilePath],
        *,
        data_columns: str | int | list[str | int],
        timestamps_column: str | int,
        metadata_key: str | None = None,
        read_kwargs: dict | None = None,
        verbose: bool = False,
    ):
        """Initialize the CSVFiberPhotometryInterface.

        Parameters
        ----------
        file_paths : FilePath or list of FilePath
            The CSV file(s) holding the fiber photometry data. When several files are given, each
            contributes its ``data_columns`` as further channels of the single response series, in
            file-then-column order; the series' time axis is taken from the first file.
        data_columns : str, int, or list of str or int
            The data column(s), read from every file, whose samples are column-stacked into this
            interface's single ``FiberPhotometryResponseSeries``. A column name (for a CSV with a
            header row) or a positional index (0-based, for a header-less CSV).
        timestamps_column : str or int
            The column holding the timestamps (seconds) for the series' time axis, read from the first
            file. A column name for a CSV with a header row, or a positional index (0-based) for a
            header-less CSV.
        metadata_key : str, optional
            Key under ``metadata["FiberPhotometry"]`` holding this interface's response-series
            metadata. When ``None`` (default), it is generated from the file name(s).
        read_kwargs : dict, optional
            Additional keyword arguments forwarded to ``pandas.read_csv`` to handle format quirks such
            as ``sep``, ``encoding``, ``decimal``, or ``skiprows``. Any value given here overrides the
            interface's own defaults (``header`` and ``float_precision``). Default is None.
        verbose : bool, default: False
            Whether to print status messages.
        """
        file_paths_list = [file_paths] if isinstance(file_paths, (str, Path)) else list(file_paths)
        self._file_paths = [str(file_path) for file_path in file_paths_list]
        self._data_columns = [data_columns] if isinstance(data_columns, (str, int)) else list(data_columns)
        self._read_kwargs = read_kwargs or dict()

        # Up-front check (rather than a pandas read-time error deep in add_to_nwbfile): each file must
        # contain its data column(s), and the first file must also contain the timestamps column.
        self._assert_columns_present(self._file_paths, self._data_columns, timestamps_column)

        if metadata_key is None:
            stems = [Path(file_path).stem.replace(" ", "_").strip("_").lower() for file_path in self._file_paths]
            metadata_key = "_".join(["fiber_photometry", *stems])

        super().__init__(
            file_paths=self._file_paths,
            # Each file is one stackable unit ("stream") for the base; a file contributes its
            # data_columns as channels, and the base column-stacks the files into one series.
            stream_names=self._file_paths,
            timestamps_column=timestamps_column,
            metadata_key=metadata_key,
            verbose=verbose,
        )

    @staticmethod
    def _assert_columns_present(
        file_paths: list[str], data_columns: list[str | int], timestamps_column: str | int
    ) -> None:
        """Assert that each file has its data column(s), and the first file has the timestamps column."""
        header_less = isinstance(timestamps_column, int)
        for index, file_path in enumerate(file_paths):
            required_columns = [timestamps_column, *data_columns] if index == 0 else list(data_columns)
            if header_less:
                num_columns = pd.read_csv(file_path, nrows=1, header=None).shape[1]
                missing = [column for column in required_columns if isinstance(column, int) and column >= num_columns]
                assert (
                    not missing
                ), f"Column index(es) {missing} out of range for '{file_path}', which has {num_columns} columns."
            else:
                available_columns = list(pd.read_csv(file_path, nrows=0).columns)
                missing = [column for column in required_columns if column not in available_columns]
                assert (
                    not missing
                ), f"Column(s) {missing} not found in '{file_path}'. Available columns: {available_columns}."

    @classmethod
    def get_available_columns(cls, file_path: FilePath) -> list[str]:
        """Return the header column names of a CSV file (empty for a header-less file).

        A convenience for picking ``data_columns`` / ``timestamps_column`` on a headered file; a
        header-less file is addressed by positional integer indices instead.
        """
        return list(pd.read_csv(file_path, nrows=0).columns)

    def _read_dataframe(self, file_path: str, columns: list[str | int]) -> pd.DataFrame:
        """Read the given columns of a CSV file into a DataFrame."""
        # An int column specifier means a header-less file (positional columns); a str means a header row.
        header = None if isinstance(self.source_data["timestamps_column"], int) else 0
        # float_precision="round_trip" uses an exact, platform-independent float parser; pandas's
        # default C parser rounds the final ULP differently across platforms. Caller-supplied
        # read_kwargs override these defaults.
        read_kwargs = {"header": header, "float_precision": "round_trip", **self._read_kwargs}
        return pd.read_csv(file_path, usecols=columns, **read_kwargs)

    def _get_stream_data(self, *, stream_name: str) -> np.ndarray:
        # stream_name is a file path; return that file's data columns as (num_samples, num_data_columns).
        dataframe = self._read_dataframe(stream_name, self._data_columns)
        return dataframe[self._data_columns].to_numpy()

    def _get_stream_timestamps(self, *, stream_name: str) -> np.ndarray:
        # stream_name is a file path; the series' time axis is the timestamps column of that file.
        timestamps_column = self.source_data["timestamps_column"]
        return self._read_dataframe(stream_name, [timestamps_column])[timestamps_column].to_numpy().astype("float64")
