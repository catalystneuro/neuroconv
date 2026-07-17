import re
from datetime import timezone

import numpy as np
from pydantic import FilePath, validate_call

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ...ophys.inscopix.inscopixgpiodatainterface import (
    _read_gpio,
    get_gpio_channel_inventory,
)
from ....utils import DeepDict

_VALID_READINGS = ("changes", "rising", "falling", "interval")


class InscopixGpioEventsInterface(BaseEventsInterface):
    """Data interface for discrete events derived from an Inscopix ``.gpio`` file.

    Inscopix stores each channel as a sparse ``(timestamp, amplitude)`` change-point sequence (bracketed
    by an opening sample at the recording start and a closing held-value sample at the end). Discrete
    events are *derived* from those change-points; this interface writes each configured channel as a
    ``pynwb.event.EventsTable`` into ``nwbfile.events``. It never stores the raw trace , that is the
    additive, independent job of :class:`.InscopixGpioInterface`.

    Selection is explicit (the file records no analog-vs-event flag): name each channel in
    ``events_config`` and say how to read it. Each entry has two orthogonal knobs:

    - ``levels`` (optional): cut the amplitude into band indices with ``numpy.digitize`` (N cut points
      -> bands ``0..N``). Omit it and the value is the raw amplitude. A coded line (an odor-concentration
      code) uses this; the band index becomes a categorical column.
    - ``reading`` (default ``"changes"``): which value-transitions become events. An event happens where
      the value actually changes vs the previous sample (so the opening/closing boundary samples, which
      are not changes, never produce events, and no ``amplitude > 0`` threshold is assumed):

      - ``"changes"`` , every transition (carrying the value it changed to);
      - ``"rising"`` / ``"falling"`` , only transitions where the value increased / decreased;
      - ``"interval"`` , each increase paired with the next decrease, giving an onset + ``duration``.

    A value column is written for a ``levels`` line (the band, categorical) and for ``"changes"`` on a
    raw line (the raw value); ``rising``/``falling``/``interval`` on a raw line are timestamp-only (the
    direction is implied).
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
            Maps a channel name to how it is read: ``{"reading": ..., "levels": [...], "field": ...}``.
            ``reading`` is one of ``"changes"`` (default), ``"rising"``, ``"falling"``, ``"interval"``;
            ``levels`` (optional) quantizes the amplitude into band indices; ``field`` (optional, default
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
        ``"changes"`` raw line gets a plain numeric value column; a directional reading on a raw line is
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
    """Turn one channel's change-points into an :class:`_EventsData`, per its ``levels``/``reading``.

    Events occur at value transitions (``value[i] != value[i-1]``), which excludes the opening sample
    and any repeated closing sample by construction; ``rising``/``falling`` compare the value to the
    previous one (no ``amplitude > 0`` threshold), so a non-zero-baseline line (e.g. 48/64) works.
    """
    reading = entry.get("reading", "changes")
    if reading not in _VALID_READINGS:
        raise ValueError(
            f"Invalid reading '{reading}' for channel '{channel_name}'; expected one of {_VALID_READINGS}."
        )
    field = entry.get("field", "value")
    leveled = "levels" in entry
    values = np.digitize(amplitudes, entry["levels"]) if leveled else amplitudes

    transitions = np.flatnonzero(values[1:] != values[:-1]) + 1  # indices where the value actually changed
    if len(transitions) == 0:
        return None
    previous, current, times = (
        values[transitions - 1],
        values[transitions],
        timestamps_seconds[transitions],
    )

    if reading == "rising":
        keep = current > previous
    elif reading == "falling":
        keep = current < previous
    else:  # "changes" keeps all transitions; "interval" onsets are the rising transitions
        keep = np.ones(len(transitions), dtype=bool) if reading == "changes" else current > previous
    if not keep.any():
        return None
    event_times, event_values = times[keep], current[keep]

    durations = None
    if reading == "interval":
        falling_times = times[current < previous]
        durations = np.full(len(event_times), np.nan)
        if len(falling_times):
            positions = np.searchsorted(falling_times, event_times, side="right")
            valid = positions < len(falling_times)
            durations[valid] = falling_times[positions[valid]] - event_times[valid]

    # A coded (leveled) line always carries its band; a raw line carries its value only for "changes".
    if leveled:
        payload = {field: event_values.astype(int)}
    elif reading == "changes":
        payload = {field: event_values}
    else:
        payload = {}

    return _EventsData(
        event_type_source_id=channel_name,
        timestamps=event_times,
        durations=durations,
        payload=payload,
    )


def _to_snake_case(name: str) -> str:
    """``"BNC Sync Output"`` -> ``bnc_sync_output`` (a lowercase name the base writer CamelCases cleanly)."""
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", name)).strip("_").lower()
