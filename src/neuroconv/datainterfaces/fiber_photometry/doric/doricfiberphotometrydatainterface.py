"""Interface for Doric Neuroscience Studio fiber photometry data (.doric HDF5 or DoricStudio CSV files)."""

import numpy as np
from pydantic import FilePath, validate_call

from neuroconv.utils import DeepDict

from ._doric_mixin import DoricLoadMixin
from ..basefiberphotometryinterface import BaseFiberPhotometryInterface


class DoricFiberPhotometryInterface(DoricLoadMixin, BaseFiberPhotometryInterface):
    """Interface for fiber photometry data from Doric Neuroscience Studio.

    Reads either of the two formats produced by Doric Neuroscience Studio (compatible with BBC300,
    BBC600, FPC, and other Doric acquisition hardware) and writes a single
    ``FiberPhotometryResponseSeries`` to NWB using the ndx-fiber-photometry extension, assembled
    from one or more input streams; use multiple interfaces (with distinct ``metadata_key`` values)
    in a converter to write several series sharing one ``FiberPhotometryTable``.

    * ``.doric`` (HDF5): stream names are auto-discovered by walking ``DataAcquisition`` for groups
      that contain a ``Time`` sibling dataset. Each non-Time 1-D dataset found this way becomes a
      stream whose name is the path relative to ``DataAcquisition`` with ``/`` replaced by ``_``
      (e.g. ``BBC300_ROISignals_Series0001_CAM1EXC1_ROI01``).
    * ``.csv`` (DoricStudio CSV export): one shared time column (matched case-insensitively against
      ``"Time(s)"``/``"time"``) plus one or more data columns; each data column is a stream named
      after its column header (e.g. ``sig``, ``ref``).

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
        self._streams: dict[str, dict] = self._discover_streams_from_file()

    def _get_stream_data(self, *, stream_name: str) -> np.ndarray:
        return self._get_stream_data_full(stream_name)

    def _get_stream_timestamps(self, *, stream_name: str) -> np.ndarray:
        return self._get_stream_timestamps_full(stream_name)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        session_start_time = self._get_session_start_time()
        if session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata
