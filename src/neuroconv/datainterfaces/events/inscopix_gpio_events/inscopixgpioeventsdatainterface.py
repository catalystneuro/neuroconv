import re
from datetime import timezone

import numpy as np
from pydantic import FilePath, validate_call

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ...ophys.inscopix.inscopixgpiodatainterface import (
    _read_gpio,
    get_gpio_channel_inventory,
)
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


class InscopixGpioEventsInterface(BaseEventsInterface):
    """Data interface for discrete events derived from an Inscopix ``.gpio`` file.

    Inscopix stores each channel as a sparse ``(timestamp, amplitude)`` change-point sequence (bracketed
    by an opening sample at the recording start and a closing held-value sample at the end). Discrete
    events are *derived* from those change-points; this interface writes each derived event type as a
    ``pynwb.event.EventsTable`` into ``nwbfile.events``. It never stores the raw trace, that is the
    additive, independent job of :class:`.InscopixGpioInterface`.

    **Selection is explicit and ``detection_configuration`` is required**, because the file records no
    analog-versus-digital flag: nothing in the bytes says which channels are lines, which are coded
    levels, and which are continuous signals, so there is no lossless default to derive and a channel
    you do not name is not read. Use :meth:`get_available_channels` to inspect the file first.

    That missing flag also makes this the one interface whose signals have **no kind**, so the validator
    admits every cut and the caller carries the assertion that a named channel really is readable as
    discrete events. :meth:`get_available_channels` is what makes that assertion informed: it reports
    each channel's value set, so a coded channel is visible as one before a cut is chosen for it.
    """

    keywords = ("events", "inscopix", "gpio")
    display_name = "Inscopix GPIO Events"
    associated_suffixes = (".gpio",)
    info = "Interface for discrete events derived from Inscopix GPIO channels."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        detection_configuration: dict[str, list[dict]],
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the InscopixGpioEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.gpio`` Inscopix file.
        detection_configuration : dict
            Which channels to read and how, keyed by the channel's ``signal_source_id`` (its name in the
            file, e.g. ``{"BNC Sync Output": [{"signal_conditioning": {"binarize": "midpoint"},
            "detection": "rising"}]}``). Each value is a **list** of
            detection specs, one per event type derived from that channel, since a channel can yield more
            than one. A spec's ``detection`` is one of ``"rising"`` / ``"falling"`` (a point event at each
            edge), ``"high_period"`` / ``"low_period"`` (a durative event, onset at one edge and duration
            to the next opposite edge), or ``"value_change"`` (a point event at every transition), and it
            is required. ``signal_conditioning`` is required too and says how the channel becomes a line:
            a channel that is already two-valued takes ``{"binarize": "midpoint"}``, whose cut falls
            strictly between its levels whatever they are (a ``0``/``1`` line and a line at 48 and 64
            alike), and a coded channel takes ``{"binarize": c}`` naming where to cut. An optional
            ``event_name`` replaces the derived identifier and is required when a channel fans out on
            numeric cuts, since a cut point does not stringify into a stable name.

            To distinguish the levels of a coded channel, cut it into one line per level and give each its
            own spec, rather than reading the code itself::

                {"GPIO-2": [
                    {"signal_conditioning": {"binarize": 136}, "detection": "high_period",
                     "event_name": "odor_present"},
                    {"signal_conditioning": {"binarize": 192}, "detection": "high_period",
                     "event_name": "odor_high"},
                ]}

            Each cut becomes its own durative event type with real start and stop times, and the band the
            channel occupies at any instant is how many of them are open, so nothing is lost. Reading the
            whole coded channel as ``value_change`` instead gives one event type marking every level
            change, with nothing to tell the levels apart.
        metadata_key : str, optional
            Key under ``metadata["Events"]`` for this interface. If None (default),
            ``"inscopix_gpio_events"``.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            file_path=file_path,
            detection_configuration=detection_configuration,
            verbose=verbose,
        )
        self.metadata_key = metadata_key or "inscopix_gpio_events"
        # available_signals: signal_source_id (the channel's name in the file) -> its descriptor. The
        # kind is None for every channel because a .gpio file records no analog-versus-digital flag, so
        # the validator admits every cut and every omission here and the read-time backstop is what
        # catches a channel that does not support the reading asked of it.
        self._available_signals = self._get_available_signals(self.source_data["file_path"])
        _validate_detection_configuration(detection_configuration, self._available_signals)
        self._detection_configuration = detection_configuration

    @staticmethod
    def _get_available_signals(file_path) -> dict[str, dict]:
        """Return ``signal_source_id -> {kind, channel_index}`` for every channel in the file.

        Names and positions only, so construction stays cheap: the amplitudes are never touched here.
        Every kind is None because the format records nothing that would settle it.
        """
        gpio = _read_gpio(file_path)
        return {
            gpio.get_channel_name(index): {"kind": None, "channel_index": index} for index in range(gpio.num_channels)
        }

    @classmethod
    def get_available_channels(cls, file_path) -> list[dict]:
        """Return the channel inventory of a ``.gpio`` file (see :func:`.get_gpio_channel_inventory`).

        Richer than the interface's own discovery, and the thing to call before writing a
        ``detection_configuration``: it reports each channel's value set, which is what tells you whether
        a channel is a line (cut it at ``"midpoint"``), a coded level (cut it once per level), or a
        continuous signal (not events at all). It reads every channel's amplitudes, which is why the
        interface does not call it.
        """
        return get_gpio_channel_inventory(file_path)

    def get_metadata(self) -> DeepDict:
        """Seed one ``event_types`` entry per event type the configuration resolves to.

        ``NWBFile/session_start_time`` is populated from the file's own start time.

        Derived from the configuration rather than from the events, so metadata costs no amplitude read
        and does not depend on whether a channel happened to change. The ``event_name`` is the identifier
        in snake case, because an Inscopix channel name carries spaces and hyphens (``BNC Sync Output``,
        ``GPIO-2``) that do not survive as an NWB object name.
        """
        metadata = super().get_metadata()
        gpio = _read_gpio(self.source_data["file_path"])
        metadata["NWBFile"]["session_start_time"] = gpio.timing.start.to_datetime().replace(tzinfo=timezone.utc)

        for event_type_source_id in _get_event_type_source_ids(self._detection_configuration):
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = {
                "event_name": _to_snake_case(event_type_source_id),
                "event_description": f"Events derived from Inscopix GPIO channel '{event_type_source_id}'.",
            }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Derive one :class:`_EventsData` per configured event type from the change-points (cached).

        Each channel is read once however many event types it yields, then each spec conditions and
        detects independently. Onset and offset **frames** index the channel's own change-point
        timestamps, so a duration is the elapsed clock time between the two edges. That matters more here
        than anywhere else: Inscopix change-points are irregularly spaced, so a frame count times an
        assumed sampling period would be wrong for every event.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        gpio = _read_gpio(self.source_data["file_path"])
        # Grouped by signal, so a channel is read once however many event types it yields.
        detection_plan = _resolve_detection_plan(self._detection_configuration)

        events_data_dict = {}
        for signal_source_id, detection_specs in detection_plan.items():
            channel_index = self._available_signals[signal_source_id]["channel_index"]
            timestamps_microseconds, amplitudes = gpio.get_channel_data(channel_index)
            time = np.asarray(timestamps_microseconds, dtype="float64") / 1e6
            data = np.asarray(amplitudes, dtype="float64")
            for event_type_source_id, spec in detection_specs:
                conditioned = _condition_signal(data, spec.get("signal_conditioning"))
                onset_frames, offset_frames = _detect_events(conditioned, spec["detection"])
                onsets, durations = _frames_to_seconds(onset_frames, offset_frames, time)
                events_data_dict[event_type_source_id] = _EventsData(
                    event_type_source_id=event_type_source_id,
                    timestamps=onsets,
                    durations=durations,
                )

        self._events_data_dict = events_data_dict
        return self._events_data_dict


def _to_snake_case(name: str) -> str:
    """``"BNC Sync Output"`` -> ``bnc_sync_output`` (a lowercase name the base writer CamelCases cleanly)."""
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", name)).strip("_").lower()
