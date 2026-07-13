import re

import numpy as np
from pydantic import FilePath, validate_call

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ....tools import get_package
from ....utils import DeepDict

_VALID_READINGS = ("rising", "falling", "interval")


class InscopixGpioEventsInterface(BaseEventsInterface):
    """Data interface for discrete events derived from an Inscopix ``.gpio`` file.

    Inscopix is a **signal-encoded** events source: the ``.gpio`` file stores each channel as sparse
    ``(timestamp_microseconds, amplitude)`` change-events, and discrete events are *derived* from those
    change-events (edge-detect a digital line, cut a coded analog line at levels). This is separate from
    :class:`.InscopixGpioInterface`, which stores the raw analog channels as ``TimeSeries``; the two read
    the same file independently, and this interface never stores the raw trace.

    Which channels become events, and how each is read, is set by ``events_config`` at construction
    (signal-encoded selection is by inclusion: a channel that is not named is never written). Each named
    channel becomes one ``pynwb.event.EventsTable`` in ``nwbfile.events``:

    - a **digital line** (config entry has ``reading``) is edge-detected into a timestamp-only event
      type: ``reading="rising"`` (default) keeps the low->high edges, ``"falling"`` the high->low edges,
      and ``"interval"`` pairs each rising edge with the next falling edge into an onset + duration.
    - a **coded analog line** (config entry has ``levels``) is cut into bands with ``numpy.digitize``,
      and an event is emitted at each band change, carrying the band index as one categorical column.

    Because Inscopix hands each line back as its own named channel (unlike a packed digital word), there
    is no bit-unpacking step; every channel is one event type keyed by its channel name.
    """

    keywords = ("events", "inscopix", "gpio")
    display_name = "Inscopix GPIO Events"
    associated_suffixes = (".gpio",)
    info = "Interface for discrete events derived from Inscopix GPIO digital and coded channels."

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
            Maps a channel name to how it is read. Each entry is either a digital-line spec
            ``{"reading": "rising" | "falling" | "interval"}`` (``reading`` defaults to ``"rising"``) or
            a coded-analog spec ``{"levels": [c1, c2, ...], "field": "concentration"}`` (``field`` names
            the value column, defaulting to ``"value"``). A channel that is not listed is not written.
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata. If
            None (default), ``"inscopix_gpio_events"`` is used.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(file_path=file_path, events_config=events_config, verbose=verbose)
        self.metadata_key = metadata_key or "inscopix_gpio_events"

    def get_metadata(self) -> DeepDict:
        """Seed the events metadata: one ``event_types`` entry per configured channel.

        A digital line gets a timestamp-only entry (empty ``columns``); a coded analog line gets one
        categorical column keyed by its ``field``, with a ``labels`` map over the observed band indices.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        from datetime import timezone

        metadata = super().get_metadata()
        isx = get_package(package_name="isx")
        gpio = isx.GpioSet.read(str(self.source_data["file_path"]))
        session_start_time = gpio.timing.start.to_datetime().replace(tzinfo=timezone.utc)
        metadata["NWBFile"]["session_start_time"] = session_start_time

        events_data = self._get_events_data_dict()
        events_config = self.source_data["events_config"]
        for channel_name, event in events_data.items():
            config_entry = events_config[channel_name]
            event_name = _to_snake_case(channel_name)
            entry = {
                "event_name": event_name,
                "event_description": f"Events derived from Inscopix GPIO channel '{channel_name}'.",
                "columns": {},
            }
            if "levels" in config_entry:  # a coded analog line: one categorical band-index column
                field = config_entry.get("field", "value")
                observed_bands = np.unique(event.payload[field])
                entry["columns"] = {
                    field: {
                        "column_name": field,
                        "description": f"Coded level (band index) of channel '{channel_name}' per event.",
                        "column_categories": {"labels": {int(band): str(int(band)) for band in observed_bands}},
                    }
                }
            metadata["Events"][self.metadata_key]["event_types"][channel_name] = entry
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Derive one :class:`_EventsData` per configured channel from the file's change-events.

        Cached after the first call. A channel that yields no events (never toggles, or has no samples
        at the configured bands) is skipped, since an empty event type is not writable.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        isx = get_package(package_name="isx")
        gpio = isx.GpioSet.read(str(self.source_data["file_path"]))
        present_channels = set(gpio.channel_dict)
        events_config = self.source_data["events_config"]

        events_data_dict = {}
        for channel_name, config_entry in events_config.items():
            if channel_name not in present_channels:
                raise ValueError(
                    f"Channel '{channel_name}' named in events_config is not present in the file "
                    f"(available: {sorted(present_channels)})."
                )
            timestamps_microseconds, amplitudes = gpio.get_channel_data(gpio.get_channel_index(channel_name))
            if len(timestamps_microseconds) == 0:
                continue
            timestamps_seconds = np.asarray(timestamps_microseconds, dtype="float64") / 1e6
            amplitudes = np.asarray(amplitudes)

            if "levels" in config_entry:
                event = self._derive_coded_analog(channel_name, config_entry, timestamps_seconds, amplitudes)
            else:
                event = self._derive_digital(channel_name, config_entry, timestamps_seconds, amplitudes)
            if event is not None:
                events_data_dict[channel_name] = event

        self._events_data_dict = events_data_dict
        return self._events_data_dict

    @staticmethod
    def _derive_digital(channel_name, config_entry, timestamps_seconds, amplitudes) -> _EventsData | None:
        """Edge-detect a digital line from its change-events.

        Each stored change-event *is* a transition, so a change-event landing on a high amplitude is a
        rising edge and one landing on low is a falling edge (the line is expected to rest at 0).
        ``reading="interval"`` pairs each rising edge with the next falling edge into an onset + duration.
        """
        reading = config_entry.get("reading", "rising")
        if reading not in _VALID_READINGS:
            raise ValueError(
                f"Invalid reading '{reading}' for channel '{channel_name}'; expected one of {_VALID_READINGS}."
            )
        is_high = amplitudes > 0
        rising_times = timestamps_seconds[is_high]
        falling_times = timestamps_seconds[~is_high]

        if reading == "rising":
            timestamps, durations = rising_times, None
        elif reading == "falling":
            timestamps, durations = falling_times, None
        else:  # interval: pair each rising edge with the next falling edge strictly after it
            durations = np.full(len(rising_times), np.nan)
            if len(falling_times):
                positions = np.searchsorted(falling_times, rising_times, side="right")
                valid = positions < len(falling_times)
                durations[valid] = falling_times[positions[valid]] - rising_times[valid]
            timestamps = rising_times

        if len(timestamps) == 0:
            return None
        return _EventsData(
            event_type_source_id=channel_name,
            timestamps=timestamps,
            durations=durations,
        )

    @staticmethod
    def _derive_coded_analog(channel_name, config_entry, timestamps_seconds, amplitudes) -> _EventsData | None:
        """Cut a coded analog line into bands and emit an event at each band change.

        ``numpy.digitize(amplitudes, levels)`` maps each sample to a band index; an event is emitted at
        the first sample and wherever the band changes, carrying the band index as the payload field.
        """
        levels = config_entry["levels"]
        field = config_entry.get("field", "value")
        bands = np.digitize(amplitudes, levels)
        change_mask = np.ones(len(bands), dtype=bool)
        change_mask[1:] = bands[1:] != bands[:-1]
        change_indices = np.where(change_mask)[0]
        if len(change_indices) == 0:
            return None
        return _EventsData(
            event_type_source_id=channel_name,
            timestamps=timestamps_seconds[change_indices],
            payload={field: bands[change_indices]},
        )


def _to_snake_case(name: str) -> str:
    """Turn a channel name into a snake_case ``event_name`` (e.g. ``"BNC Sync Output"`` -> ``bnc_sync_output``).

    A lowercase ``event_name`` lets the base writer CamelCase it into a clean table object name
    (``bnc_sync_output`` -> ``BncSyncOutput``), avoiding spaces/hyphens in NWB object names.
    """
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", name)).strip("_").lower()
