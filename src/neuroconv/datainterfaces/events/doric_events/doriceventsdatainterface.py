"""Interface for discrete events (digital IO) from Doric Neuroscience Studio ``.doric`` files."""

import warnings
from datetime import datetime

import numpy as np
from pydantic import FilePath, validate_call

from neuroconv.utils import DeepDict

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools.events import resolve_detection_plan, validate_detection_configuration
from ....tools.signal_processing import discretize_trace


class DoricEventsInterface(BaseEventsInterface):
    """Convert discrete events (digital IO) from Doric Neuroscience Studio ``.doric`` files to NWB.

    A ``.doric`` file records digital IO lines (e.g. a camera-exposure TTL, a behavior trigger) as
    sampled ``0``/``1`` traces under ``DigitalIO`` groups. Each line is a *signal*, and the events derived
    from it are set by ``detection_configuration``: one entry per signal holding a list of detection
    specs, since a signal can yield more than one event type. Each event type is written as its own
    ``pynwb.event.EventsTable`` into ``nwbfile.events``. By default every line is read as a
    ``high_period`` (each rising edge is an event onset, its duration the span to the next falling edge).
    A line that never toggles is skipped. ``session_start_time`` is read from the file's ``Created``
    attribute when present.

    Only the modern ``.doric`` HDF5 layout (root group ``DataAcquisition``) is read here; the legacy
    "EPConsole" layout is not yet supported, and the DoricStudio CSV export is handled by
    :class:`.DoricCSVEventsInterface`.
    """

    keywords = ("events", "Doric")
    display_name = "DoricEvents"
    info = "Data Interface for converting discrete events (digital IO) from Doric Neuroscience Studio files."
    associated_suffixes = ("doric",)
    # strptime format of the .doric HDF5 "Created" attribute, parsed for session_start_time.
    _session_start_time_format = "%a %b %d %H:%M:%S %Y"

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        detection_configuration: dict | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the DoricEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.doric`` HDF5 file.
        detection_configuration : dict, optional
            Which digital lines to read and how, keyed by the line's ``signal_source_id`` (its
            ``DigitalIO`` dataset key, e.g. ``{"Camera1": [{"detection": "high_period"}]}``). Each value
            is a **list** of detection specs, one per event type derived from that line, since a line can
            yield more than one. A spec's ``detection`` is one of ``"rising"`` / ``"falling"`` (a point
            event at each edge) or ``"high_period"`` / ``"low_period"`` (a durative event, onset at one
            edge and duration to the next opposite edge), and it is required. ``signal_conditioning`` is
            omitted for a ``.doric`` line, which is already a ``0``/``1`` signal. An optional
            ``event_name`` replaces the derived identifier and pins it against later edits. If None
            (default), every digital line in the file is read as a ``high_period``, lossless for an
            active-high line; use ``"low_period"`` for an active-low one. When given, only the named
            lines are read.
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
        # available_signals: signal_source_id (the DigitalIO dataset key, e.g. "Camera1") -> its
        # descriptor. Every .doric digital line is kind "line", already a 0/1 signal, so conditioning is
        # always omittable here and a cut is never legal.
        self._available_signals = self._discover_signals(self.source_data["file_path"])
        # Validate a caller-supplied configuration eagerly (fail-fast at construction); the None default
        # is trusted. A spec is all-or-nothing, never half-filled from a default.
        if detection_configuration is not None:
            validate_detection_configuration(detection_configuration, self._available_signals)
        else:
            # The default, used only when the caller passes none: read every discovered line as a
            # "high_period", the lossless durative reading (onset at the rising edge, duration to the
            # falling edge, for an active-high line).
            detection_configuration = {
                signal_source_id: [{"detection": "high_period"}] for signal_source_id in self._available_signals
            }
        self._detection_configuration = detection_configuration
        # The resolved plan: event_type_source_id -> (signal_source_id, spec). One entry per event type,
        # with its identifier already derived, so nothing about the reading is left for read time.
        self._detection_plan = resolve_detection_plan(detection_configuration)

    @staticmethod
    def _discover_signals(file_path) -> dict[str, dict]:
        """Return ``signal_source_id -> {kind, data_path, time_path}`` for every digital line in the file.

        Walks ``DataAcquisition`` for ``DigitalIO`` groups (a group whose leaf name is ``DigitalIO``
        holding a ``Time`` dataset) and treats each non-Time 1-D dataset as a digital line. The line's
        dataset key is its ``signal_source_id`` (identity-in-header, e.g. ``Camera1``, ``DigitalCh1``).
        The ``DigitalIO`` group is what settles the kind structurally, with no data read.
        """
        import h5py

        available_signals: dict[str, dict] = {}
        with h5py.File(file_path, "r") as f:
            if "DataAcquisition" not in f:
                return available_signals

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
                        # The digital line's name is its signal_source_id (identity-in-header).
                        available_signals[key] = {
                            "kind": "line",
                            "data_path": f"DataAcquisition/{name}/{key}",
                            "time_path": f"DataAcquisition/{name}/Time",
                        }

            f["DataAcquisition"].visititems(_visit)
        return available_signals

    def _get_session_start_time(self) -> datetime | None:
        """Parse the session start time from the file's ``Created`` attribute, if present."""
        import h5py

        with h5py.File(self.source_data["file_path"], "r") as f:
            session_start_time_string = f.attrs.get("Created", "")
        if not session_start_time_string:
            return None
        try:
            return datetime.strptime(session_start_time_string, self._session_start_time_format)
        except ValueError:
            warnings.warn(
                f"Could not parse 'Created' attribute from .doric file (got {session_start_time_string!r}). "
                f"Expected format: '{self._session_start_time_format}'. Session start time will not be set automatically."
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

        # Each event_type_source_id resolved from the configuration is its own event type, and event_name
        # (the human-facing label) defaults to that identifier. A .doric file ships no meaning for a line,
        # so only the name is seeded here. Only event types that carry at least one event appear (a
        # constant line is skipped), matching _get_events_data_dict.
        for event_type_source_id in self._get_events_data_dict():
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = {
                "event_name": event_type_source_id
            }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation by edge-detecting each selected line, cached.

        Each entry of the resolved plan becomes one :class:`_EventsData` keyed by its
        ``event_type_source_id``: its signal's trace is edge-detected per the spec's ``detection`` (via
        :func:`discretize_trace`) into onset frames and, for a durative reading, per-event durations. The
        onset timestamps are read from that signal's ``Time`` dataset; durations (in frames) are scaled to
        seconds by the file's sampling period. An event type with no event (a constant line, or one that
        never opens) is skipped, so the empty state never reaches the writer.

        A ``.doric`` line is already a ``0``/``1`` signal, so no conditioning runs here and the reading is
        applied to the signal's own values.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        import h5py

        events_data_dict = {}
        with h5py.File(self.source_data["file_path"], "r") as f:
            for event_type_source_id, (signal_source_id, spec) in self._detection_plan.items():
                paths = self._available_signals[signal_source_id]
                data = np.asarray(f[paths["data_path"]][:], dtype="float64")
                time = np.asarray(f[paths["time_path"]][:], dtype="float64")
                frame_period = float(np.median(np.diff(time)))  # regular Doric clock; duration frames -> seconds
                # A digital line is a densely sampled 0/1 trace; threshold=0.5 discretizes it strictly.
                onset_frames, duration_frames = discretize_trace(data, spec["detection"], threshold=0.5)
                if onset_frames.size == 0:
                    continue  # an event type with no matching edge has no event; skip it entirely
                onsets = time[onset_frames]
                durations = None if duration_frames is None else duration_frames * frame_period
                events_data_dict[event_type_source_id] = _EventsData(
                    event_type_source_id=event_type_source_id, timestamps=onsets, durations=durations
                )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
