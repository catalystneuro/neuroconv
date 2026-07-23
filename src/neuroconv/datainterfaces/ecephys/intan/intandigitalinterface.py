from typing import Literal

from pydantic import FilePath, validate_call

from ...events.baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools.signal_processing import discretize_trace


class IntanDigitalInterface(BaseEventsInterface):
    """Data interface for converting Intan digital TTL channels to discrete events.

    The Intan controller packs its 16 digital input (or output) lines into a single 16-bit word per
    sample; bit *i* of that word is digital line *i*. This interface carves individual lines out of
    that word and edge-detects each one into events, written as ``pynwb.event.EventsTable`` objects in
    ``nwbfile.events`` (via :class:`.BaseEventsInterface`).

    By default every **enabled** line the header exposes becomes its own event type, stored as a
    **high pulse**: the event's timestamp is the rising (0->1) edge and its duration is the span to the
    falling (1->0) edge (the ``high_period`` reading). A line that was recorded but never toggles is
    still written, as an empty (zero-row) table, faithful to the source (the line existed, nothing
    fired). The high-pulse reading assumes an **active-high** line (idles low, pulses high); an
    active-low device (idles high, pulses low) should set ``detect: "low_period"`` on an explicit
    ``event_specs`` entry.

    The digital line as a continuous waveform is not stored here; that is
    :class:`.IntanAnalogInterface`'s job. This is a purely additive, opt-in product that derives
    discrete events from the line.

    Selection and interpretation are set by ``event_specs`` (see ``__init__``), which is keyed by the
    format's **bit positions**, not by the reader's demultiplexed channel names, so a saved spec does
    not depend on the backend.
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
        metadata_key: str | None = None,
        stream_name: Literal["USB board digital input channel", "USB board digital output channel"],
        event_specs: dict | None = None,
        verbose: bool = False,
    ):
        """Initialize the IntanDigitalInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to either a ``.rhd`` or a ``.rhs`` file. Time-split (rotated) recordings are not
            supported by this interface; pass a single recording.
        stream_name : str
            The digital stream to read, one of ``"USB board digital input channel"`` or
            ``"USB board digital output channel"``. It selects the digital word the ``bits`` are carved
            from.
        event_specs : dict, optional
            One spec per event, keyed by a field name, each an entry of the form
            ``{"bits": [i], "detect": ...}``:

            - ``bits`` : a **one-element** list holding the bit position of the line in the digital word.
              A list of length > 1 (a coded word) is not supported yet and raises ``ValueError``.
            - ``detect`` : how the line's transitions become events, one of ``"rising"`` (a point event
              at each 0->1), ``"falling"`` (a point event at each 1->0), ``"high_period"`` (a durative
              event, onset at 0->1 and duration to the next 1->0), or ``"low_period"`` (a durative event,
              onset at 1->0 and duration to the next 0->1, for an active-low line). Defaults to
              ``"high_period"``, which is lossless.

            If None (default), every enabled digital line in the word is derived as its own
            ``"high_period"`` event (a high pulse: onset at the 0->1 rise, duration to the 1->0 fall),
            which assumes active-high lines; set ``detect: "low_period"`` for an active-low device. A
            line that never toggles is still written, as an empty (zero-row) table, so the recorded set
            of lines is preserved. An empty dict ``{}`` raises ``ValueError`` (to skip digital events
            entirely, do not construct this interface, or exclude the stream in the converter). A field
            naming a bit position absent from the word raises ``ValueError``.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata. If
            None (default), ``"intan_digital"`` is used.
        verbose : bool, default: False
            Whether to print status messages.
        """
        from spikeinterface.extractors import read_intan

        file_path = str(file_path)
        self.recording_extractor = read_intan(
            file_path=file_path,
            stream_name=stream_name,
            all_annotations=True,
        )

        # Map each bit position to its demultiplexed channel id. neo already splits the packed word into
        # per-line channels; native_channel_order[channel_id] is that line's bit position, so this is the
        # "bit -> backend data" seam. Keying the public spec by bit (not by these channel names) keeps
        # the spec independent of the reader.
        native_channel_order = self.recording_extractor.neo_reader.native_channel_order
        # int(...) because native_order is a numpy int16 (neo's header dtype); plain int keys match the
        # user's plain-int ``bits`` and render as ``[0]`` rather than ``[np.int16(0)]`` in the "bit not
        # present" error message (numpy 2.x reprs scalars with the ``np.int16(...)`` prefix).
        self._bit_to_channel = {
            int(native_channel_order[channel_id]): channel_id
            for channel_id in self.recording_extractor.get_channel_ids()
        }

        self._stream_name = stream_name
        self._resolved_fields = self._resolve_event_specs(event_specs)

        super().__init__(
            file_path=file_path,
            stream_name=stream_name,
            event_specs=event_specs,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "intan_digital"

    def _resolve_event_specs(self, event_specs: dict | None) -> dict:
        """Turn ``event_specs`` into resolved fields ``{event_type_source_id: {"bit", "detect", "event_name"}}``.

        Three separate steps: ``None`` produces the code default (:meth:`_default_resolved_fields`); a dict
        is first validated (:meth:`_validate_event_specs`, which raises) and then parsed into the internal
        shape here. Keeping validation in its own method is deliberate: its structural half (``bits`` is a
        non-empty list, ``detect`` is a valid value) is the part a pydantic model or a shared
        ``validate_event_specs`` could take over later, leaving this method to parse and default-synthesize.
        """
        if event_specs is None:
            return self._default_resolved_fields()

        self._validate_event_specs(event_specs)
        # Parse (validated input): pull the single bit out, default detect, name the event after the field.
        return {
            field_source_id: {
                "bit": entry["bits"][0],
                "detect": entry.get("detect", "high_period"),
                "event_name": field_source_id,
            }
            for field_source_id, entry in event_specs.items()
        }

    def _default_resolved_fields(self) -> dict:
        """The code default (no ``event_specs``): one ``high_period`` event per enabled line, source id
        and name the line's native channel name. Not user input, so nothing to validate; every enabled
        line is derived in :meth:`_get_events_data_dict` (a line that never toggles becomes an empty
        table)."""
        return {
            str(channel_id): {
                "bit": bit,
                "detect": "high_period",
                "event_name": str(channel_id),
            }
            for bit, channel_id in self._bit_to_channel.items()
        }

    def _validate_event_specs(self, event_specs: dict) -> None:
        """Raise ``ValueError`` on any invalid entry. Structural checks (``bits`` a non-empty list,
        ``detect`` a valid value) and file-dependent semantic checks (bit present in the word, coded-word
        deferral) are both here; the structural half is what could later move to pydantic."""
        valid_detect = ("rising", "falling", "high_period", "low_period")

        # An empty dict is almost always a mistake (or confusion with None). Unlike NIDQ, whose combined
        # analog+digital interface reads {} as "keep the analog, drop the digital half", a digital-only
        # interface has no other half to keep, so {} would mean "build an interface that does nothing".
        # Raise with guidance instead of that silent no-op.
        if not event_specs:
            raise ValueError(
                "event_specs is empty. Pass None (the default) to derive every enabled line, or name "
                "at least one line, e.g. {'sync': {'bits': [0]}}. To skip digital events entirely, do not "
                "construct this interface (or exclude the stream in the converter)."
            )

        for field_source_id, entry in event_specs.items():
            bits = entry.get("bits")
            if not isinstance(bits, list) or len(bits) == 0:
                raise ValueError(
                    f"event_specs field '{field_source_id}' must set 'bits' to a non-empty list, got {bits!r}."
                )
            if len(bits) > 1:
                raise ValueError(
                    f"event_specs field '{field_source_id}' declares a coded/multi-bit word (bits={bits}). Coded words need a "
                    "strobe line to be read safely and are not supported yet; pass one bit per entry."
                )
            if bits[0] not in self._bit_to_channel:
                raise ValueError(
                    f"event_specs field '{field_source_id}' references bit {bits[0]}, which is not present in stream "
                    f"'{self._stream_name}'. Available bit positions are {sorted(self._bit_to_channel)}."
                )
            detect = entry.get("detect", "high_period")
            if detect not in valid_detect:
                raise ValueError(
                    f"event_specs field '{field_source_id}' has invalid detect '{detect}'. Valid values are {list(valid_detect)}."
                )

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Read each resolved line, edge-detect it per ``detect``, and emit one :class:`_EventsData`.

        Every enabled line the header exposes gets an entry, so the written set is decided by the format
        (which lines were recorded), not by which lines happened to fire: a line that never toggles yields
        an empty :class:`_EventsData` and is written as a zero-row table (truth to the source, the line was
        recorded, nothing fired). This is also the only place the digital traces are read; ``get_metadata``
        stays header-only, so constructing the interface and inspecting metadata never load sample data.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        recording = self.recording_extractor
        fs = recording.get_sampling_frequency()

        events_data_dict = {}
        for event_type_source_id, spec in self._resolved_fields.items():
            channel_id = self._bit_to_channel[spec["bit"]]
            trace = recording.get_traces(channel_ids=[channel_id])  # (n_samples, 1), values 0/1
            # threshold=0.5 because the line is strictly 0/1; discretize_trace returns durations in frames.
            onset_frames, duration_frames = discretize_trace(trace, spec["detect"], threshold=0.5)
            timestamps = recording.sample_index_to_time(onset_frames.astype("int64"), segment_index=0)
            durations = None if duration_frames is None else duration_frames / fs
            events_data_dict[event_type_source_id] = _EventsData(
                event_type_source_id=event_type_source_id,
                timestamps=timestamps,
                durations=durations,
                payload={},  # a single line carries no value column
            )

        self._events_data_dict = events_data_dict
        return self._events_data_dict

    def get_metadata(self) -> dict:
        """Seed one ``event_types`` entry per enabled line, named from ``event_specs`` or the header.

        Header-only by design: it lists every resolved line (the enabled lines of the digital word, or the
        lines the user named) without reading the traces, so which lines are listed is decided by the
        format, not by which lines fired, and constructing or inspecting metadata never loads sample data
        (the traces are read only in :meth:`add_to_nwbfile`). A single line is timestamp-only or durative
        and carries no value column, so each entry is just an ``event_name`` (no ``event_description``, no
        ``columns``), matching how a bare TDT epoc seeds.
        """
        metadata = super().get_metadata()
        event_types = metadata["Events"][self.metadata_key]["event_types"]
        for event_type_source_id, spec in self._resolved_fields.items():
            event_types[event_type_source_id] = {"event_name": spec["event_name"]}
        return metadata
