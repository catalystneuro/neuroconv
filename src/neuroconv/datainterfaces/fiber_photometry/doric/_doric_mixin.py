import warnings
from datetime import datetime

import numpy as np

_DORIC_CREATED_FMT = "%a %b %d %H:%M:%S %Y"


class DoricLoadMixin:
    """Shared .doric HDF5 reading logic for interfaces constructed with ``file_path``.

    Provides stream discovery (walking ``DataAcquisition`` for groups with a ``Time`` sibling
    dataset) and per-stream data/timestamp/session-start-time reading. The host interface must
    populate ``self.source_data["file_path"]`` with the path to the ``.doric`` file and
    ``self._streams`` (via :meth:`_discover_streams_from_file`) before reading data.
    """

    @staticmethod
    def _discover_streams(f) -> dict:
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
                        "data_path": f"DataAcquisition/{name}/{key}",
                        "time_path": f"DataAcquisition/{name}/Time",
                    }

        f["DataAcquisition"].visititems(_visit)
        return streams

    def _discover_streams_from_file(self) -> dict:
        import h5py

        with h5py.File(self.source_data["file_path"], "r") as f:
            return self._discover_streams(f)

    @classmethod
    def get_available_streams(cls, file_path) -> list[str]:
        """Return the names of the streams available in a .doric file.

        Parameters
        ----------
        file_path : FilePath
            Path to the .doric HDF5 file.

        Returns
        -------
        list[str]
            Sorted list of stream names.
        """
        import h5py

        with h5py.File(file_path, "r") as f:
            streams = cls._discover_streams(f)
        return sorted(streams)

    def _get_session_start_time(self) -> datetime | None:
        """Parse the session start time from the file's ``Created`` attribute, if present."""
        import h5py

        with h5py.File(self.source_data["file_path"], "r") as f:
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

    def _get_stream_data_full(self, stream_name: str) -> np.ndarray:
        import h5py

        info = self._streams[stream_name]
        with h5py.File(self.source_data["file_path"], "r") as f:
            return np.asarray(f[info["data_path"]][:])

    def _get_stream_timestamps_full(self, stream_name: str) -> np.ndarray:
        import h5py

        info = self._streams[stream_name]
        with h5py.File(self.source_data["file_path"], "r") as f:
            return np.asarray(f[info["time_path"]][:])

    def _load_stream_array(self, stream_name: str, t1: float = 0.0, t2: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        """Load a single stream's data and timestamps from the HDF5 file, restricted to [t1, t2].

        Parameters
        ----------
        stream_name : str
            A key returned by :py:meth:`get_available_streams`.
        t1 : float
            Start time in seconds (original clock). 0 means beginning of recording.
        t2 : float
            End time in seconds (original clock). 0 means end of recording.

        Returns
        -------
        data : np.ndarray, shape (N,)
        timestamps : np.ndarray, shape (N,)
        """
        import h5py

        info = self._streams[stream_name]
        with h5py.File(self.source_data["file_path"], "r") as f:
            time_data = f[info["time_path"]][:]
            start_idx = int(np.searchsorted(time_data, t1)) if t1 > 0.0 else 0
            end_idx = int(np.searchsorted(time_data, t2, side="right")) if t2 > 0.0 else len(time_data)
            return f[info["data_path"]][start_idx:end_idx], time_data[start_idx:end_idx]
