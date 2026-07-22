"""Interface for fiber photometry data stored in a CSV file."""

from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import FilePath, validate_call

from ._demux import ColumnDemux, DemuxConfig
from ..basefiberphotometryinterface import BaseFiberPhotometryInterface


class CSVFiberPhotometryInterface(BaseFiberPhotometryInterface):
    """Data Interface for converting raw fiber photometry data from a CSV file.

    This is a general-purpose CSV fiber photometry reader: the caller points at one CSV file, names
    the column holding the timestamps in seconds (``timestamps_column``), and names the data
    column(s) whose fluorescence samples become this interface's single
    ``FiberPhotometryResponseSeries`` (``data_columns``). Columns are addressed by name (for a CSV
    with a header row) or by 0-based positional index (for a header-less CSV).

    The channels of the response series are ``data_columns`` read from the file, in column order,
    column-stacked into one series. This covers two layouts with the same knobs:

    - **One data column** (the GuPPy acquisition format's ``<stream>.csv`` with ``timestamps`` and
      ``data`` columns) -- one single-channel series.
    - **Several data columns** -- one multi-channel series sharing the file's ``timestamps_column``.

    To aggregate *several* per-channel CSV files (e.g. GuPPy's per-region CSVs) into one series, use
    :class:`.MultiFileCSVFiberPhotometryInterface`. To write several *separate* series (e.g. a signal
    and an isosbestic control) sharing one ``FiberPhotometryTable``, use one interface per series
    (with distinct ``metadata_key`` values) in a converter.

    For an **interleaved** file, where the excitation channels are multiplexed frame-by-frame down the
    rows, pass a ``demux`` config selecting the one channel this interface reads: ``{"by": "column",
    ...}`` when a column labels each row's channel (e.g. a Neurophotometrics ``LedState``), or ``{"by":
    "stride", ...}`` when the channels cycle in a fixed order in a header-less file. So one interleaved
    file yields one channel per interface; instantiate one per channel and compose them in a converter.

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
        demux: DemuxConfig | None = None,
        metadata_key: str | None = None,
        read_kwargs: dict | None = None,
        verbose: bool = False,
    ):
        """Initialize the CSVFiberPhotometryInterface.

        Parameters
        ----------
        file_path : FilePath
            The CSV file holding the fiber photometry data.
        data_columns : str, int, or list of str or int
            The data column(s) whose samples are column-stacked into this interface's single
            ``FiberPhotometryResponseSeries``. A column name (for a CSV with a header row) or a
            positional index (0-based, for a header-less CSV).
        timestamps_column : str or int
            The column holding the timestamps (seconds) for the series' time axis. A column name for a
            CSV with a header row, or a positional index (0-based) for a header-less CSV.
        demux : dict or None, optional
            For an interleaved file (excitation channels multiplexed frame-by-frame down the rows), a
            config selecting the one channel this interface reads. Two shapes, chosen by ``by``:
            ``{"by": "column", "column": <col>, "value": <v>}`` reads the rows whose ``column`` equals
            ``value`` (e.g. a Neurophotometrics ``LedState``); ``{"by": "stride", "channels": <k>,
            "index": <i>, "skip_rows": <n>}`` reads every ``k``-th row starting at ``i`` after dropping
            ``n`` leading rows. Default None reads every row (no demux). Compose one interface per
            channel in a converter.
        metadata_key : str, optional
            Key under ``metadata["FiberPhotometry"]`` holding this interface's response-series
            metadata. When ``None`` (default), it is generated from the file name.
        read_kwargs : dict, optional
            Additional keyword arguments forwarded to ``pandas.read_csv`` to handle format quirks such
            as ``sep``, ``encoding``, ``decimal``, or ``skiprows``. Any value given here overrides the
            interface's own defaults (``header`` and ``float_precision``). Default is None.
        verbose : bool, default: False
            Whether to print status messages.
        """
        file_path = str(file_path)
        self._data_columns = [data_columns] if isinstance(data_columns, (str, int)) else list(data_columns)
        self._read_kwargs = self._resolve_read_kwargs(timestamps_column, read_kwargs)
        self._demux = demux

        # Up-front check (rather than a pandas read-time error deep in add_to_nwbfile): the file must
        # contain its data column(s), the timestamps column, and, for a column demux, the label column.
        # Uses the resolved read_kwargs so the header is parsed with the same dialect the data reads use.
        columns_present = [timestamps_column, *self._data_columns]
        if isinstance(demux, ColumnDemux):
            columns_present.append(demux.column)
        self._assert_columns_present(file_path, columns_present)

        if metadata_key is None:
            stem = Path(file_path).stem.replace(" ", "_").strip("_").lower()
            metadata_key = f"fiber_photometry_{stem}"

        # The file is the interface's single "stream": stream_names carries the path, and the base
        # hands it back to the reading seams below to build one response series. timestamps_column is
        # the only source config the seams read back from source_data.
        super().__init__(
            stream_names=[file_path],
            timestamps_column=timestamps_column,
            metadata_key=metadata_key,
            verbose=verbose,
        )

    @staticmethod
    def _resolve_read_kwargs(timestamps_column: str | int, read_kwargs: dict | None) -> dict:
        """Resolve the canonical ``pandas.read_csv`` kwargs once, for every read this interface makes.

        ``header`` is fixed by how columns are addressed: a positional (``int``) ``timestamps_column``
        means a header-less file (``header=None``), a named (``str``) one means a header row
        (``header=0``). ``float_precision="round_trip"`` uses an exact, platform-independent float parser
        (pandas's default C parser rounds the final ULP differently across platforms). Caller-supplied
        ``read_kwargs`` override these defaults.
        """
        header = None if isinstance(timestamps_column, int) else 0
        return {"header": header, "float_precision": "round_trip", **(read_kwargs or dict())}

    def _read_csv(self, file_path: str, **call_kwargs) -> pd.DataFrame:
        """Read a CSV through this interface's resolved ``read_kwargs``, plus any per-call overrides.

        The single ``pandas.read_csv`` entry point for the interface, so every read -- the data reads and
        the up-front column checks alike -- parses the file with the same dialect.
        """
        return pd.read_csv(file_path, **{**self._read_kwargs, **call_kwargs})

    def _assert_columns_present(self, file_path: str, columns: list[str | int]) -> None:
        """Assert that a CSV file contains all of ``columns`` (by header name, or by 0-based position)."""
        # A str column specifier means a headered file; an int means a header-less, positional file.
        header_less = isinstance(columns[0], int)
        if header_less:
            num_columns = self._read_csv(file_path, nrows=1).shape[1]
            missing = [column for column in columns if column >= num_columns]
            assert (
                not missing
            ), f"Column index(es) {missing} out of range for '{file_path}', which has {num_columns} columns."
        else:
            available_columns = list(self._read_csv(file_path, nrows=0).columns)
            missing = [column for column in columns if column not in available_columns]
            assert (
                not missing
            ), f"Column(s) {missing} not found in '{file_path}'. Available columns: {available_columns}."

    @classmethod
    def get_available_columns(cls, file_path: FilePath, read_kwargs: dict | None = None) -> list[str]:
        """Return the header column names of a CSV file (empty for a header-less file).

        A convenience for picking ``data_columns`` / ``timestamps_column`` on a headered file; a
        header-less file is addressed by positional integer indices instead.

        Parameters
        ----------
        file_path : FilePath
            The CSV file to read the header from.
        read_kwargs : dict, optional
            Additional keyword arguments forwarded to ``pandas.read_csv`` (e.g. ``sep``, ``encoding``,
            ``skiprows``) so the header is parsed with the same dialect the interface will read the file
            with. Pass the same value you would give the interface's ``read_kwargs``. Default is None.
        """
        return list(pd.read_csv(file_path, nrows=0, **(read_kwargs or dict())).columns)

    def _read_dataframe(self, *, file_path: str, columns: list[str | int]) -> pd.DataFrame:
        """Read the given columns of a CSV file into a DataFrame, demultiplexed to this channel.

        With a column demux the label column is read alongside ``columns`` and only the rows whose value
        in it equals ``value`` are kept; with a stride demux the leading ``skip_rows`` are dropped and
        every ``channels``-th row from ``index`` is taken. Data and timestamps go through this same
        method, so both are demuxed identically and stay row-aligned.
        """
        # Demux is a single-file feature set only in this class's __init__; a subclass that reuses this
        # read path without demuxing (MultiFileCSVFiberPhotometryInterface) simply never sets it.
        demux = getattr(self, "_demux", None)
        if demux is None:
            return self._read_csv(file_path, usecols=columns)
        if isinstance(demux, ColumnDemux):
            read_columns = columns if demux.column in columns else [*columns, demux.column]
            dataframe = self._read_csv(file_path, usecols=read_columns)
            return dataframe[dataframe[demux.column] == demux.value]
        dataframe = self._read_csv(file_path, usecols=columns)
        return dataframe.iloc[demux.skip_rows :].iloc[demux.index :: demux.channels]

    def _get_stream_data(self, *, stream_name: str) -> np.ndarray:
        # stream_name is a file path; return that file's data columns as (num_samples, num_data_columns).
        dataframe = self._read_dataframe(file_path=stream_name, columns=self._data_columns)
        return dataframe[self._data_columns].to_numpy()

    def _get_stream_timestamps(self, *, stream_name: str) -> np.ndarray:
        # stream_name is a file path; the series' time axis is the timestamps column of that file.
        timestamps_column = self.source_data["timestamps_column"]
        dataframe = self._read_dataframe(file_path=stream_name, columns=[timestamps_column])
        return dataframe[timestamps_column].to_numpy().astype("float64")
