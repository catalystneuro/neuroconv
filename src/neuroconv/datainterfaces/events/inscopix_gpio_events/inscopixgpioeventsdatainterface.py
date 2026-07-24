import re
from datetime import timezone

import numpy as np
from pydantic import FilePath, validate_call

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ...ophys.inscopix.inscopixgpiodatainterface import (
    _read_gpio,
    get_gpio_channel_inventory,
)
from ....tools.signal_processing import discretize_trace
from ....utils import DeepDict

# The reading vocabulary is shared with IntanDigitalInterface: a plain digital line is edge-detected the
# same way in both (via ``discretize_trace``), with the same durative ``high_period`` default. ``changes``
# is an Inscopix-only extra for a multi-value/coded line, which ``discretize_trace`` (binary by design)
# cannot express, so it keeps its own minimal path here.
_VALID_DETECT = ("changes", "rising", "falling", "high_period", "low_period")


class InscopixGpioEventsInterface(BaseEventsInterface):
    """Data interface for discrete events derived from an Inscopix ``.gpio`` file.

    Inscopix stores each channel as a sparse ``(timestamp, amplitude)`` change-point sequence (bracketed
    by an opening sample at the recording start and a closing held-value sample at the end). Discrete
    events are *derived* from those change-points; this interface writes each configured channel as a
    ``pynwb.event.EventsTable`` into ``nwbfile.events``. It never stores the raw trace, that is the
    additive, independent job of :class:`.InscopixGpioInterface`.

    Selection is explicit (the file records no analog-vs-event flag): name each channel in
    ``events_config`` and say how to read it. Each entry has two orthogonal knobs:

    - ``levels`` (optional): cut the amplitude into band indices with ``numpy.digitize`` (N cut points
      -> bands ``0..N``). Omit it and the value is the raw amplitude. A coded line (an odor-concentration
      code) uses this; the band index becomes a categorical column.
    - ``detect`` (default ``"high_period"`` for a plain line, ``"changes"`` for a ``levels`` line): how
      the line's transitions become events. The naming and default match
      :class:`.IntanDigitalInterface`, and for a plain digital line the four edge readings are delegated
      to the shared :func:`~neuroconv.tools.signal_processing.discretize_trace`, so both interfaces
      produce events the same way:

      - ``"high_period"`` , each rising edge paired with the next falling edge (onset + ``duration``);
      - ``"low_period"`` , each falling edge paired with the next rising edge (onset + ``duration``);
      - ``"rising"`` / ``"falling"`` , only the up / down transitions, as point events;
      - ``"changes"`` , every value transition (carrying the value it changed to). This is Inscopix-only:
        a multi-value/coded line has no equivalent in ``discretize_trace`` (which is binary), so it keeps
        its own path. A raw line's transitions are thresholded at the trace mean (so a non-zero-baseline
        binary line such as 48/64 still reads "rising = value increased").

    A value column is written for a ``levels`` line (the band, categorical) and for ``"changes"`` on a
    raw line (the raw value); the binary edge readings on a raw line are timestamp-only (the direction is
    implied). A ``levels`` (coded) line keeps its band-comparison edge logic for every ``detect`` (its
    band identity has no binary equivalent), and always carries the band.
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
        events_config: dict[str, dict],
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the InscopixGpioEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.gpio`` Inscopix file.
        events_config : dict
            Maps a channel name to how it is read: ``{"detect": ..., "levels": [...], "field": ...}``.
            ``detect`` is one of ``"high_period"`` (the default for a plain line), ``"low_period"``,
            ``"rising"``, ``"falling"``, or ``"changes"`` (the default for a ``levels`` line); ``levels``
            (optional) quantizes the amplitude into band indices; ``field`` (optional, default
            ``"value"``) names the value column. A channel not listed is not written. Use
            :meth:`get_available_channels` to inspect the file first.
        metadata_key : str, optional
            Key under ``metadata["Events"]`` for this interface. If None (default),
            ``"inscopix_gpio_events"``.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(file_path=file_path, events_config=events_config, verbose=verbose)
        self.metadata_key = metadata_key or "inscopix_gpio_events"

    @classmethod
    def get_available_channels(cls, file_path) -> list[dict]:
        """Return the channel inventory of a ``.gpio`` file (see :func:`.get_gpio_channel_inventory`)."""
        return get_gpio_channel_inventory(file_path)

    def get_metadata(self) -> DeepDict:
        """Seed one ``event_types`` entry per configured channel.

        A ``levels`` line gets a categorical value column (band index, with a ``labels`` map); a
        ``"changes"`` raw line gets a plain numeric value column; an edge reading on a raw line is
        timestamp-only (empty ``columns``).
        """
        metadata = super().get_metadata()
        gpio = _read_gpio(self.source_data["file_path"])
        metadata["NWBFile"]["session_start_time"] = gpio.timing.start.to_datetime().replace(tzinfo=timezone.utc)

        events_config = self.source_data["events_config"]
        for channel_name, event in self._get_events_data_dict().items():
            entry = events_config[channel_name]
            field = entry.get("field", "value")
            spec = {
                "event_name": _to_snake_case(channel_name),
                "event_description": f"Events derived from Inscopix GPIO channel '{channel_name}'.",
                "columns": {},
            }
            if field in event.payload:
                column = {
                    "column_name": field,
                    "description": f"Value of channel '{channel_name}' per event.",
                }
                if "levels" in entry:  # a coded band index -> categorical, seed labels over observed bands
                    observed = np.unique(event.payload[field])
                    column["column_categories"] = {"labels": {int(band): str(int(band)) for band in observed}}
                spec["columns"] = {field: column}
            metadata["Events"][self.metadata_key]["event_types"][channel_name] = spec
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Derive one :class:`_EventsData` per configured channel from the file's change-points (cached)."""
        if self._events_data_dict is not None:
            return self._events_data_dict

        gpio = _read_gpio(self.source_data["file_path"])
        present_channels = set(gpio.channel_dict)
        events_config = self.source_data["events_config"]

        events_data_dict = {}
        for channel_name, entry in events_config.items():
            if channel_name not in present_channels:
                raise ValueError(
                    f"Channel '{channel_name}' named in events_config is not present in the file "
                    f"(available: {sorted(present_channels)})."
                )
            timestamps_microseconds, amplitudes = gpio.get_channel_data(gpio.get_channel_index(channel_name))
            if len(timestamps_microseconds) == 0:
                continue
            event = _derive_events(
                channel_name,
                entry,
                np.asarray(timestamps_microseconds, dtype="float64") / 1e6,
                np.asarray(amplitudes),
            )
            if event is not None:
                events_data_dict[channel_name] = event

        self._events_data_dict = events_data_dict
        return self._events_data_dict


