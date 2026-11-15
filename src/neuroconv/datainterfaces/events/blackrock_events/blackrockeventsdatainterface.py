"""Interface for the events of a Blackrock event file (``.nev``)."""

import numpy as np
from pydantic import FilePath, validate_call

from ..baseeventsinterface import BaseEventsInterface, _EventsData
from ...ecephys.blackrock._blackrock_events_reader import read_event_file
from ....utils import DeepDict

# For each event type: the payload fields it carries, each with its description. The column is named after the
# field, except where _COLUMN_NAMES says otherwise.
_EVENT_TYPE_COLUMNS = {
    "digital_input": {
        "value": "The value of the 16-bit digital input port written with this event, one bit per line.",
        "insertion_reason": (
            "Why the packet was written, as the bit flags of the Blackrock file specification. Bit 0 is a change "
            "on the digital input port; the other bits changed meaning between spec 2.x and spec 3.0."
        ),
    },
    "comments": {
        "text": "The text of the comment.",
        "start_offset": (
            "The seconds from when the comment was started to when it was written, or NaN when the file does not "
            "record it."
        ),
    },
    "recording_events": {
        "reason": "What the recording did: start, stop, pause or resume.",
    },
    "button_triggers": {
        "trigger_type": "The trigger type of the packet, 1 for a button press.",
    },
    "video_sync": {
        "file_number": "The number of the video file.",
        "frame_number": "The number of the video frame.",
        "elapsed_time": "The elapsed time of the video, in milliseconds, on the video's own clock.",
        "source_id": "The identifier of the video source.",
    },
    "log_events": {
        "mode": "The mode of the log entry.",
        "application": "The application that wrote the log entry.",
        "text": "The text of the log entry.",
    },
    "configuration_changes": {
        "change_type": "The type of the configuration change.",
        "text": "The text describing the configuration change.",
    },
}

# A column whose name ends in `_time` is read as a time on the session clock, which the video's elapsed time is not.
_COLUMN_NAMES = {("video_sync", "elapsed_time"): "elapsed_milliseconds"}


class BlackrockEventsInterface(BaseEventsInterface):
    """Data interface for the events of a Blackrock event file (``.nev``).

    Each kind of event packet in the file that holds at least one packet is written as one
    ``pynwb.event.EventsTable`` in ``nwbfile.events``, with the fields of the packet as columns:

    - ``digital_input``: the 16-bit digital input port, with its ``value`` and ``insertion_reason``.
    - ``comments``: comments typed in Central or sent to it, with their ``text`` and ``start_offset``.
    - ``recording_events``: the starts, stops, pauses and resumes of the recording, in a ``reason`` column.
    - ``button_triggers``, ``video_sync``, ``log_events`` and ``configuration_changes``.

    A digital packet is the value of the whole port at the moment Central wrote it. When Central writes one
    depends on how its digital input was configured (on any change, on a rising edge, or on a strobe), which the
    file does not record, so each packet is written as it is and the port value is not split into lines.

    The times are the packet timestamps divided by the timestamp resolution of the file, as the recording and
    sorting interfaces time the same file.
    """

    display_name = "Blackrock Events"
    keywords = ("events", "Blackrock", "TTL")
    associated_suffixes = (".nev",)
    info = "Interface for converting the events of Blackrock event files."

    @validate_call
    def __init__(self, file_path: FilePath, *, metadata_key: str | None = None, verbose: bool = False):
        """Initialize reading of the events of a Blackrock event file.

        Parameters
        ----------
        file_path : FilePath
            Path to the Blackrock event file (``.nev``).
        metadata_key : str, optional
            The key under ``metadata["Events"]`` that namespaces this interface's events metadata.
            If None (default), ``"blackrock_events"`` is used.
        verbose : bool, default: False
            Whether to output verbose text.
        """
        self.metadata_key = metadata_key or "blackrock_events"
        self._events = read_event_file(file_path)
        super().__init__(file_path=file_path, verbose=verbose)
        if not self.get_event_type_source_ids():
            raise ValueError(f"'{self._events.file_path.name}' holds no event packets.")

    def get_metadata(self) -> DeepDict:
        """Get the metadata, with the session start time from the file's time origin.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        if self._events.time_origin is not None:
            metadata["NWBFile"]["session_start_time"] = self._events.time_origin.isoformat()
        if self._events.comment:
            metadata["NWBFile"]["session_description"] = self._events.comment

        for event_type_source_id in self.get_event_type_source_ids():
            columns = {
                field_source_id: {
                    "column_name": _COLUMN_NAMES.get((event_type_source_id, field_source_id), field_source_id),
                    "description": description,
                }
                for field_source_id, description in _EVENT_TYPE_COLUMNS[event_type_source_id].items()
            }
            metadata["Events"][self.metadata_key]["event_types"][event_type_source_id] = {
                "event_name": event_type_source_id,
                "columns": columns,
            }
        return metadata

    def _get_events_data_dict(self) -> dict[str, _EventsData]:
        """Build one entry per kind of event packet the file holds, cached after the first call."""
        if self._events_data_dict is not None:
            return self._events_data_dict

        events = self._events
        resolution = events.timestamp_resolution

        def seconds(timestamps) -> np.ndarray:
            return np.asarray(timestamps, dtype="float64") / resolution

        payloads = {}
        if len(events.digital_events) > 0:
            payloads["digital_input"] = (
                events.digital_events["timestamp"],
                dict(
                    value=events.digital_events["value"],
                    insertion_reason=events.digital_events["insertion_reason"],
                ),
            )
        if events.comments:
            payloads["comments"] = (
                [comment["timestamp"] for comment in events.comments],
                dict(
                    text=np.array([comment["text"] for comment in events.comments]),
                    start_offset=np.array(
                        [
                            (
                                np.nan
                                if comment["start_timestamp"] is None
                                else (comment["timestamp"] - comment["start_timestamp"]) / resolution
                            )
                            for comment in events.comments
                        ]
                    ),
                ),
            )
        if events.recording_events:
            payloads["recording_events"] = (
                [event["timestamp"] for event in events.recording_events],
                dict(reason=np.array([event["reason"] for event in events.recording_events])),
            )
        if len(events.button_trigger_events) > 0:
            payloads["button_triggers"] = (
                events.button_trigger_events["timestamp"],
                dict(trigger_type=np.asarray(events.button_trigger_events["trigger_type"])),
            )
        if len(events.video_sync_events) > 0:
            payloads["video_sync"] = (
                events.video_sync_events["timestamp"],
                {
                    field_source_id: np.asarray(events.video_sync_events[field_source_id])
                    for field_source_id in _EVENT_TYPE_COLUMNS["video_sync"]
                },
            )
        if events.log_events:
            payloads["log_events"] = (
                [event["timestamp"] for event in events.log_events],
                {
                    field_source_id: np.array([event[field_source_id] for event in events.log_events])
                    for field_source_id in _EVENT_TYPE_COLUMNS["log_events"]
                },
            )
        if events.configuration_events:
            payloads["configuration_changes"] = (
                [event["timestamp"] for event in events.configuration_events],
                {
                    field_source_id: np.array([event[field_source_id] for event in events.configuration_events])
                    for field_source_id in _EVENT_TYPE_COLUMNS["configuration_changes"]
                },
            )

        self._events_data_dict = {
            event_type_source_id: _EventsData(
                event_type_source_id=event_type_source_id, timestamps=seconds(timestamps), payload=payload
            )
            for event_type_source_id, (timestamps, payload) in payloads.items()
        }
        return self._events_data_dict
