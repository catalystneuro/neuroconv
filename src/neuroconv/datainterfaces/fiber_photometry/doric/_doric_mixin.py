import warnings
from datetime import datetime
from pathlib import Path

import numpy as np

_DORIC_CREATED_FMT = "%a %b %d %H:%M:%S %Y"
_CSV_TIME_COLUMN_CANDIDATES = ("time", "time(s)")


class DoricLoadMixin:
    """Shared reading logic for Doric Neuroscience Studio fiber photometry files.

    Supports two export formats:

    * ``.doric`` (HDF5): streams are discovered by walking ``DataAcquisition`` for groups that
      contain a ``Time`` sibling dataset; each non-Time 1-D dataset found this way is a stream.
    * ``.csv`` (DoricStudio CSV export): one shared time column (matched case-insensitively
      against ``"Time(s)"``/``"time"``) plus one or more data columns, each of which is a stream.
      The time column may be on the first or second line (older exports prepend a channel/device
      "group" line above the real header), and trailing unnamed (empty) columns are ignored.

    The host interface must populate ``self.source_data["file_path"]`` with the path to the file
    and ``self._streams`` (via :meth:`_discover_streams_from_file`) before reading data.
    """

    @staticmethod
    def _is_csv(file_path) -> bool:
        return Path(file_path).suffix.lower() == ".csv"

    # ------------------------------------------------------------------
    # Stream discovery
    # ------------------------------------------------------------------

    @staticmethod
    def _discover_streams_hdf5(f) -> dict:
        """Walk DataAcquisition and return stream_name -> {data_path, time_path}."""
        import h5py

        streams: dict[str, dict] = {}
        if "DataAcquisition" not in f:
            return streams

        def _visit(name: str, obj) -> None:
            if not isinstance(obj, h5py.Group):
                return
            if "Time" not in obj:
                return
            for key in obj:
                if key == "Time":
                    continue
                item = obj[key]
                if isinstance(item, h5py.Dataset) and item.ndim == 1:
                    stream_name = f"{name}/{key}".replace("/", "_")
                    streams[stream_name] = {
                        "format": "hdf5",
                        "data_path": f"DataAcquisition/{name}/{key}",
                        "time_path": f"DataAcquisition/{name}/Time",
                    }

        f["DataAcquisition"].visititems(_visit)
        return streams

    @staticmethod
    def _find_csv_header_row_and_time_column(file_path) -> tuple[int, str, list[str]]:
        """Locate the header row and time column of a DoricStudio CSV export.

        Most exports have the column names on the first line (e.g. ``time,ref,sig``). Older Doric
        Neuroscience Studio exports instead prepend a channel/device "group" line above the real
        header (e.g. ``---,Analog In. | Ch.1,...`` followed by ``Time(s),AIn-1 - Dem (ref),...``).
        Both are handled by probing candidate header rows for one that contains a recognized time
        column.
        """
        import pandas as pd

        for header_row in (0, 1):
            columns = [str(column) for column in pd.read_csv(file_path, header=header_row, nrows=0).columns]
            time_column = next(
                (column for column in columns if column.strip().lower() in _CSV_TIME_COLUMN_CANDIDATES), None
            )
            if time_column is not None:
                return header_row, time_column, columns
        raise ValueError(
            f"Could not find a time column in {file_path}. Expected one of "
            f"{_CSV_TIME_COLUMN_CANDIDATES} (case-insensitive) on the first or second line."
        )

    @classmethod
    def _discover_streams_csv(cls, file_path) -> dict:
        """Return stream_name -> {header_row, data_column, time_column} from a CSV export."""
        header_row, time_column, columns = cls._find_csv_header_row_and_time_column(file_path)
        return {
            column: {"format": "csv", "header_row": header_row, "data_column": column, "time_column": time_column}
            for column in columns
            if column != time_column and not column.startswith("Unnamed:")
        }

    @classmethod
    def _discover_streams_from_path(cls, file_path) -> dict:
        if cls._is_csv(file_path):
            return cls._discover_streams_csv(file_path)
        import h5py

        with h5py.File(file_path, "r") as f:
            return cls._discover_streams_hdf5(f)

    def _discover_streams_from_file(self) -> dict:
        return self._discover_streams_from_path(self.source_data["file_path"])

    @classmethod
    def get_available_streams(cls, file_path) -> list[str]:
        """Return the names of the streams available in a Doric ``.doric`` or ``.csv`` file.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.doric`` HDF5 file or DoricStudio CSV export.

        Returns
        -------
        list[str]
            Sorted list of stream names.
        """
        return sorted(cls._discover_streams_from_path(file_path))

    # ------------------------------------------------------------------
    # Session start time (HDF5 only; not embedded in the CSV export)
    # ------------------------------------------------------------------

    def _get_session_start_time(self) -> datetime | None:
        """Parse the session start time from the file's ``Created`` attribute, if present."""
        file_path = self.source_data["file_path"]
        if self._is_csv(file_path):
            return None

        import h5py

        with h5py.File(file_path, "r") as f:
            created_str = f.attrs.get("Created", "")
        if not created_str:
            return None
        try:
            return datetime.strptime(created_str, _DORIC_CREATED_FMT)
        except ValueError:
            warnings.warn(
                f"Could not parse 'Created' attribute from .doric file (got {created_str!r}). "
                f"Expected format: '{_DORIC_CREATED_FMT}'. Session start time will not be set automatically."
            )
            return None

    # ------------------------------------------------------------------
    # Per-stream data / timestamps
    # ------------------------------------------------------------------

    def _read_csv_dataframe(self, header_row: int):
        cache = getattr(self, "_csv_dataframes", None)
        if cache is None:
            cache = self._csv_dataframes = {}
        if header_row not in cache:
            import pandas as pd

            cache[header_row] = pd.read_csv(self.source_data["file_path"], header=header_row)
        return cache[header_row]

    def _get_stream_data_full(self, stream_name: str) -> np.ndarray:
        info = self._streams[stream_name]
        if info["format"] == "csv":
            df = self._read_csv_dataframe(info["header_row"])
            return np.asarray(df[info["data_column"]].values)

        import h5py

        with h5py.File(self.source_data["file_path"], "r") as f:
            return np.asarray(f[info["data_path"]][:])

    def _get_stream_timestamps_full(self, stream_name: str) -> np.ndarray:
        info = self._streams[stream_name]
        if info["format"] == "csv":
            df = self._read_csv_dataframe(info["header_row"])
            return np.asarray(df[info["time_column"]].values)

        import h5py

        with h5py.File(self.source_data["file_path"], "r") as f:
            return np.asarray(f[info["time_path"]][:])
