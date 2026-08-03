"""Interface for discrete events derived from the SpikeGLX NIDQ board's sampled signals."""

import warnings

import numpy as np

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
from ....utils import DeepDict

# A NIDQ channel is addressed by the board's own name, ``XA0``, which is what ``~snsChanMap``, the
# SpikeGLX user interface and CatGT all show. neo builds its channel ids by prefixing the stream
# (``nidq#XA0``) so that ids stay unique across a run's imec and NI streams, and because this interface
# handed those ids straight back for its first few releases, that spelling reached user code. It is
# still accepted wherever a channel is named, behind this warning. It lives here rather than in
# spikeglxnidqinterface.py only because that module imports this one.
_NEO_ADDRESSING_DEPRECATION = (
    "Addressing a NIDQ channel by neo's stream-qualified id ('nidq#XA0') is deprecated and will be "
    "removed on or after August 2027. Use the board's own name ('XA0'), which is what the SpikeGLX "
    "header, CatGT and get_channel_names() all show. The stream prefix distinguishes nothing here, "
    "since this interface only ever reads the nidq stream."
)


class _SpikeGLXNIDQEventsInterface(BaseEventsInterface):
    """Derive discrete events from the NIDQ board's sampled signals. Private, driven by its parent.

    Constructed by :class:`.SpikeGLXNIDQInterface` rather than by a user, which is why it is private:
    NIDQ analog and digital signals come off one board and one clock, so the board gets one public
    interface and this class is the part of it that speaks events. It exists as a class rather than as
    methods on the parent because the whole ``EventsTable`` writer lives on
    :class:`~neuroconv.datainterfaces.events.baseeventsinterface.BaseEventsInterface`, and the parent is
    a plain ``BaseDataInterface`` whose ``add_to_nwbfile`` already carries the analog iterator options.

    **The addressable signal is the word, not the line.** SpikeGLX saves its sixteen digital lines packed
    into one integer channel per word (``~snsChanMap`` lists a single ``XD0`` entry, and ``niXDChans1``
    says which bit positions that word carries), and its own extraction tool addresses a line as word
    plus bit (``CatGT -XD=js,ip,word,bit``). So ``XD0`` is the ``signal_source_id`` and a line is reached
    with ``signal_conditioning={"bits": [n]}``. This is the only format in the codebase that needs that
    cut; every other one names its lines in the header.

    Analog channels are inventoried alongside the digital words, so ``XA``/``MA`` can be cut into events
    with ``binarize`` (a photodiode or a lever trace cut into a discrete signal). They are never derived
    by default, since there is no defensible cut point to invent.
    """

    display_name = "SpikeGLX NIDQ Events"
    keywords = ("events", "Neuropixels", "nidq", "NIDQ", "SpikeGLX")
    associated_suffixes = (".nidq", ".meta", ".bin")
    info = "Interface for discrete events derived from the SpikeGLX NIDQ board's signals."

    def __init__(
        self,
        *,
        folder_path,
        detection_configuration: dict | None = None,
        metadata_key: str = "spikeglx_nidq",
        verbose: bool = False,
    ):
        """Initialize the events half of a NIDQ conversion.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing the ``.nidq.bin`` file.
        detection_configuration : dict, optional
            Which signals to read and how, keyed by ``signal_source_id`` (the board's own handle, e.g.
            ``"XD0"`` for a digital word or ``"XA1"`` for an analog channel). Each value is a **list** of
            detection specs, one per event type derived from that signal. A digital word's spec must
            carry ``signal_conditioning={"bits": [n]}`` naming the one line to read; an analog channel's
            must carry ``signal_conditioning={"binarize": c}`` plus an ``event_name``. A spec's
            ``detection`` is one of ``"rising"`` / ``"falling"`` (a point event at each edge),
            ``"high_period"`` / ``"low_period"`` (a durative event), or ``"value_change"``, and it is
            required. If None (default), every line of every digital word is read as a ``high_period``
            and the analog channels are skipped.
        metadata_key : str, default: "spikeglx_nidq"
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata.
        verbose : bool, default: False
            Whether to output verbose text.
        """
        from spikeinterface.extractors.extractor_classes import (
            SpikeGLXRecordingExtractor,
        )

        super().__init__(folder_path=folder_path, verbose=verbose)
        self.metadata_key = metadata_key
        # Its own reader rather than the parent's, so this stays an ordinary interface: source data is a
        # path, it can be constructed and tested on its own, and nothing in its signature is a live
        # object. The second open is cheap (the bin file is memmapped) and both readers see the same
        # immutable file.
        #
        # The one thing to keep in mind: the parent writes its analog TimeSeries from *its* extractor and
        # this writes events from *this* one, so anything that mutates a reader's clock has to be applied
        # to both. Nothing does today (SpikeGLXNIDQInterface has no alignment API, and stub_test builds a
        # separate stubbed recording the analog path alone sees), but `set_aligned_starting_time` would,
        # and silently shifting one and not the other is the same class of bug this interface just fixed.
        self.recording_extractor = SpikeGLXRecordingExtractor(
            folder_path=folder_path,
            stream_id="nidq",
            all_annotations=True,
        )
        signals_info = self.recording_extractor.neo_reader.signals_info_dict[(0, "nidq")]

        # available_signals: signal_source_id (the board's handle, e.g. "XD0", "XA1") -> its descriptor.
        # The header settles every kind structurally with no data read (niXDChans versus niXAChans), which
        # is what lets the validator reject a cut the signal does not admit.
        self._available_signals = self._get_available_signals(
            recording_extractor=self.recording_extractor,
            digital_line_names=signals_info["digital_channels"],
        )
        if detection_configuration is None:
            detection_configuration = self._get_default_detection_configuration()
        else:
            # The signal_source_id is the board's own handle ("XD0"), matching ~snsChanMap, the SpikeGLX
            # user interface and CatGT, and matching how every other events interface keys on the source's
            # own name. neo's stream-qualified id ("nidq#XD0") is accepted too, as a temporary
            # backwards-compatibility shim: this interface handed those ids back from get_channel_names()
            # and took them in analog_channel_groups for its first few releases, so user code has them.
            # Both now warn and go on or after August 2027, together with this block and the collision
            # check inside it, which exists only because two spellings do.
            normalized = {}
            used_neo_addressing = False
            for signal_source_id, specs in detection_configuration.items():
                handle = str(signal_source_id).split("#")[-1]
                used_neo_addressing |= "#" in str(signal_source_id)
                if handle in normalized:
                    # Both spellings of one signal. Rewriting them into a dict would keep whichever came
                    # last and drop the other in silence, which is exactly the failure this module's
                    # validation exists to remove.
                    raise ValueError(
                        f"detection_configuration names the signal '{handle}' twice, once with neo's "
                        f"stream prefix and once without. Both spellings address the same "
                        "signal, so give it a single entry holding all of its detection specs."
                    )
                normalized[handle] = specs
            if used_neo_addressing:
                warnings.warn(_NEO_ADDRESSING_DEPRECATION, FutureWarning, stacklevel=4)
            detection_configuration = normalized
        # One construction-time check, on the default as well as on a caller-supplied configuration: the
        # default is machine-built but its inputs are not, so it too can resolve two event types to the
        # same identifier. Validation covers structure and identifier resolution alike.
        #
        # `{}` is exempt, and is the one place it means anything. The shared grammar refuses an empty
        # configuration because selecting nothing is normally a mistake, and that rule stays intact:
        # nothing empty is ever handed to it. Here `{}` is not a configuration at all but a suppression
        # sentinel, "keep the analog channels, write no events", which this interface alone needs because
        # a converter builds it for you and dropping it is not an option. It mirrors the released
        # `analog_channel_groups={}`, so the pair keeps meaning the same thing on both sides.
        if detection_configuration:
            _validate_detection_configuration(detection_configuration, self._available_signals)
        self._detection_configuration = detection_configuration

    @staticmethod
    def _get_available_signals(recording_extractor, digital_line_names) -> dict[str, dict]:
        """Return ``signal_source_id -> {kind, channel_id, bits}`` for every NIDQ signal.

        The handle is the board's own name with the reader's stream prefix dropped (``nidq#XD0`` ->
        ``XD0``), which is what ``~snsChanMap`` and the SpikeGLX user interface show. Kind comes from
        the name class: an ``XD`` channel is a packed ``word``, an ``XA``/``MA`` channel is ``analog``.
        Both are settled from the header with no sample read. A word also carries ``bits``, the line
        positions it holds, which is what the zero-configuration default fans out over.

        ``digital_line_names`` are the reader's already-parsed ``niXDChans1`` entries, one per acquired
        line. That field is a general list rather than a range (``"0,2:4,6:7"`` is legal, and the
        SpikeGLX manual's own multi-byte example is ``"0:4,22"``), so parsing it is worth not doing
        twice.

        .. warning::

            ``XD0`` means two different things depending on who is speaking, and both appear here.
            SpikeGLX's ``~snsChanMap`` uses it for the saved *word channel*, which is what
            ``signal_source_id`` keys on. The reader uses the same spelling for its synthesised per-line
            names, where ``XD0`` is *line 0*, which is what ``digital_line_names`` holds and where the
            bit positions come from. On a one-byte recording both exist and the strings collide.
        """
        word_bits = sorted(int(str(name)[2:]) for name in digital_line_names)

        available_signals: dict[str, dict] = {}
        word_channel_ids = []
        for channel_id in recording_extractor.get_channel_ids():
            channel_id = str(channel_id)
            signal_source_id = channel_id.split("#")[-1]
            if signal_source_id.startswith("XD"):
                word_channel_ids.append(channel_id)
                available_signals[signal_source_id] = {
                    "kind": "word",
                    "channel_id": channel_id,
                    "bits": word_bits,
                }
            elif signal_source_id.startswith("XA") or signal_source_id.startswith("MA"):
                available_signals[signal_source_id] = {"kind": "analog", "channel_id": channel_id}

        # A line's bit position is its own line number, so a rig whose highest line is 16 or above needs
        # three or four bytes, which SpikeGLX then stores as *two* 16-bit stream columns. The bit
        # positions would have to be split across those columns (line 17 is bit 1 of the second one), and
        # this reads a single column and takes bit n for line n. Refuse rather than silently report the
        # high lines as the low ones. Lines 8-15 are fine: two bytes still pack into one column.
        #
        # No such recording is known to exist. The board most rigs use, the PXIe-6341, has only 8 clocked
        # ("waveform") digital lines and rejects a wider configuration outright, which is
        # billkarsh/SpikeGLX issue #40; every .nidq.meta anyone has is niXDChans1=0:7. A 6363 or a 6535
        # could produce one, so this fails loudly on the first such file instead of guessing at a layout
        # that has never been seen.
        if len(word_channel_ids) > 1 or (word_bits and max(word_bits) > 15):
            raise NotImplementedError(
                f"This NIDQ recording stores its digital lines in more than one 16-bit word "
                f"(lines {word_bits}, word channels {word_channel_ids}), which "
                "is not supported yet: a line's bit position is its own line number, so lines 16 and "
                "above live in a second word. Please open an issue with this file's .nidq.meta, since no "
                "such recording was available when this was written."
            )
        return available_signals

    def _get_default_detection_configuration(self) -> dict:
        """Every line of every digital word as its own ``high_period`` event type; analog skipped.

        Lossless for independent lines (the common case: each carries its own TTL), and every transition
        is preserved, so a code is still reconstructable from the per-bit tables afterwards. It is the
        wrong reading for a *trial-code* word, where the bits are one value rather than eight signals,
        and nothing in the file distinguishes the two; a coded word therefore needs an explicit spec and
        is deliberately not reachable from here.

        Analog channels are skipped rather than guessed: a continuous trace has no defensible cut, and
        inventing one would fabricate events.
        """
        detection_configuration = {}
        for signal_source_id, descriptor in self._available_signals.items():
            if descriptor["kind"] != "word":
                continue
            specs = [{"signal_conditioning": {"bits": [bit]}, "detection": "high_period"} for bit in descriptor["bits"]]
            if specs:
                detection_configuration[signal_source_id] = specs
        return detection_configuration

    def get_metadata(self) -> DeepDict:
        """Seed one ``event_types`` entry per event type the configuration resolves to.

        Derived from the configuration rather than from the events, so metadata costs no trace read:
        whether a line happened to fire does not change which event types the configuration asked for.
        The NIDQ board ships no meaning for a line, so only the name is seeded.
        """
        metadata = super().get_metadata()
        for event_type_source_id in _get_event_type_source_ids(self._detection_configuration):
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = {
                "event_name": event_type_source_id
            }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation by carving and edge-detecting each signal, cached.

        Each entry of the resolved plan becomes one :class:`_EventsData`: the signal's trace is
        conditioned per the spec (a bit carved out of the word, or an analog trace cut at a level),
        read into onset frames and, for a durative reading, offset frames, and both are then converted
        through the recording's own clock.

        The clock is passed as a **callable** rather than as an array. NIDQ derives its times from a
        sampling rate instead of storing them, so materialising the clock would build one float per
        sample (three hours at 30 kHz is 324 million entries) to read the handful of frames the events
        landed on. ``sample_index_to_time`` reads only those frames, and it carries the stream's own
        start time, so the events stay aligned with the analog series written from the same extractor.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        # Built here rather than held on the interface: the configuration is the source of truth, and the
        # plan is pure and cheap to rebuild. Grouped by signal, so a word is read once however many lines
        # are carved out of it.
        detection_plan = _resolve_detection_plan(self._detection_configuration)

        events_data_dict = {}
        for signal_source_id, detection_specs in detection_plan.items():
            channel_id = self._available_signals[signal_source_id]["channel_id"]
            # Unscaled (the extractor's default). Required for a word, whose value *is* the bit pattern:
            # SpikeGLX declares one input range for the device, so the reader hands digital channels the
            # same volts-per-count gain as the analog ones and applying it would destroy what `bits`
            # carves. Analog channels are read the same way, so a `binarize` cut point is expressed in
            # the signal's stored values, matching every other interface using this grammar.
            trace = np.ravel(self.recording_extractor.get_traces(channel_ids=[channel_id]))
            for event_type_source_id, spec in detection_specs:
                conditioned = _condition_signal(trace, spec["signal_conditioning"])
                onset_frames, offset_frames = _detect_events(conditioned, spec["detection"])
                onsets, durations = _frames_to_seconds(
                    onset_frames, offset_frames, self.recording_extractor.sample_index_to_time
                )
                events_data_dict[event_type_source_id] = _EventsData(
                    event_type_source_id=event_type_source_id,
                    timestamps=onsets,
                    durations=durations,
                )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
