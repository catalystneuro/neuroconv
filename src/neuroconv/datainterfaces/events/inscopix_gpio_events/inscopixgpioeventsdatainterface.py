from datetime import timezone

import numpy as np
from pydantic import FilePath, validate_call

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ...ophys.inscopix._inscopix_gpio_reader import get_gpio_channel_inventory, read_gpio
from ...ophys.inscopix.inscopixgpiodatainterface import _to_snake_case
from ....tools.signal_processing import _detect_occurrences
from ....utils import DeepDict

# How the eight digital inputs and eight digital outputs are wired on the DAQ box is not documented
# publicly, and it decides whether they are one port each or eight sources each. Until it is known they
# are listed but refused, so either answer can be added later without changing a configuration.
_DIGITAL_CHANNEL_PREFIXES = ("Digital GPI ", "Digital GPO ")
_DIGITAL_CHANNELS_ISSUE_URL = "https://github.com/catalystneuro/neuroconv/issues/2280"


class InscopixGpioEventsInterface(BaseEventsInterface):
    """Data interface for discrete events derived from an Inscopix ``.gpio`` file.

    Inscopix stores each channel as a sparse ``(timestamp, amplitude)`` change-point sequence (bracketed
    by an opening sample at the recording start and a closing held-value sample at the end). Discrete
    events are *derived* from those change-points; this interface writes each derived event type as a
    ``pynwb.event.EventsTable`` into ``nwbfile.events``. It never stores the raw trace, that is the
    additive, independent job of :class:`.InscopixGpioInterface`.

    **Selection is explicit and ``event_extraction_configuration`` is required**, because the file
    records no analog-versus-digital flag: nothing in the bytes says which channels are lines, which are
    coded levels, and which are continuous signals, so there is no lossless default to derive and a
    channel you do not name is not read. Each channel is a source of its own, and an entry cuts it into a
    line with ``signal_conditioning`` before ``detection`` reads it. The digital inputs and outputs
    (``Digital GPI 0`` to ``7`` and ``Digital GPO 0`` to ``7``) are not supported as event sources yet;
    :class:`.InscopixGpioInterface` still writes them as ``TimeSeries``. Use :meth:`get_available_channels`
    to inspect the file first: it reports each channel's value set, so a coded channel is visible as one
    before a cut is chosen for it.

    Do not read two ``.gpio`` files with the same name at the same time, even from different folders:
    pyisx converts each into a temporary file named after the file name alone, so parallel reads
    overwrite each other's copy and fail.
    """

    keywords = ("events", "inscopix", "gpio")
    display_name = "Inscopix GPIO Events"
    _supports_event_extraction_configuration = True
    associated_suffixes = (".gpio",)
    info = "Interface for discrete events derived from Inscopix GPIO channels."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        event_extraction_configuration: dict[str, dict],
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the InscopixGpioEventsInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.gpio`` Inscopix file.
        event_extraction_configuration : dict
            Entries keyed by the event type identifier. Each entry names a channel of the file in
            ``source``, cuts it into a line with ``signal_conditioning`` and says which changes are events
            with ``detection``, for example ``{"frames": {"source": "BNC Sync Output",
            "signal_conditioning": {"binarize": "midpoint"}, "detection": {"on_change": {"onset":
            "rising"}}}}``. A channel that is already two-valued takes ``{"binarize": "midpoint"}``, whose
            cut falls strictly between its levels whatever they are (a ``0``/``1`` line and a line at 48
            and 64 alike), and a coded channel takes ``{"binarize": c}`` naming where to cut.

            To distinguish the levels of a coded channel, give each cut an entry of its own on the same
            channel, rather than reading the code itself::

                {
                    "odor_present": {
                        "source": "GPIO-2",
                        "signal_conditioning": {"binarize": 136},
                        "detection": {"on_change": {"onset": "rising", "end": "falling"}},
                    },
                    "odor_high": {
                        "source": "GPIO-2",
                        "signal_conditioning": {"binarize": 192},
                        "detection": {"on_change": {"onset": "rising", "end": "falling"}},
                    },
                }

            Each cut becomes its own durative event type with real start and stop times, and the band the
            channel occupies at any instant is how many of them are open, so nothing is lost.

            ``timestamp_estimate`` is refused: the file records the time of each change, so each event
            takes that time.
        metadata_key : str, optional
            Key under ``metadata["Events"]`` for this interface. If None (default),
            ``"inscopix_gpio_events"``.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        self.metadata_key = metadata_key or "inscopix_gpio_events"
        self._channel_indices = self._get_channel_indices(file_path)
        available_sources = {
            channel_name: {"supported_operations": ["signal_conditioning", "detection"]}
            for channel_name in self._channel_indices
        }
        for channel_name in available_sources:
            if channel_name.startswith(_DIGITAL_CHANNEL_PREFIXES):
                available_sources[channel_name] = {
                    "supported_operations": [],
                    "unsupported_reason": (
                        "events from the digital inputs and outputs of the DAQ box are not supported yet. "
                        f"If you need them, see {_DIGITAL_CHANNELS_ISSUE_URL}"
                    ),
                }
        self._event_extraction_configuration = self._resolve_event_sources(
            event_extraction_configuration, available_sources
        )
        # A .gpio file stores each change with its own timestamp, so an event takes the time of its change.
        # The stored point before a change is the previous change, which can be seconds earlier, so an
        # estimate that reads the sample before a change has no meaning here.
        for entry_name, entry in self._event_extraction_configuration.items():
            if "timestamp_estimate" in entry.get("detection", {}):
                raise ValueError(
                    f"Event extraction entry {entry_name!r} sets 'timestamp_estimate', which does not apply to an "
                    "Inscopix .gpio file. The file records the time of each change, so each event takes that time."
                )
        super().__init__(
            file_path=file_path,
            event_extraction_configuration=event_extraction_configuration,
            verbose=verbose,
        )

    def get_event_type_source_ids(self) -> list[str]:
        """The event types the configuration names, read from nothing."""
        return list(self._event_extraction_configuration)

    @staticmethod
    def _get_channel_indices(file_path) -> dict[str, int]:
        """Return ``channel name -> channel index`` for every channel in the file.

        Names and positions only, so construction stays cheap: the amplitudes are never touched here.
        """
        gpio = read_gpio(file_path)
        return {gpio.get_channel_name(index): index for index in range(gpio.num_channels)}

    @classmethod
    def get_available_event_sources(cls, file_path: FilePath) -> list[str]:
        """List every channel in the file, in file order."""
        return list(cls._get_channel_indices(file_path))

    @classmethod
    def get_available_channels(cls, file_path) -> list[dict]:
        """Return one dict per channel of a ``.gpio`` file.

        Richer than the interface's own discovery, and the thing to call before writing an
        ``event_extraction_configuration``: it reports each channel's value set, which is what tells you whether
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
        gpio = read_gpio(self.source_data["file_path"])
        metadata["NWBFile"]["session_start_time"] = gpio.timing.start.to_datetime().replace(tzinfo=timezone.utc)

        for event_type_source_id in self.get_event_type_source_ids():
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = {
                "event_name": _to_snake_case(event_type_source_id),
                "event_description": f"Events derived from Inscopix GPIO channel '{event_type_source_id}'.",
            }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Derive one :class:`_EventsData` per configured entry from the change-points (cached).

        Onset and offset samples index the channel's own change-point timestamps, so a duration is the
        elapsed clock time between the two edges. That matters more here than anywhere else: Inscopix
        change-points are irregularly spaced, so a sample count times an assumed sampling period would be
        wrong for every event.
        """
        if self._events_data_dict is not None:
            return self._events_data_dict

        gpio = read_gpio(self.source_data["file_path"])
        events_data_dict = {}
        for event_type_source_id, entry in self._event_extraction_configuration.items():
            timestamps_microseconds, amplitudes = gpio.get_channel_data(self._channel_indices[entry["source"]])
            onsets, durations = _detect_occurrences(
                entry=entry,
                trace=np.asarray(amplitudes, dtype="float64"),
                timestamps=np.asarray(timestamps_microseconds, dtype="float64") / 1e6,
            )
            events_data_dict[event_type_source_id] = _EventsData(
                event_type_source_id=event_type_source_id,
                timestamps=onsets,
                durations=durations,
            )

        self._events_data_dict = events_data_dict
        return self._events_data_dict
