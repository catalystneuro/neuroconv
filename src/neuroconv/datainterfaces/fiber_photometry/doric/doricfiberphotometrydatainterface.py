"""Interface for Doric Neuroscience Studio fiber photometry data (.doric HDF5 or DoricStudio CSV files)."""

import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call

from neuroconv.utils import DeepDict

from ..basefiberphotometryinterface import BaseFiberPhotometryInterface

_DORIC_CREATED_FMT = "%a %b %d %H:%M:%S %Y"
_CSV_TIME_COLUMN_CANDIDATES = ("time", "time(s)")


class DoricFiberPhotometryInterface(BaseFiberPhotometryInterface):
    """Interface for fiber photometry data from Doric Neuroscience Studio.

    Reads either of the two formats produced by Doric Neuroscience Studio (compatible with BBC300,
    BBC600, FPC, and other Doric acquisition hardware) and writes a single
    ``FiberPhotometryResponseSeries`` to NWB using the ndx-fiber-photometry extension, assembled
    from one or more input streams; use multiple interfaces (with distinct ``metadata_key`` values)
    in a converter to write several series sharing one ``FiberPhotometryTable``.

    * ``.doric`` (HDF5): stream names are auto-discovered by walking ``DataAcquisition`` for groups
      that contain a ``Time`` sibling dataset. Each non-Time 1-D dataset found this way becomes a
      stream whose name is the path relative to ``DataAcquisition`` with ``/`` replaced by ``_``
      (e.g. ``BBC300_ROISignals_Series0001_CAM1EXC1_ROI01``). Older "EPConsole"-style exports that
      instead nest each stream under ``Traces/<console>/<stream>/<stream>`` (with a sibling
      ``Traces/<console>/Time(s)/...`` group holding the shared timestamps) are also supported.
    * ``.csv`` (DoricStudio CSV export): one shared time column (matched case-insensitively against
      ``"Time(s)"``/``"time"``) plus one or more data columns; each data column is a stream named
      after its column header (e.g. ``sig``, ``ref``). The time column may be on the first or second
      line (older exports prepend a channel/device "group" line above the real header), and trailing
      unnamed (empty) columns are ignored.

    Call :meth:`get_available_streams` to discover stream names for either format.
    """

    display_name = "DoricFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from Doric Neuroscience Studio."
    associated_suffixes = ("doric", "csv")

    @validate_call
    def __init__(
        self,
        *,
        file_path: FilePath,
        stream_names: str | list[str],
        metadata_key: str | None = None,
        stream_indices: list[int] | None = None,
        verbose: bool = False,
    ):
        """Initialize the DoricFiberPhotometryInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.doric`` HDF5 file or DoricStudio ``.csv`` export.
        stream_names : str or list of str
            The input stream(s) whose samples are assembled into this interface's single
            ``FiberPhotometryResponseSeries``. Call :meth:`get_available_streams` to discover them.
        metadata_key : str, optional
            Key under ``metadata["FiberPhotometry"]`` holding this interface's response-series
            metadata. When ``None`` (default), it is generated from ``stream_names``.
        stream_indices : list of int, optional
            Column indices selecting which channels of the (column-stacked) stream data to keep.
        verbose : bool, default: False
            Whether to print status messages.
        """
        super().__init__(
            file_path=file_path,
            stream_names=stream_names,
            metadata_key=metadata_key,
            stream_indices=stream_indices,
            verbose=verbose,
        )
        self._streams: dict[str, dict] = self._discover_streams(self.source_data["file_path"])

    # ------------------------------------------------------------------
    # Stream discovery
    # ------------------------------------------------------------------

    @staticmethod
    def _is_csv(file_path) -> bool:
        return Path(file_path).suffix.lower() == ".csv"

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
        return sorted(cls._discover_streams(file_path))

    @classmethod
    def _discover_streams(cls, file_path) -> dict:
        """Dispatch to the CSV or HDF5 stream discoverer based on the file extension.

        For HDF5, the modern ``DataAcquisition``-based layout is tried first, falling back to the
        legacy ``Traces``-based layout when the former yields no streams.
        """
        if cls._is_csv(file_path):
            return cls._discover_csv_streams(file_path)
        import h5py

        with h5py.File(file_path, "r") as f:
            return cls._discover_hdf5_streams(f) or cls._discover_hdf5_streams_legacy(f)

    @staticmethod
    def _discover_hdf5_streams(f) -> dict:
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
    def _discover_hdf5_streams_legacy(f) -> dict:
        """Walk the legacy ``Traces`` layout (older "EPConsole" .doric exports).

        Under ``Traces/<console>/``, each stream is its own group holding a single dataset with the
        same name as the group (e.g. ``Traces/Console/AIn-1 - Raw/AIn-1 - Raw``), and the shared
        timestamps live in a sibling time-like group (e.g. ``Traces/Console/Time(s)/Console_time(s)``).
        """
        import h5py

        streams: dict[str, dict] = {}
        if "Traces" not in f:
            return streams

        def _visit(name: str, obj) -> None:
            if not isinstance(obj, h5py.Group):
                return
            time_child_name = next(
                (
                    child_name
                    for child_name in obj
                    if isinstance(obj[child_name], h5py.Group)
                    and child_name.strip().lower() in _CSV_TIME_COLUMN_CANDIDATES
                ),
                None,
            )
            if time_child_name is None:
                return
            time_group = obj[time_child_name]
            time_datasets = [key for key in time_group if isinstance(time_group[key], h5py.Dataset)]
            if len(time_datasets) != 1:
                return
            time_path = f"Traces/{name}/{time_child_name}/{time_datasets[0]}"

            for child_name in obj:
                if child_name == time_child_name:
                    continue
                child = obj[child_name]
                if not isinstance(child, h5py.Group) or child_name not in child:
                    continue
                data_item = child[child_name]
                if isinstance(data_item, h5py.Dataset) and data_item.ndim == 1:
                    stream_name = f"{name}/{child_name}".replace("/", "_")
                    streams[stream_name] = {
                        "format": "hdf5",
                        "data_path": f"Traces/{name}/{child_name}/{child_name}",
                        "time_path": time_path,
                    }

        f["Traces"].visititems(_visit)
        return streams

    @classmethod
    def _discover_csv_streams(cls, file_path) -> dict:
        """Return stream_name -> {header_row, data_column, time_column} from a CSV export."""
        header_row, time_column, columns = cls._locate_csv_header(file_path)
        return {
            column: {"format": "csv", "header_row": header_row, "data_column": column, "time_column": time_column}
            for column in columns
            if column != time_column and not column.startswith("Unnamed:")
        }

    @staticmethod
    def _locate_csv_header(file_path) -> tuple[int, str, list[str]]:
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

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        session_start_time = self._get_session_start_time()
        if session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata

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

    def _get_stream_data(self, *, stream_name: str) -> np.ndarray:
        info = self._streams[stream_name]
        if info["format"] == "csv":
            df = self._read_csv_dataframe(info["header_row"])
            return np.asarray(df[info["data_column"]].values)

        import h5py

        with h5py.File(self.source_data["file_path"], "r") as f:
            return np.asarray(f[info["data_path"]][:])

    def _get_stream_timestamps(self, *, stream_name: str) -> np.ndarray:
        info = self._streams[stream_name]
        if info["format"] == "csv":
            df = self._read_csv_dataframe(info["header_row"])
            return np.asarray(df[info["time_column"]].values)

        import h5py

        with h5py.File(self.source_data["file_path"], "r") as f:
            return np.asarray(f[info["time_path"]][:])
