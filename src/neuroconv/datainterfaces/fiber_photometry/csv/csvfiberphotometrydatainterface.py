"""Interface for fiber photometry data stored in a CSV file."""

import numpy as np
import pandas as pd
from pydantic import FilePath, validate_call

from ..basefiberphotometryinterface import BaseFiberPhotometryInterface


class CSVFiberPhotometryInterface(BaseFiberPhotometryInterface):
    """Data Interface for converting raw fiber photometry data from a single CSV file.

    This is a general-purpose CSV fiber photometry reader: the caller points at one CSV file, names
    the column holding the timestamps in seconds (``timestamps_column``), and names the data
    column(s) whose fluorescence samples become this interface's single
    ``FiberPhotometryResponseSeries`` (``data_columns``). Both narrow files (one data column, e.g. the
    GuPPy acquisition format's ``<stream>.csv`` with ``timestamps`` and ``data`` columns) and wide
    files (several data columns sharing one timestamps column) are supported.

    A list of ``data_columns`` is column-stacked into one multi-channel response series; to write
    several *separate* series (e.g. a signal and an isosbestic control) sharing one
    ``FiberPhotometryTable``, use one interface per series (with distinct ``metadata_key`` values) in
    a converter.

    Notes
    -----
    CSV recordings carry no embedded recording-start timestamp, so :meth:`get_metadata` does NOT
    populate ``NWBFile/session_start_time``. The user must supply it via editable metadata.
    """

    display_name = "CSVFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from a CSV file."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
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
        file_path : FilePath
            The path to the CSV file holding the fiber photometry data.
        data_columns : str, int, or list of str or int
            The data column(s) whose samples are column-stacked into this interface's single
            ``FiberPhotometryResponseSeries``. A column name (for a CSV with a header row) or a
            positional index (0-based, for a header-less CSV). Pass a list to stack several columns
            into one multi-channel series.
        timestamps_column : str or int
            The column holding the timestamps (seconds), shared by every data column. A column name
            for a CSV with a header row, or a positional index (0-based) for a header-less CSV.
        metadata_key : str, optional
            Key under ``metadata["FiberPhotometry"]`` holding this interface's response-series
            metadata. When ``None`` (default), it is generated from ``data_columns``.
        read_kwargs : dict, optional
            Additional keyword arguments forwarded to ``pandas.read_csv`` to handle format quirks such
            as ``sep``, ``encoding``, ``decimal``, or ``skiprows``. Any value given here overrides the
            interface's own defaults (``header`` and ``float_precision``). Default is None.
        verbose : bool, default: False
            Whether to print status messages.
        """
        data_columns_list = [data_columns] if isinstance(data_columns, (str, int)) else list(data_columns)
        self._read_kwargs = read_kwargs or dict()
        super().__init__(
            file_path=file_path,
            stream_names=data_columns_list,
            timestamps_column=timestamps_column,
            metadata_key=metadata_key,
            verbose=verbose,
        )

    @classmethod
    def get_available_columns(cls, file_path: FilePath) -> list[str]:
        """Return the header column names of the CSV file (empty for a header-less file).

        A convenience for picking ``data_columns`` / ``timestamps_column`` on a headered file; a
        header-less file is addressed by positional integer indices instead.
        """
        return list(pd.read_csv(file_path, nrows=0).columns)

    def _read_column(self, column: str | int) -> np.ndarray:
        """Read a single column from the CSV file as a numpy array."""
        # An int column specifier means a header-less file (positional columns); a str means a header row.
        header = None if isinstance(self.source_data["timestamps_column"], int) else 0
        # float_precision="round_trip" uses an exact, platform-independent float parser; pandas's
        # default C parser rounds the final ULP differently across platforms. Caller-supplied
        # read_kwargs override these defaults.
        read_kwargs = {"header": header, "float_precision": "round_trip", **self._read_kwargs}
        dataframe = pd.read_csv(self.source_data["file_path"], usecols=[column], **read_kwargs)
        return dataframe[column].to_numpy()

    def _get_stream_data(self, *, stream_name: str | int) -> np.ndarray:
        return self._read_column(stream_name)

    def _get_stream_timestamps(self, *, stream_name: str | int) -> np.ndarray:
        return self._read_column(self.source_data["timestamps_column"]).astype("float64")
