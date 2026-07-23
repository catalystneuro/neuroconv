"""Interface for discrete events (digital IO) from Doric Neuroscience Studio ``.doric`` files."""

import warnings
from datetime import datetime

import numpy as np
from pydantic import FilePath, validate_call

from neuroconv.utils import DeepDict

from ..baseeventsinterface import BaseEventsInterface, _EventsData


class DoricEventsInterface(BaseEventsInterface):
    """Convert discrete events from Doric Neuroscience Studio ``.doric`` digital IO to NWB.

    A ``.doric`` file records digital IO lines (e.g. a camera-exposure TTL, a behavior trigger) as
    sampled ``0``/``1`` traces. This interface detects each line's rising edges (``0 -> 1`` transitions)
    as event onsets and writes one ``pynwb.event.EventsTable`` per line into ``nwbfile.events``. Every
    ``DigitalIO`` line that toggles is converted; a constant line (no transition) is skipped.
    ``session_start_time`` is read from the file when present.

    Only the modern ``.doric`` HDF5 layout is supported; the legacy "EPConsole" layout and the
    DoricStudio CSV export are not read for events.
    """

    keywords = ("events", "Doric")
    display_name = "DoricEvents"
    info = "Data Interface for converting discrete events (digital IO) from Doric Neuroscience Studio files."
    associated_suffixes = ("doric",)
    # strptime format of the .doric HDF5 "Created" attribute, parsed for session_start_time.
    _created_format = "%a %b %d %H:%M:%S %Y"

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the DoricEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.doric`` HDF5 file.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata.
            If None (default), ``"doric_events"`` is used.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            file_path=file_path,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "doric_events"
        self._event_source_paths = self._discover_event_sources(self.source_data["file_path"])

    @staticmethod
    def _discover_event_sources(file_path) -> dict[str, dict]:
        """Return ``event_type_source_id -> {data_path, time_path}`` for every digital line in the file.

        Walks ``DataAcquisition`` for ``DigitalIO`` groups (a group whose leaf name is ``DigitalIO``
        holding a ``Time`` dataset) and treats each non-Time 1-D dataset as a digital line. The line's
        dataset key is its ``event_type_source_id`` (identity-in-header, e.g. ``Camera1``, ``DigitalCh1``).
        """
        import h5py

        event_source_paths: dict[str, dict] = {}
        with h5py.File(file_path, "r") as f:
            if "DataAcquisition" not in f:
                return event_source_paths

            def _visit(name: str, obj) -> None:
                if not isinstance(obj, h5py.Group):
                    return
                if name.rsplit("/", 1)[-1] != "DigitalIO" or "Time" not in obj:
                    return
                for key in obj:
                    if key == "Time":
                        continue
                    item = obj[key]
                    if isinstance(item, h5py.Dataset) and item.ndim == 1:
                        # The digital line's name is its event_type_source_id (identity-in-header).
                        event_source_paths[key] = {
                            "data_path": f"DataAcquisition/{name}/{key}",
                            "time_path": f"DataAcquisition/{name}/Time",
                        }

            f["DataAcquisition"].visititems(_visit)
        return event_source_paths

    def _get_session_start_time(self) -> datetime | None:
        """Parse the session start time from the file's ``Created`` attribute, if present."""
        import h5py

        with h5py.File(self.source_data["file_path"], "r") as f:
            created_str = f.attrs.get("Created", "")
        if not created_str:
            return None
        try:
            return datetime.strptime(created_str, self._created_format)
        except ValueError:
            warnings.warn(
                f"Could not parse 'Created' attribute from .doric file (got {created_str!r}). "
                f"Expected format: '{self._created_format}'. Session start time will not be set automatically."
            )
            return None

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the DoricEventsInterface.

        ``NWBFile/session_start_time`` is populated from the file's ``Created`` attribute when present.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        session_start_time = self._get_session_start_time()
        if session_start_time is not None:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Identity-in-header: each event_type_source_id (a digital line's name) is its own event type,
        # and event_name (the human-facing label) defaults to that handle. A .doric file ships no meaning
        # for a line, so only the name is seeded here. Only lines that carry at least one rising edge
        # appear (a constant line is skipped), matching _get_events_data_dict.
        for event_type_source_id in self._get_events_data_dict():
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = {
                "event_name": event_type_source_id
            }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation by rising-edge detecting each digital line, cached.

        Each discovered digital line becomes one :class:`_EventsData` keyed by its ``event_type_source_id``
        (the line name): its rising edges (``0 -> 1`` transitions in the sampled binary trace) are the
        onset timestamps, taken from the shared ``Time`` vector. A line with no rising edge (constant, or
        already high at the first sample) carries no event and is skipped, so the empty state never reaches
        the writer.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        import h5py

        events_data_dict = {}
        with h5py.File(self.source_data["file_path"], "r") as f:
            for event_type_source_id, paths in self._event_source_paths.items():
                data = np.asarray(f[paths["data_path"]][:])
                time = np.asarray(f[paths["time_path"]][:])
                # A digital line is a densely sampled 0/1 trace; its events are the rising edges (a
                # low->high transition). Treat any value above 0.5 as high, robust to float 0.0/1.0.
                high = data > 0.5
                rising_edges = np.flatnonzero(~high[:-1] & high[1:]) + 1
                if rising_edges.size == 0:
                    continue  # a constant / never-rising line has no onset; skip it entirely
                onsets = time[rising_edges]
                events_data_dict[event_type_source_id] = _EventsData(
                    event_type_source_id=event_type_source_id, timestamps=onsets
                )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
