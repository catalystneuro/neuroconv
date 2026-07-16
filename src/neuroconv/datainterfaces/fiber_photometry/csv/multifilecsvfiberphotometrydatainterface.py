"""Interface aggregating several per-channel CSV files into one fiber photometry response series."""

from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import FilePath, validate_call

from .csvfiberphotometrydatainterface import CSVFiberPhotometryInterface
from ..basefiberphotometryinterface import BaseFiberPhotometryInterface


class MultiFileCSVFiberPhotometryInterface(CSVFiberPhotometryInterface):
    """Data Interface aggregating several per-channel CSV files into one fiber photometry series.

    Some acquisition formats write one CSV file per channel/region rather than one wide CSV -- GuPPy,
    for instance, stores each region in its own file whose channel identity lives in the *filename*.
    This interface reads ``data_columns`` from each file, in file-then-column order, and column-stacks
    them into this interface's single ``FiberPhotometryResponseSeries``. The channels share one time
    axis, taken from the first file's ``timestamps_column``.

    Because only channels on a common timebase can share one series, the first file must contain the
    ``timestamps_column``. Secondary files may omit it (their timestamps would be redundant); when a
    secondary file *does* contain it, the interface asserts it matches the first file's timestamps, so
    files that do not share a timebase fail loudly instead of producing a silently mis-timed series.

    For the common single-file case, use :class:`.CSVFiberPhotometryInterface` instead. To write
    several *separate* series (e.g. a signal and an isosbestic control) sharing one
    ``FiberPhotometryTable``, use one interface per series (with distinct ``metadata_key`` values) in
    a converter.

    Notes
    -----
    CSV recordings carry no embedded recording-start timestamp, so :meth:`get_metadata` does NOT
    populate ``NWBFile/session_start_time``. The user must supply it via editable metadata.
    """

    display_name = "MultiFileCSVFiberPhotometry"
    info = "Data Interface aggregating several per-channel CSV files into one fiber photometry series."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        file_paths: list[FilePath],
        *,
        data_columns: str | int | list[str | int],
        timestamps_column: str | int,
        metadata_key: str | None = None,
        read_kwargs: dict | None = None,
        verbose: bool = False,
    ):
        """Initialize the MultiFileCSVFiberPhotometryInterface.

        Parameters
        ----------
        file_paths : list of FilePath
            The per-channel CSV files, each contributing its ``data_columns`` as further channels of
            the single response series, in file-then-column order. The channels share the first file's
            time axis.
        data_columns : str, int, or list of str or int
            The data column(s), read from every file, whose samples are column-stacked into this
            interface's single ``FiberPhotometryResponseSeries``. A column name (for CSVs with a
            header row) or a positional index (0-based, for header-less CSVs).
        timestamps_column : str or int
            The column holding the timestamps (seconds) for the series' time axis, read from the first
            file. A column name for CSVs with a header row, or a positional index (0-based) for
            header-less CSVs.
        metadata_key : str, optional
            Key under ``metadata["FiberPhotometry"]`` holding this interface's response-series
            metadata. When ``None`` (default), it is generated from the file names.
        read_kwargs : dict, optional
            Additional keyword arguments forwarded to ``pandas.read_csv`` to handle format quirks such
            as ``sep``, ``encoding``, ``decimal``, or ``skiprows``. Any value given here overrides the
            interface's own defaults (``header`` and ``float_precision``). Default is None.
        verbose : bool, default: False
            Whether to print status messages.
        """
        self._file_paths = [str(file_path) for file_path in file_paths]
        self._data_columns = [data_columns] if isinstance(data_columns, (str, int)) else list(data_columns)
        self._read_kwargs = read_kwargs or dict()

        # Up-front check: the first file must contain the timestamps column and its data column(s);
        # every other file must contain its data column(s) (its timestamps, if present, are checked for
        # alignment below). Reuses the parent's per-file column primitive.
        self._assert_columns_present(self._file_paths[0], [timestamps_column, *self._data_columns])
        for file_path in self._file_paths[1:]:
            self._assert_columns_present(file_path, self._data_columns)

        if metadata_key is None:
            stems = [Path(file_path).stem.replace(" ", "_").strip("_").lower() for file_path in self._file_paths]
            metadata_key = "_".join(["fiber_photometry", *stems])

        # Each file is one stackable "stream" for the base: stream_names carries the paths, and the
        # base column-stacks the files into one series. Bypasses the single-file parent __init__
        # (different signature) and initializes the base directly.
        BaseFiberPhotometryInterface.__init__(
            self,
            stream_names=self._file_paths,
            timestamps_column=timestamps_column,
            metadata_key=metadata_key,
            verbose=verbose,
        )
        self._assert_timestamps_aligned(timestamps_column)

    def _assert_timestamps_aligned(self, timestamps_column: str | int) -> None:
        """Assert that every file carrying the timestamps column agrees with the first file's timebase.

        Only channels on a common time axis can be column-stacked into one series. Secondary files may
        omit their (redundant) timestamps column; those that keep it must match the first file, so
        misaligned files fail loudly instead of being silently pinned to the first file's timestamps.
        """
        reference_timestamps = self._get_stream_timestamps(stream_name=self._file_paths[0])
        for file_path in self._file_paths[1:]:
            if not self._file_has_column(file_path, timestamps_column):
                continue
            timestamps = self._get_stream_timestamps(stream_name=file_path)
            assert timestamps.shape == reference_timestamps.shape and np.allclose(timestamps, reference_timestamps), (
                f"Timestamps in '{file_path}' do not match the first file's timestamps. Only channels "
                "on a common time axis can be aggregated into one FiberPhotometryResponseSeries; use "
                "separate interfaces for files that do not share a timebase."
            )

    @staticmethod
    def _file_has_column(file_path: str, column: str | int) -> bool:
        """Whether a CSV file contains the given column (by header name, or by 0-based position)."""
        if isinstance(column, int):
            num_columns = pd.read_csv(file_path, nrows=1, header=None).shape[1]
            return column < num_columns
        return column in list(pd.read_csv(file_path, nrows=0).columns)
