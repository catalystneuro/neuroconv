"""Interface for discrete events (digital IO) from pyPhotometry ``.ppd`` recordings."""

from datetime import datetime

import numpy as np
from pydantic import FilePath, validate_call

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ...fiber_photometry.pyphotometry._file_reader import read_ppd
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


class PyPhotometryEventsInterface(BaseEventsInterface):
    """Convert discrete events (digital IO) from pyPhotometry ``.ppd`` recordings to NWB.

    A ``.ppd`` file is a single stream of unsigned 16-bit words, each holding fifteen bits of an analog
    sample and one bit of a digital line, and the words cycle through the board's analog inputs. A digital
    line therefore rides in the low bit of the words of the analog input it shares a slot with, and takes
    that input's rate and start time: with two inputs at 130 Hz, ``digital_1`` is sampled at 130 Hz from
    the start of the recording and ``digital_2`` at 130 Hz one tick of the 260 Hz sampling timer later.

    Each line is a *signal*, sampled ``0``/``1`` rather than a list of onsets, and the events derived from
    it are set by ``detection_configuration``: one entry per line holding a list of detection specs, since
    a line can yield more than one event type. Each event type is written as its own
    ``pynwb.event.EventsTable`` into ``nwbfile.events``. By default every line is read as a
    ``high_period`` (each rising edge is an event onset, its duration the span to the next falling edge).
    A line that never toggles still yields its event type, written as a zero-row table, since the type
    existed in the recording and nothing fired. ``session_start_time`` is read from the header's
    ``date_time``.

    Lines are named the way pyPhotometry's own reader names them, ``digital_1`` and ``digital_2``. How
    many a file holds depends on the acquisition mode and on the header: a mode with two analog inputs
    carries both lines, while ``3EX_2EM_pulsed`` states one digital signal in its header, because the
    firmware drives its third LED from the second digital input.

    The fluorescence in the same words is a separate interface,
    :class:`.PyPhotometryFiberPhotometryInterface`, since the two are different neurodata types; put both
    in a converter of your own to write a recording whole.
    """

    keywords = ("events", "pyPhotometry")
    display_name = "pyPhotometry Events"
    info = "Data Interface for converting discrete events (digital IO) from pyPhotometry recordings."
    associated_suffixes = (".ppd",)

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        detection_configuration: dict | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the PyPhotometryEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.ppd`` file.
        detection_configuration : dict, optional
            Which digital lines to read and how, keyed by the line's ``signal_source_id`` (``"digital_1"``
            or ``"digital_2"``, e.g. ``{"digital_1": [{"signal_conditioning": {"binarize": "midpoint"},
            "detection": "high_period"}]}``). Each value is a **list** of detection specs, one per event
            type derived from that line, since a line can yield more than one. A spec's ``detection`` is
            one of ``"rising"`` / ``"falling"`` (a point event at each edge) or ``"high_period"`` /
            ``"low_period"`` (a durative event, onset at one edge and duration to the next opposite edge),
            and it is required. ``signal_conditioning`` is required too and says how the signal becomes a
            line: the reader has already pulled the bit out of the word, so a ``.ppd`` line arrives
            ``0``/``1`` and takes ``{"binarize": "midpoint"}``, whose cut falls strictly between the two
            levels whatever they are. An optional ``event_name`` replaces the derived identifier and pins
            it against later edits. If None (default), every digital line the file carries is read as a
            ``high_period``, lossless for an active-high line; use ``"low_period"`` for an active-low one.
            When given, only the named lines are read.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata.
            If None (default), ``"pyphotometry_events"`` is used.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            file_path=file_path,
            detection_configuration=detection_configuration,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "pyphotometry_events"
        # Read once and kept, the way the fiber photometry interface holds it: a photometry session is
        # small enough to hold, and separating the words into signals is what tells us which lines exist.
        self._recording = read_ppd(self.source_data["file_path"])
        # available_signals: signal_source_id ("digital_1") -> its descriptor. Every signal a .ppd carries
        # here is a digital line, one bit wide by construction, and kind "line" is what lets the validator
        # reject a bit carve on one.
        self._available_signals = {
            self._signal_source_id(digital_signal): {"kind": "line"}
            for digital_signal in self._recording.digital_signals
        }
        if detection_configuration is None:
            # The default, used only when the caller passes none: read every line the file carries as a
            # "high_period", the lossless durative reading (onset at the rising edge, duration to the
            # falling edge, for an active-high line). The "midpoint" cut is what a line takes: it falls
            # strictly between the two levels whatever they are, so it needs no knowledge of the file.
            detection_configuration = {
                signal_source_id: [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "high_period"}]
                for signal_source_id in self._available_signals
            }
        # One construction-time check, on the default as well as on a caller-supplied configuration: the
        # default is machine-built but its inputs are not, so it too can resolve two event types to the
        # same identifier. Validation covers structure and identifier resolution alike.
        _validate_detection_configuration(detection_configuration, self._available_signals)
        self._detection_configuration = detection_configuration

    @staticmethod
    def _signal_source_id(digital_signal) -> str:
        """Name a line after the digital input it came off, counting from one as the vendor does."""
        return f"digital_{digital_signal.digital_input + 1}"

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the PyPhotometryEventsInterface.

        ``NWBFile/session_start_time`` is populated from the header's ``date_time``, which every header
        generation carries.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        date_time = self._recording.header.get("date_time")
        if date_time is not None:
            metadata["NWBFile"]["session_start_time"] = datetime.fromisoformat(date_time)

        # Each event_type_source_id resolved from the configuration is its own event type, and event_name
        # (the human-facing label) defaults to that identifier. A .ppd carries no meaning for a line, not
        # even a label, so only the name is seeded here. Derived from the configuration rather than from
        # the events, so whether a line happened to fire does not change which event types the
        # configuration asked for.
        for event_type_source_id in _get_event_type_source_ids(self._detection_configuration):
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = {
                "event_name": event_type_source_id
            }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build the internal event representation by edge-detecting each selected line, cached.

        Each entry of the resolved plan becomes one :class:`_EventsData` keyed by its
        ``event_type_source_id``: its line is read per the spec's ``detection`` into onset frames and, for
        a durative reading, offset frames, which are then read against that line's own clock. An event
        type with no event (a line that never toggles) keeps its entry with empty timestamps, which the
        writer renders as a zero-row table.

        A ``.ppd`` line is already a ``0``/``1`` signal by the time the reader hands it over, so its cut
        is the derived midpoint, which lands between the two levels and hands detection back the same line.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        # Built here rather than held on the interface: the configuration is the source of truth, and the
        # plan is pure and cheap to rebuild. Grouped by signal, so a line is read once however many event
        # types it yields.
        detection_plan = _resolve_detection_plan(self._detection_configuration)
        digital_signals = {
            self._signal_source_id(digital_signal): digital_signal
            for digital_signal in self._recording.digital_signals
        }

        events_data_dict = {}
        for signal_source_id, detection_specs in detection_plan.items():
            digital_signal = digital_signals[signal_source_id]
            # A .ppd stores no clock, only a rate, and each line starts when the analog input it shares a
            # slot with does. The clock is handed over as a function of frame so only the frames the
            # events landed on are read, rather than materialising one timestamp per sample to index a
            # few dozen of them.
            def read_clock(frames, digital_signal=digital_signal):
                return digital_signal.starting_time_in_seconds + np.asarray(frames) / digital_signal.rate_in_hz

            for event_type_source_id, spec in detection_specs:
                conditioned = _condition_signal(digital_signal.data, spec["signal_conditioning"])
                onset_frames, offset_frames = _detect_events(conditioned, spec["detection"])
                onsets, durations = _frames_to_seconds(onset_frames, offset_frames, read_clock)
                events_data_dict[event_type_source_id] = _EventsData(
                    event_type_source_id=event_type_source_id,
                    timestamps=onsets,
                    durations=durations,
                )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
