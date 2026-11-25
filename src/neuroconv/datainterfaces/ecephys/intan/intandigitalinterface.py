import warnings
from functools import partial
from pathlib import Path

from pydantic import FilePath, validate_call

from ._utils import _warn_if_split_siblings_detected
from ...events.baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools.events import _resolve_event_types, _validate_detection_configuration
from ....tools.signal_processing import (
    _ON_CHANGE_READINGS,
    _TIMESTAMP_ESTIMATES,
    _detect_occurrences,
)

# The two digital words an Intan controller records. A file carries either, both, or neither, and the
# lines of both share the amplifier's sampling rate and timeline, so one interface covers whichever are
# present.
_DIGITAL_STREAM_NAMES = {
    "USB board digital input channel": "digital_inputs",
    "USB board digital output channel": "digital_outputs",
}
_PORT_STREAM_NAMES = {port: stream_name for stream_name, port in _DIGITAL_STREAM_NAMES.items()}


class IntanDigitalInterface(BaseEventsInterface):
    """Data interface for converting Intan digital TTL lines to discrete events.

    The Intan controller packs its 16 digital input lines (and its 16 digital output lines) into one
    16-bit word per sample, and the header names every line it recorded. This interface reads lines of
    those words and edge-detects them into events, written as ``pynwb.event.EventsTable`` objects in
    ``nwbfile.events`` (via :class:`.BaseEventsInterface`).

    **Each word is a port, and a line is addressed by its position on the port**, counted from 0. The
    sources are ``"digital_inputs"`` and ``"digital_outputs"`` whichever way the file was saved (inside
    the ``.rhd``/``.rhs`` file, as one word file, or as one file per line). The header's line names are not
    the address, because the naming scheme changed across Intan software versions: line 0 is ``DIN-00``
    in an older file and ``DIGITAL-IN-01`` in a newer one.

    By default every line the header exposes becomes its own event type, named after the line in the
    header and read as a **high pulse**: the event's timestamp is the rising (0->1) edge and its duration
    is the span to the falling (1->0) edge. A line that was recorded but never toggles is still written, as
    an empty (zero-row) table, faithful to the source (the line existed, nothing fired). The high-pulse
    reading assumes an **active-high** line (idles low, pulses high); for an active-low device (idles
    high, pulses low), configure ``{"onset": "falling", "end": "rising"}``.

    Recordings saved with Intan RHX's "new save file every N minutes" option are supported via
    ``saved_files_are_split``, which concatenates the rotated siblings in ``file_path.parent`` in
    filename order before edge detection, so a pulse spanning a chunk boundary reads as one pulse.

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
        event_extraction_configuration: dict[str, dict] | None = None,
        detection_configuration: dict[str, list[dict]] | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
        saved_files_are_split: bool = False,
    ):
        """Initialize the IntanDigitalInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to either a ``.rhd`` or a ``.rhs`` file. When ``saved_files_are_split=True`` this is
            any single file in the session folder; its parent directory is scanned for siblings.
        event_extraction_configuration : dict, optional
            Entries keyed by the event type identifier. Each entry names a port in ``source``
            (``"digital_inputs"`` or ``"digital_outputs"``), picks one of its lines in
            ``detection={"lines": [line], ...}`` and says which changes are events with ``on_change``.
            A line is counted from 0 by its position on the port, so ``DIGITAL-IN-01`` and ``DIN-00`` are
            both line 0. ``get_available_event_sources`` lists the ports in a file.

            If None (default), every recorded line becomes an event type named after the line in the
            header (``DIGITAL-IN-01``), read from each rising change to the next falling change, so each
            event is one high pulse with its duration. This assumes an active-high line.
        detection_configuration : dict, optional
            Deprecated and will be removed in v0.13.0. Use ``event_extraction_configuration`` instead.
            The released shape, keyed by the line's header name, is translated to an
            ``event_extraction_configuration`` with the same event type identifiers.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata. If
            None (default), ``"intan_digital"`` is used.
        saved_files_are_split : bool, default: False
            Set to True when the recording was saved using Intan RHX's "new save file every N
            minutes" option, producing several rotated ``.rhd``/``.rhs`` files in one session
            folder. All sibling files in ``file_path.parent`` are concatenated in filename order.
        verbose : bool, default: False
            Whether to print status messages.
        """
        file_path = str(file_path)
        if not saved_files_are_split:
            _warn_if_split_siblings_detected(Path(file_path), interface_name="IntanDigitalInterface")
        # One extractor per digital word present, held because reading a line's trace goes through the
        # word that carries it. Building them reads the header only, so construction stays cheap.
        self._recording_extractors = self._read_digital_streams(file_path, saved_files_are_split=saved_files_are_split)
        # port -> {line position: channel id}. The header lists only the lines enabled at acquisition, and
        # gives each its position on the port as ``native_order``.
        self._port_lines = {
            _DIGITAL_STREAM_NAMES[stream_name]: {
                int(line): str(channel_id)
                for line, channel_id in zip(recording.get_property("native_order"), recording.get_channel_ids())
            }
            for stream_name, recording in self._recording_extractors.items()
        }
        if not any(self._port_lines.values()):
            # Ordinary data rather than a defect: the header names only the lines that were enabled at
            # acquisition, so a session recorded with the digital inputs and outputs off carries no
            # digital word at all.
            raise ValueError(
                f"'{file_path}' carries no digital channels. Intan's header declares only the lines that "
                "were enabled at acquisition, so a session recorded with its digital inputs and outputs "
                "disabled has none and there is nothing for this interface to convert."
            )

        if detection_configuration is not None:
            if event_extraction_configuration is not None:
                raise ValueError(
                    "Pass 'event_extraction_configuration' or the deprecated 'detection_configuration', not both."
                )
            warnings.warn(
                "'detection_configuration' is deprecated and will be removed in v0.13.0. "
                "Use 'event_extraction_configuration' instead.",
                FutureWarning,
                stacklevel=2,
            )
            event_extraction_configuration = _translate_detection_configuration(
                detection_configuration, self._port_lines
            )
        if event_extraction_configuration is None:
            event_extraction_configuration = {
                channel_id: {
                    "source": port,
                    "detection": {"lines": [line], "on_change": {"onset": "rising", "end": "falling"}},
                }
                for port, lines in self._port_lines.items()
                for line, channel_id in lines.items()
            }

        available_sources = {port: {"supported_operations": ["detection"]} for port in self._port_lines}
        configuration = self._resolve_event_sources(event_extraction_configuration, available_sources)
        for entry_name, entry in configuration.items():
            port = entry["source"]
            line = entry["detection"].get("lines", [0])[0]
            if line not in self._port_lines[port]:
                raise ValueError(
                    f"Event extraction entry {entry_name!r} reads line {line} of {port!r}, which the file did "
                    f"not record. Recorded lines: {sorted(self._port_lines[port])}."
                )
        self._event_extraction_configuration = configuration

        super().__init__(
            file_path=file_path,
            event_extraction_configuration=event_extraction_configuration,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "intan_digital"

    @classmethod
    def get_available_event_sources(cls, file_path: FilePath) -> list[str]:
        """List the digital ports present in the header, independent of the save layout."""
        from spikeinterface.extractors import get_neo_streams

        stream_names, _ = get_neo_streams("intan", file_path=file_path)
        return [port for stream, port in _DIGITAL_STREAM_NAMES.items() if stream in stream_names]

    def get_event_type_source_ids(self) -> list[str]:
        """The event types the configuration names, read from nothing."""
        return list(self._event_extraction_configuration)

    @staticmethod
    def _read_digital_streams(file_path, saved_files_are_split: bool = False) -> dict:
        """Return ``stream_name -> recording`` for whichever digital words the file carries.

        A file may hold the input word, the output word, both, or neither, so the streams present are
        read from the header rather than named by the caller.
        """
        from spikeinterface.extractors import (
            get_neo_streams,
            read_intan,
            read_split_intan_files,
        )

        stream_names, _ = get_neo_streams("intan", file_path=file_path)

        def read_stream(stream_name):
            if saved_files_are_split:
                # One continuous segment across the rotated files, so edge detection sees a pulse
                # that starts in one chunk and ends in the next as the single pulse it is.
                return read_split_intan_files(
                    folder_path=Path(file_path).parent, stream_name=stream_name, all_annotations=True
                )
            return read_intan(file_path=file_path, stream_name=stream_name, all_annotations=True)

        return {
            stream_name: read_stream(stream_name)
            for stream_name in _DIGITAL_STREAM_NAMES
            if stream_name in stream_names
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
        for event_type_source_id in self.get_event_type_source_ids():
            event_types[event_type_source_id] = {"event_name": event_type_source_id}
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Read the line of each entry, detect its events and emit one :class:`_EventsData`, cached.

        Onset and offset samples are turned into seconds by asking the recording for the time of those
        samples: Intan derives its clock from the sampling rate instead of storing one, so the clock is
        passed as a callable and only the samples the events landed on are ever computed.

        An event type with no event (a line that never toggles) keeps its entry with empty timestamps,
        which the writer renders as a zero-row table.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        events_data_dict = {}
        for event_type_source_id, entry in self._event_extraction_configuration.items():
            port = entry["source"]
            line = entry["detection"].get("lines", [0])[0]
            recording = self._recording_extractors[_PORT_STREAM_NAMES[port]]
            trace = recording.get_traces(channel_ids=[self._port_lines[port][line]])[:, 0]
            # python-neo hands each recorded line over as its own 0/1 channel. Placing it back at its
            # position in the port's word lets the entry address the line as it would in the word itself.
            word = trace.astype("uint16") << line
            onsets, durations = _detect_occurrences(
                entry=entry,
                trace=word,
                timestamps=partial(recording.sample_index_to_time, segment_index=0),
            )
            events_data_dict[event_type_source_id] = _EventsData(
                event_type_source_id=event_type_source_id,
                timestamps=onsets,
                durations=durations,
            )

        self._events_data_dict = events_data_dict
        return self._events_data_dict


def _translate_detection_configuration(detection_configuration: dict, port_lines: dict) -> dict:
    """Translate the released ``detection_configuration`` into an ``event_extraction_configuration``.

    The released shape is keyed by the line's header name, with a list of specs per line. Each spec becomes
    one entry on the line's port, under the identifier the released shape gave it, so the event types,
    their metadata keys and their tables stay as they were.
    """
    line_addresses = {
        channel_id: (port, line) for port, lines in port_lines.items() for line, channel_id in lines.items()
    }
    _validate_detection_configuration(
        detection_configuration, {channel_id: {"kind": "line"} for channel_id in line_addresses}
    )
    on_change_by_reading = {reading: on_change for on_change, reading in _ON_CHANGE_READINGS.items()}
    estimate_by_convention = {convention: estimate for estimate, convention in _TIMESTAMP_ESTIMATES.items()}

    event_extraction_configuration = {}
    for event_type_source_id, channel_id, spec in _resolve_event_types(detection_configuration):
        port, line = line_addresses[channel_id]
        onset, end = on_change_by_reading[spec["detection"]]
        on_change = {"onset": onset} if end is None else {"onset": onset, "end": end}
        detection = {"lines": [line], "on_change": on_change}
        if "event_time_convention" in spec:
            detection["timestamp_estimate"] = estimate_by_convention[spec["event_time_convention"]]
        event_extraction_configuration[event_type_source_id] = {"source": port, "detection": detection}
    return event_extraction_configuration