def _derive_events(channel_name, entry, timestamps_seconds, amplitudes) -> _EventsData | None:
    """Turn one channel's change-points into an :class:`_EventsData`, per its ``levels``/``detect``.

    A plain (non-``levels``) line is edge-detected exactly as ``IntanDigitalInterface`` does, via the
    shared :func:`~neuroconv.tools.signal_processing.discretize_trace`; ``changes`` on a plain line keeps
    its own value-carrying transition path (``discretize_trace`` is binary). A ``levels`` (coded) line
    keeps a band-comparison path for every reading, because its band identity has no binary equivalent.
    """
    leveled = "levels" in entry
    detect = entry.get("detect")
    if detect is None:  # a plain line defaults to Intan's ``high_period``; a coded line to its transitions
        detect = "changes" if leveled else "high_period"
    if detect not in _VALID_DETECT:
        raise ValueError(f"Invalid detect '{detect}' for channel '{channel_name}'; expected one of {_VALID_DETECT}.")
    field = entry.get("field", "value")

    if leveled:
        bands = np.digitize(amplitudes, entry["levels"])
        return _derive_from_bands(channel_name, detect, field, timestamps_seconds, bands)
    return _derive_from_trace(channel_name, detect, field, timestamps_seconds, amplitudes)


def _derive_from_trace(channel_name, detect, field, timestamps_seconds, amplitudes) -> _EventsData | None:
    """Derive events from a plain (raw) line: ``changes`` carries the value; the four edge readings route
    through :func:`~neuroconv.tools.signal_processing.discretize_trace`, timestamp-only.

    ``discretize_trace`` returns onset frame indices into the change-point array and, for a durative
    reading, per-event durations **in frames** (the close index minus the onset index, ``NaN`` where the
    interval never closes). The change-points are irregularly spaced, so a frame delta is not a fixed
    period: the onset frame plus the frame duration is the close index, and the duration in seconds is the
    difference of the two change-point timestamps.
    """
    if detect == "changes":  # every transition, carrying the value it changed to (Inscopix-only path)
        transitions = np.flatnonzero(amplitudes[1:] != amplitudes[:-1]) + 1
        if len(transitions) == 0:
            return None
        return _EventsData(
            event_type_source_id=channel_name,
            timestamps=timestamps_seconds[transitions],
            durations=None,
            payload={field: amplitudes[transitions]},
        )

    # Default threshold (the trace mean) so a non-zero-baseline binary line (e.g. 48/64) still reads
    # "rising = value increased" rather than assuming an ``amplitude > 0`` high state.
    onset_frames, duration_frames = discretize_trace(amplitudes, detect)
    if len(onset_frames) == 0:
        return None
    durations = None
    if duration_frames is not None:
        durations = np.full(len(onset_frames), np.nan)
        matched = ~np.isnan(duration_frames)
        close_frames = (onset_frames[matched] + duration_frames[matched]).astype("int64")
        durations[matched] = timestamps_seconds[close_frames] - timestamps_seconds[onset_frames[matched]]
    return _EventsData(
        event_type_source_id=channel_name,
        timestamps=timestamps_seconds[onset_frames],
        durations=durations,
        payload={},
    )


