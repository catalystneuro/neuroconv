"""Interface for discrete events (digital IO) from Doric Neuroscience Studio ``.doric`` files."""

import warnings
from datetime import datetime

import numpy as np
from pydantic import FilePath, validate_call

from neuroconv.utils import DeepDict

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools.events import validate_event_specs
from ....tools.signal_processing import discretize_trace


class DoricEventsInterface(BaseEventsInterface):
    """Convert discrete events (digital IO) from Doric Neuroscience Studio ``.doric`` files to NWB.

    A ``.doric`` file records digital IO lines (e.g. a camera-exposure TTL, a behavior trigger) as
    sampled ``0``/``1`` traces under ``DigitalIO`` groups. This interface edge-detects each line and
    writes one ``pynwb.event.EventsTable`` per line into ``nwbfile.events``. How each line's transitions
    become events is set per line by ``event_specs``; by default every line is read as a ``high_period``
    (each rising edge is an event onset, its duration the span to the next falling edge). A line that
    never toggles is skipped. ``session_start_time`` is read from the file's ``Created`` attribute when
    present.

    Only the modern ``.doric`` HDF5 layout (root group ``DataAcquisition``) is read here; the legacy
    "EPConsole" layout is not yet supported, and the DoricStudio CSV export is handled by
    :class:`.DoricCSVEventsInterface`.
    """

    keywords = ("events", "Doric")
    display_name = "DoricEvents"
    info = "Data Interface for converting discrete events (digital IO) from Doric Neuroscience Studio files."
    associated_suffixes = ("doric",)
    # strptime format of the .doric HDF5 "Created" attribute, parsed for session_start_time.
    _created_format = "%a %b %d %H:%M:%S %Y"
    # The reading a digital line defaults to when event_specs does not set one: the lossless durative
    # reading (onset at the rising edge, duration to the falling edge, for an active-high line).
    _default_detect = "high_period"

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        event_specs: dict | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the DoricEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.doric`` HDF5 file.
        event_specs : dict, optional
            Per digital line, how its transitions become events, keyed by the line's name (its
            ``DigitalIO`` dataset key, e.g. ``{"Camera1": {"detect": "high_period"}}``). ``detect`` is
            one of ``"rising"`` / ``"falling"`` (a point event at each edge) or ``"high_period"`` /
            ``"low_period"`` (a durative event, onset at one edge and duration to the next opposite
            edge), default ``"high_period"`` (lossless for an active-high line; use ``"low_period"`` for
            an active-low line). If None (default), every digital line in the file is read as a
            ``high_period``. When given, only the named lines are read (selection by inclusion).
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
        # available_lines: source_id (the DigitalIO dataset key, e.g. "Camera1") -> its
        # {data_path, time_path} handle in the HDF5 file.
        self._available_lines = self._discover_event_sources(self.source_data["file_path"])
        self._resolved_specs = self._resolve_event_specs(event_specs)

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

    def _resolve_event_specs(self, event_specs: dict | None) -> dict:
        """Turn ``event_specs`` into resolved fields ``{event_type_source_id: {"detect", "paths"}}``.

        ``None`` produces the code default (:meth:`_default_event_specs`); a user dict is first validated
        (:func:`~neuroconv.tools.events.validate_event_specs`, which raises). Both are then parsed into
        the internal shape here. Each digital line's dataset key (e.g. ``Camera1``) is its
        ``event_type_source_id`` (identity-in-header).
        """
        if event_specs is None:
            event_specs = self._default_event_specs()
        else:
            validate_event_specs(event_specs, self._available_lines)
        return {
            source_id: {"detect": entry.get("detect", self._default_detect), "paths": self._available_lines[source_id]}
            for source_id, entry in event_specs.items()
        }

    def _default_event_specs(self) -> dict:
        """The code default (no user ``event_specs``): every digital line with the default ``detect``.

        Trusted (not user input), so it skips validation and flows straight into the parse; a line that
        never toggles is skipped later in :meth:`_get_events_data_dict`.
        """
        return {source_id: {"detect": self._default_detect} for source_id in self._available_lines}

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
        """Build the internal event representation by edge-detecting each digital line, cached.

        Each selected digital line becomes one :class:`_EventsData` keyed by its ``event_type_source_id``
        (the line name): its trace is edge-detected per the line's ``detect`` (via
        :func:`discretize_trace`) into onset frames and, for a durative reading, per-event durations. The
        onset timestamps are read from that line's ``Time`` dataset; durations (in frames) are scaled to
        seconds by the file's sampling period. A line with no event (constant, or never opening) is
        skipped, so the empty state never reaches the writer.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        import h5py

        events_data_dict = {}
        with h5py.File(self.source_data["file_path"], "r") as f:
            for event_type_source_id, spec in self._resolved_specs.items():
                paths = spec["paths"]
                data = np.asarray(f[paths["data_path"]][:], dtype="float64")
                time = np.asarray(f[paths["time_path"]][:], dtype="float64")
                frame_period = float(np.median(np.diff(time)))  # regular Doric clock; duration frames -> seconds
                # A digital line is a densely sampled 0/1 trace; threshold=0.5 discretizes it strictly.
                onset_frames, duration_frames = discretize_trace(data, spec["detect"], threshold=0.5)
                if onset_frames.size == 0:
                    continue  # a line with no matching edge has no event; skip it entirely
                onsets = time[onset_frames]
                durations = None if duration_frames is None else duration_frames * frame_period
                events_data_dict[event_type_source_id] = _EventsData(
                    event_type_source_id=event_type_source_id, timestamps=onsets, durations=durations
                )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
