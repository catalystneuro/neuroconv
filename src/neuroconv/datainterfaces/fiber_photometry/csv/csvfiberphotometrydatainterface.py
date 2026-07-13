"""Interface for raw fiber photometry data stored as per-stream CSV files."""

from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import DirectoryPath, validate_call

from ..basefiberphotometryinterface import BaseFiberPhotometryInterface


class CSVFiberPhotometryInterface(BaseFiberPhotometryInterface):
    """Data Interface for converting raw fiber photometry data from CSV files.

    This CSV format is a raw acquisition format, with one CSV per stream (e.g. a signal channel, an
    isosbestic control channel). Each data CSV has (at least) two columns -- ``timestamps`` (seconds)
    and ``data`` (fluorescence) -- and is named after its stream (``<stream_name>.csv``). Call
    :meth:`get_available_streams` to list the data streams discovered in a folder.

    Each interface writes a single ``FiberPhotometryResponseSeries``, assembled from one or more input
    streams; use multiple interfaces (with distinct ``metadata_key`` values) in a converter to write
    several series sharing one ``FiberPhotometryTable``.

    Notes
    -----
    Unlike the TDT format, CSV recordings carry no embedded recording-start timestamp, so
    :meth:`get_metadata` does NOT populate ``NWBFile/session_start_time``. The user must supply it via
    editable metadata.
    """

    display_name = "CSVFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from CSV files."
    associated_suffixes = ("csv",)

    @validate_call
    def __init__(
        self,
        *,
        folder_path: DirectoryPath,
        stream_names: str | list[str],
        metadata_key: str | None = None,
        stream_indices: list[int] | None = None,
        verbose: bool = False,
    ):
        """Initialize the CSVFiberPhotometryInterface.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder containing the per-stream CSV files.
        stream_names : str or list of str
            The input stream(s) -- CSV file stems (see :meth:`get_available_streams`) -- whose samples
            are column-stacked into this interface's single ``FiberPhotometryResponseSeries``.
        metadata_key : str, optional
            Key under ``metadata["FiberPhotometry"]`` holding this interface's response-series metadata.
            When ``None`` (default), it is generated from ``stream_names``.
        stream_indices : list of int, optional
            Column indices selecting which channels of the (column-stacked) stream data to keep.
        verbose : bool, default: False
            Whether to print status messages.
        """
        super().__init__(
            folder_path=folder_path,
            stream_names=stream_names,
            metadata_key=metadata_key,
            stream_indices=stream_indices,
            verbose=verbose,
        )

    @classmethod
    def get_available_streams(cls, folder_path: DirectoryPath) -> list[str]:
        """Return the names of the data streams (CSV file stems) discovered in the folder.

        Only the data CSVs (those with a ``data`` column) are streams; single-column event CSVs (e.g.
        TTLs) are excluded -- those belong to a separate events interface.
        """
        stream_names = []
        for path in sorted(Path(folder_path).glob("*.csv")):
            columns = [column.lower() for column in pd.read_csv(path, nrows=0).columns]
            if "data" in columns:
                stream_names.append(path.stem)
        return stream_names

    def _stream_csv_path(self, stream_name: str) -> Path:
        """Return the path to the CSV file backing the given stream."""
        return Path(self.source_data["folder_path"]) / f"{stream_name}.csv"

    def _get_stream_data(self, *, stream_name: str) -> np.ndarray:
        return pd.read_csv(self._stream_csv_path(stream_name), usecols=["data"])["data"].to_numpy()

    def _get_stream_timestamps(self, *, stream_name: str) -> np.ndarray:
        return pd.read_csv(self._stream_csv_path(stream_name), usecols=["timestamps"])["timestamps"].to_numpy()