def _derive_from_bands(channel_name, detect, field, timestamps_seconds, bands) -> _EventsData | None:
    """Derive events from a ``levels`` (coded) line by comparing band indices, always carrying the band.

    ``discretize_trace`` is binary and would erase the band identity, so a coded line keeps this
    Inscopix-specific path: ``changes`` keeps every band transition, ``rising``/``high_period`` keep the
    band increases, ``falling``/``low_period`` the band decreases, and a durative reading pairs each onset
    with the next opposite-direction band change.
    """
    transitions = np.flatnonzero(bands[1:] != bands[:-1]) + 1  # indices where the band actually changed
    if len(transitions) == 0:
        return None
    previous, current, times = bands[transitions - 1], bands[transitions], timestamps_seconds[transitions]

    if detect in ("rising", "high_period"):
        keep = current > previous
    elif detect in ("falling", "low_period"):
        keep = current < previous
    else:  # "changes"
        keep = np.ones(len(transitions), dtype=bool)
    if not keep.any():
        return None
    event_times, event_bands = times[keep], current[keep]

    durations = None
    if detect in ("high_period", "low_period"):
        opposite = times[current < previous] if detect == "high_period" else times[current > previous]
        durations = np.full(len(event_times), np.nan)
        if len(opposite):
            positions = np.searchsorted(opposite, event_times, side="right")
            valid = positions < len(opposite)
            durations[valid] = opposite[positions[valid]] - event_times[valid]

    return _EventsData(
        event_type_source_id=channel_name,
        timestamps=event_times,
        durations=durations,
        payload={field: event_bands.astype(int)},
    )


def _to_snake_case(name: str) -> str:
    """``"BNC Sync Output"`` -> ``bnc_sync_output`` (a lowercase name the base writer CamelCases cleanly)."""
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", name)).strip("_").lower()
