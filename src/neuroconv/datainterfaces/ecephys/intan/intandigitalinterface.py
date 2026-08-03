from functools import partial

from pydantic import FilePath, validate_call

from ...events.baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools.events import (
    _get_event_type_source_ids,
    _resolve_detection_plan,
    _validate_detection_configuration,
)
from ....tools.signal_processing import (
    _condition_signal,
    _detect_events,
    _frames_to_seconds,
)

# The two digital words an Intan controller records. A file carries either, both, or neither, and the
# lines of both share the amplifier's sampling rate and timeline, so one interface covers whichever are
# present.
_DIGITAL_STREAM_NAMES = ("USB board digital input channel", "USB board digital output channel")


class IntanDigitalInterface(BaseEventsInterface):
    """Data interface for converting Intan digital TTL lines to discrete events.

    The Intan controller packs its 16 digital input lines (and its 16 digital output lines) into one
    16-bit word per sample, and the header names every line it recorded. This interface reads each named
    line and edge-detects it into events, written as ``pynwb.event.EventsTable`` objects in
    ``nwbfile.events`` (via :class:`.BaseEventsInterface`).

    **Lines are addressed by the header's own name**, the ``native_channel_name`` the Intan software
    wrote (``DIGITAL-IN-01``, ``DIN-00``, ``DIGITAL-OUT-05``), which is what the acquisition software
    shows. That name is a genuine source handle rather than a rendering of the bit position, and it is
    not derivable from one: the naming scheme changed across Intan software versions, so bit 0 is
    ``DIN-00`` in an older file and ``DIGITAL-IN-01`` in a newer one. Because every line is named
    individually, the name alone does the addressing, and one interface instance covers both digital
    words without being told which to read.

    By default every line the header exposes becomes its own event type, read as a **high pulse**: the
    event's timestamp is the rising (0->1) edge and its duration is the span to the falling (1->0) edge
    (the ``high_period`` reading). A line that was recorded but never toggles is still written, as an
    empty (zero-row) table, faithful to the source (the line existed, nothing fired). The high-pulse
    reading assumes an **active-high** line (idles low, pulses high); an active-low device (idles high,
    pulses low) wants ``"low_period"``.

    The digital line as a continuous waveform is not stored here; that is :class:`.IntanAnalogInterface`'s
    job. This is a purely additive, opt-in product that derives discrete events from the line.
    """

    display_name = "Intan Digital"
    keywords = ("intan", "digital", "TTL", "events", "rhd", "rhs")
    associated_suffixes = (".rhd", ".rhs")
    info = "Interface for converting Intan digital TTL channels to events."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        detection_configuration: dict[str, list[dict]] | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the IntanDigitalInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to either a ``.rhd`` or a ``.rhs`` file. Time-split (rotated) recordings are not
            supported by this interface; pass a single recording.
        detection_configuration : dict, optional
            Which digital lines to read and how, keyed by the line's ``signal_source_id`` (the header's
            name for it, e.g. ``{"DIGITAL-IN-01": [{"signal_conditioning": {"binarize": "midpoint"},
            "detection": "rising"}]}``). Each value is a **list**
            of detection specs, one per event type derived from that line, since a line can yield more
            than one. A spec's ``detection`` is one of ``"rising"`` / ``"falling"`` (a point event at each
            edge) or ``"high_period"`` / ``"low_period"`` (a durative event, onset at one edge and
            duration to the next opposite edge), and it is required. ``signal_conditioning`` is required
            too and says how the signal becomes a line: an Intan digital line is already ``0``/``1``, so
            it takes ``{"binarize": "midpoint"}``, whose cut falls strictly between the two levels
            whatever they are. An optional ``event_name`` replaces the derived identifier and pins it
            against later edits.

            If None (default), every line the header exposes is read as a ``"high_period"``, lossless for
            an active-high line; use ``"low_period"`` for an active-low one. When given, only the named
            lines are read.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata. If
            None (default), ``"intan_digital"`` is used.
        verbose : bool, default: False
            Whether to print status messages.
        """
        file_path = str(file_path)
        # One extractor per digital word present, held because reading a line's trace goes through the
        # word that carries it. Building them reads the header only, so construction stays cheap.
        self._recording_extractors = self._read_digital_streams(file_path)
        # available_signals: signal_source_id (the header's channel name) -> its descriptor. Every
        # discovered signal is a "line" because the word is already demultiplexed into strictly 0/1
        # per-line traces, which is settled structurally and is what lets the validator reject both a
        # 'bits' carve: there is no packed word left to carve.
        self._available_signals = self._get_available_signals(self._recording_extractors)
        if not self._available_signals:
            # Ordinary data rather than a defect: the header names only the lines that were enabled at
            # acquisition, so a session recorded with the digital inputs and outputs off carries no
            # digital word at all. Said here because the default configuration derived below would
            # otherwise come out empty and be refused by the validator's empty-configuration guard,
            # which tells the caller to pass the None they just passed.
            raise ValueError(
                f"'{file_path}' carries no digital channels. Intan's header declares only the lines that "
                "were enabled at acquisition, so a session recorded with its digital inputs and outputs "
                "disabled has none and there is nothing for this interface to convert."
            )
        if detection_configuration is None:
            # The default, used only when the caller passes none: read every line as a "high_period", the
            # lossless durative reading (onset at the rising edge, duration to the falling edge).
            detection_configuration = {
                signal_source_id: [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "high_period"}]
                for signal_source_id in self._available_signals
            }
        # One construction-time check, on the default as well as on a caller-supplied configuration: the
        # default is machine-built but its inputs are not, so it too can resolve two event types to the
        # same identifier. Validation covers structure and identifier resolution (rules 4 and 5) alike.
        _validate_detection_configuration(detection_configuration, self._available_signals)
        self._detection_configuration = detection_configuration

        super().__init__(
            file_path=file_path,
            detection_configuration=detection_configuration,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "intan_digital"

    @staticmethod
    def _read_digital_streams(file_path) -> dict:
        """Return ``stream_name -> recording`` for whichever digital words the file carries.

        A file may hold the input word, the output word, both, or neither, so the streams present are
        read from the header rather than named by the caller.
        """
        from spikeinterface.extractors import get_neo_streams, read_intan

        stream_names, _ = get_neo_streams("intan", file_path=file_path)
        return {
            stream_name: read_intan(file_path=file_path, stream_name=stream_name, all_annotations=True)
            for stream_name in _DIGITAL_STREAM_NAMES
            if stream_name in stream_names
        }

    @staticmethod
    def _get_available_signals(recording_extractors: dict) -> dict[str, dict]:
        """Return ``signal_source_id -> {kind, stream_name, channel_id}`` for every digital line.

        The validator's inventory: its keys are the names a ``detection_configuration`` may use, and the
        rest of each descriptor is this interface's own addressing, which is why it is private.
        """
        return {
            str(channel_id): {"kind": "line", "stream_name": stream_name, "channel_id": channel_id}
            for stream_name, recording in recording_extractors.items()
            for channel_id in recording.get_channel_ids()
        }

    def get_metadata(self) -> dict:
        """Seed one ``event_types`` entry per event type the configuration resolves to.

        Header-only by design: the entries come from the configuration rather than from the events, so
        which event types are listed is decided by what was asked for rather than by which lines happened
        to fire, and constructing or inspecting metadata never loads sample data (the traces are read only
        in :meth:`add_to_nwbfile`). An Intan file ships no prose for a digital line and a line carries no
        value column, so each entry is just an ``event_name``.
        """
        metadata = super().get_metadata()
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        for event_type_source_id in _get_event_type_source_ids(self._detection_configuration):
            event_types[event_type_source_id] = {"event_name": event_type_source_id}
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Read each selected line, edge-detect it per its spec, and emit one :class:`_EventsData`, cached.

        Each line is read once however many event types it yields. Onset and offset **frames** are turned
        into seconds by asking the recording for the time of those frames, which is where Intan differs
        from the other signal-encoded sources: it derives its clock from the sampling rate instead of
        storing one, so the clock is passed as a callable and only the frames the events landed on are
        ever computed. Materialising a whole recording's timestamps to read a handful of edges would cost
        324 million values for three hours at 30 kHz.

        An event type with no event (a line that never toggles) keeps its entry with empty timestamps,
        which the writer renders as a zero-row table.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        # Built here rather than held on the interface: the configuration is the source of truth, and the
        # plan is pure and cheap to rebuild. Grouped by signal, so a line is read once however many event
        # types it yields.
        detection_plan = _resolve_detection_plan(self._detection_configuration)

        events_data_dict = {}
        for signal_source_id, detection_specs in detection_plan.items():
            descriptor = self._available_signals[signal_source_id]
            recording = self._recording_extractors[descriptor["stream_name"]]
            # (n_samples, 1) from a single-channel selection; the reading works on the line itself.
            trace = recording.get_traces(channel_ids=[descriptor["channel_id"]])[:, 0]
            read_clock = partial(recording.sample_index_to_time, segment_index=0)
            for event_type_source_id, spec in detection_specs:
                # An Intan digital line arrives already demultiplexed into a 0/1 trace, so no conditioning
                # applies and the reading is taken from the line's own values, with no cut anywhere.
                conditioned = _condition_signal(trace, spec["signal_conditioning"])
                onset_frames, offset_frames = _detect_events(conditioned, spec["detection"])
                onsets, durations = _frames_to_seconds(onset_frames, offset_frames, read_clock)
                events_data_dict[event_type_source_id] = _EventsData(
                    event_type_source_id=event_type_source_id,
                    timestamps=onsets,
                    durations=durations,
                )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
