"""Interface for discrete events (digital IO) from Doric Neuroscience Studio ``.doric`` files."""

import warnings
from datetime import datetime

import numpy as np
from pydantic import FilePath, validate_call

from neuroconv.utils import DeepDict

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools.events import (
    _get_event_type_source_ids,
    resolve_detection_plan,
    validate_detection_configuration,
)
from ....tools.signal_processing import (
    _condition_signal,
    _detect_events,
    _frames_to_seconds,
)


class DoricEventsInterface(BaseEventsInterface):
    """Convert discrete events (digital IO) from Doric Neuroscience Studio ``.doric`` files to NWB.

    A ``.doric`` file records digital IO lines (e.g. a camera-exposure TTL, a behavior trigger) as
    sampled ``0``/``1`` traces under ``DigitalIO`` groups. Each line is a *signal*, and the events derived
    from it are set by ``detection_configuration``: one entry per signal holding a list of detection
    specs, since a signal can yield more than one event type. Each event type is written as its own
    ``pynwb.event.EventsTable`` into ``nwbfile.events``. By default every line is read as a
    ``high_period`` (each rising edge is an event onset, its duration the span to the next falling edge).
    A line that never toggles still yields its event type, written as a zero-row table, since the type
    existed in the recording and nothing fired. ``session_start_time`` is read from the file's
    ``Created`` attribute when present.

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
            detection_configuration=detection_configuration,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "doric_events"
        # available_signals: signal_source_id (the DigitalIO dataset key, e.g. "Camera1") -> its
        # descriptor. Membership of a DigitalIO group makes every discovered signal kind "line", settled
        # structurally with no data read, which is what lets the validator reject a cut on it.
        self._available_signals = self._discover_signals(self.source_data["file_path"])
        if detection_configuration is None:
            # The default, used only when the caller passes none: read every discovered line as a
            # "high_period", the lossless durative reading (onset at the rising edge, duration to the
            # falling edge, for an active-high line).
            detection_configuration = {
                signal_source_id: [{"detection": "high_period"}] for signal_source_id in self._available_signals
            }
        # One construction-time check, on the default as well as on a caller-supplied configuration: the
        # default is machine-built but its inputs are not, so it too can resolve two event types to the
        # same identifier. Validation covers structure and identifier resolution (rules 4 and 5) alike.
        validate_detection_configuration(detection_configuration, self._available_signals)
        self._detection_configuration = detection_configuration

    @staticmethod
    def _discover_signals(file_path) -> dict[str, dict]:
        """Return ``signal_source_id -> {kind, data_path, time_path}`` for every digital line in the file.

        Walks ``DataAcquisition`` for ``DigitalIO`` groups (a group whose leaf name is ``DigitalIO``
        holding a ``Time`` dataset) and treats each non-Time 1-D dataset as a digital line. The line's
        dataset key is its ``signal_source_id`` (identity-in-header, e.g. ``Camera1``, ``DigitalCh1``).
        Membership of a ``DigitalIO`` group is what makes every discovered signal a digital line, and it
        is settled structurally with no data read.
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
        # so only the name is seeded here. Derived from the configuration rather than from the events or
        # the plan, so metadata costs no data read and does not depend on a plan existing: whether a line
        # happened to fire does not change which event types the configuration asked for.
        for event_type_source_id in _get_event_type_source_ids(self._detection_configuration):
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = {
                "event_name": event_type_source_id
            }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation by edge-detecting each selected line, cached.

        Each entry of the resolved plan becomes one :class:`_EventsData` keyed by its
        ``event_type_source_id``: its signal's trace is read per the spec's ``detection`` into onset
        frames and, for a durative reading, offset frames. Both are then indexed into that signal's
        ``Time`` dataset, so a duration is the elapsed clock time between the two edges rather than a
        frame count times an assumed sampling period. An event type with no event (a constant line, or
        one that never opens) keeps its entry with empty timestamps, which the writer renders as a
        zero-row table.

        A ``.doric`` line is already a ``0``/``1`` signal, so no conditioning runs here and the reading is
        applied to the signal's own values.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        import h5py

        # Built here rather than held on the interface: the configuration is the source of truth, and the
        # plan is pure and cheap to rebuild. Grouped by signal, so a signal is read once however many
        # event types it yields.
        detection_plan = resolve_detection_plan(self._detection_configuration)

        events_data_dict = {}
        with h5py.File(self.source_data["file_path"], "r") as f:
            for signal_source_id, event_types in detection_plan.items():
                paths = self._available_signals[signal_source_id]
                data = np.asarray(f[paths["data_path"]][:], dtype="float64")
                time = np.asarray(f[paths["time_path"]][:], dtype="float64")
                for event_type_source_id, spec in event_types:
                    # A .doric digital line is already a 0/1 signal, so no conditioning applies and the
                    # reading is taken from the signal's own values, with no cut anywhere.
                    conditioned = _condition_signal(data, spec.get("signal_conditioning"))
                    onset_frames, offset_frames, values = _detect_events(conditioned, spec["detection"])
                    onsets, durations = _frames_to_seconds(onset_frames, offset_frames, time)
                    events_data_dict[event_type_source_id] = _EventsData(
                        event_type_source_id=event_type_source_id,
                        timestamps=onsets,
                        durations=durations,
                        payload={} if values is None else {"value": values},
                    )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
