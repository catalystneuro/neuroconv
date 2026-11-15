"""Read the events of Blackrock event files (`.nev`).

The layouts follow the Blackrock file specification documents LB-0110 revision 7.0 (file spec 3.0) and LB-0023
revision 7.00, with the 2.x layouts as implemented by python-neo's `BlackrockRawIO`. Spec 2.0 event files share the
spec 2.1 layout.

An event file is a basic header, extended headers, and fixed-size packets. A packet starts with a timestamp and a
packet identifier. Identifiers from 1 to 0x7FFF are spike packets of that electrode and are not read here. The rest
are events: 0 is the digital input port, and the identifiers from 0xFFF9 up are comments, video sync, button
triggers, log entries, configuration changes and recording events.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_PTP_TIMESTAMP_RESOLUTION = 1_000_000_000

_NEV_BASIC_HEADER = np.dtype(
    [
        ("file_id", "S8"),
        ("ver_major", "u1"),
        ("ver_minor", "u1"),
        ("additional_flags", "<u2"),
        ("bytes_in_headers", "<u4"),
        ("bytes_in_data_packets", "<u4"),
        ("timestamp_resolution", "<u4"),
        ("sample_resolution", "<u4"),
        ("year", "<u2"),
        ("month", "<u2"),
        ("weekday", "<u2"),
        ("day", "<u2"),
        ("hour", "<u2"),
        ("minute", "<u2"),
        ("second", "<u2"),
        ("millisecond", "<u2"),
        ("application", "S32"),
        ("comment", "S256"),
        ("extended_header_count", "<u4"),
    ]
)

_DIGITAL_PACKET_ID = 0
_COMMENT_PACKET_ID = 0xFFFF
_VIDEO_SYNC_PACKET_ID = 0xFFFE
_BUTTON_TRIGGER_PACKET_ID = 0xFFFC
_LOG_PACKET_ID = 0xFFFB
_CONFIGURATION_PACKET_ID = 0xFFFA
_RECORDING_EVENT_PACKET_ID = 0xFFF9

_RECORDING_EVENT_REASONS = {0: "start", 1: "stop", 2: "pause", 3: "resume"}


@dataclass
class _NEVEvents:
    file_path: Path
    spec: str
    timestamp_resolution: int
    """Ticks per second of every timestamp in the file: 30,000, or 1,000,000,000 for PTP (Precision Time
    Protocol) files."""
    time_origin: datetime | None
    application: str
    comment: str
    digital_events: np.ndarray
    """Structured: `timestamp`, `insertion_reason` and `value`, the 16-bit word of the digital input port."""
    comments: list[dict]
    video_sync_events: np.ndarray
    button_trigger_events: np.ndarray
    log_events: list[dict]
    configuration_events: list[dict]
    recording_events: list[dict]

    @property
    def is_ptp(self) -> bool:
        return self.timestamp_resolution == _PTP_TIMESTAMP_RESOLUTION


def _decode_bytes(value: bytes) -> str:
    return value.split(b"\x00", 1)[0].decode("latin-1").strip()


def _read_time_origin(header: np.void) -> datetime | None:
    """The time origin is a Windows SYSTEMTIME, in UTC since spec 2.3 (LB-0110, table 4-1)."""
    if header["year"] == 0:
        return None
    return datetime(
        year=int(header["year"]),
        month=int(header["month"]),
        day=int(header["day"]),
        hour=int(header["hour"]),
        minute=int(header["minute"]),
        second=int(header["second"]),
        microsecond=int(header["millisecond"]) * 1000,
        tzinfo=timezone.utc,
    )


def read_event_file(file_path: str | Path) -> _NEVEvents:
    """Read the headers and every event packet of a Blackrock event file."""
    file_path = Path(file_path)
    file_size = file_path.stat().st_size
    if file_size < _NEV_BASIC_HEADER.itemsize:
        raise ValueError(
            f"'{file_path.name}' is {file_size} bytes long, shorter than the {_NEV_BASIC_HEADER.itemsize}-byte "
            "basic header of a Blackrock event file."
        )
    basic_header = np.fromfile(file_path, dtype=_NEV_BASIC_HEADER, count=1)[0]
    if basic_header["file_id"] not in (b"NEURALEV", b"BREVENTS"):
        raise ValueError(f"'{file_path.name}' does not start with a Blackrock event file identifier.")
    spec = f"{basic_header['ver_major']}.{basic_header['ver_minor']}"
    bytes_in_headers = int(basic_header["bytes_in_headers"])
    packet_size = int(basic_header["bytes_in_data_packets"])
    timestamp_resolution = int(basic_header["timestamp_resolution"])

    timestamp_type = "<u8" if spec == "3.0" else "<u4"
    timestamp_size = np.dtype(timestamp_type).itemsize
    packet_count = max(file_size - bytes_in_headers, 0) // packet_size
    common_dtype = np.dtype(
        [("timestamp", timestamp_type), ("packet_id", "<u2"), ("body", f"V{packet_size - timestamp_size - 2}")]
    )
    if packet_count == 0:
        packets = np.zeros(0, dtype=common_dtype)
    else:
        packets = np.memmap(file_path, dtype=common_dtype, mode="r", offset=bytes_in_headers, shape=(packet_count,))

    packet_ids = np.asarray(packets["packet_id"])
    # A packet whose timestamp is all ones continues the previous packet's payload (LB-0110, section 4.3).
    is_continuation = np.asarray(packets["timestamp"]) == np.iinfo(timestamp_type).max

    def body_view(packet_id: int, fields: list) -> np.ndarray:
        used_size = np.dtype(fields).itemsize
        remainder = packet_size - timestamp_size - 2 - used_size
        dtype = np.dtype(
            [("timestamp", timestamp_type), ("packet_id", "<u2"), *fields]
            + ([("unused", f"V{remainder}")] if remainder > 0 else [])
        )
        return np.asarray(packets[(packet_ids == packet_id) & ~is_continuation]).view(dtype)

    digital_packets = body_view(_DIGITAL_PACKET_ID, [("insertion_reason", "u1"), ("reserved", "u1"), ("value", "<u2")])
    digital_events = np.zeros(
        len(digital_packets), dtype=[("timestamp", "<u8"), ("insertion_reason", "u1"), ("value", "<u2")]
    )
    for name in digital_events.dtype.names:
        digital_events[name] = digital_packets[name]

    comment_packets = body_view(
        _COMMENT_PACKET_ID,
        [("char_set", "u1"), ("flag", "u1"), ("data", "<u4"), ("text", f"S{packet_size - timestamp_size - 2 - 6}")],
    )
    is_ptp = timestamp_resolution == _PTP_TIMESTAMP_RESOLUTION
    comments = [_decode_comment(packet, is_ptp=is_ptp) for packet in comment_packets]

    video_sync_events = body_view(
        _VIDEO_SYNC_PACKET_ID,
        [("file_number", "<u2"), ("frame_number", "<u4"), ("elapsed_time", "<u4"), ("source_id", "<u4")],
    )
    button_trigger_events = body_view(_BUTTON_TRIGGER_PACKET_ID, [("trigger_type", "<u2")])
    log_packets = body_view(
        _LOG_PACKET_ID,
        [("mode", "<u2"), ("application", "S16"), ("text", f"S{packet_size - timestamp_size - 2 - 18}")],
    )
    log_events = [
        dict(
            timestamp=int(packet["timestamp"]),
            mode=int(packet["mode"]),
            application=_decode_bytes(packet["application"]),
            text=_decode_bytes(packet["text"]),
        )
        for packet in log_packets
    ]
    configuration_packets = body_view(
        _CONFIGURATION_PACKET_ID, [("change_type", "<u2"), ("text", f"S{packet_size - timestamp_size - 4}")]
    )
    configuration_events = [
        dict(
            timestamp=int(packet["timestamp"]),
            change_type=int(packet["change_type"]),
            text=_decode_bytes(packet["text"]),
        )
        for packet in configuration_packets
    ]
    recording_packets = body_view(_RECORDING_EVENT_PACKET_ID, [("reason", "<u2")])
    recording_events = [
        dict(
            timestamp=int(packet["timestamp"]),
            reason=_RECORDING_EVENT_REASONS.get(int(packet["reason"]), f"unknown ({int(packet['reason'])})"),
        )
        for packet in recording_packets
    ]

    return _NEVEvents(
        file_path=file_path,
        spec=spec,
        timestamp_resolution=timestamp_resolution,
        time_origin=_read_time_origin(basic_header),
        application=_decode_bytes(basic_header["application"]),
        comment=_decode_bytes(basic_header["comment"]),
        digital_events=digital_events,
        comments=comments,
        video_sync_events=video_sync_events,
        button_trigger_events=button_trigger_events,
        log_events=log_events,
        configuration_events=configuration_events,
        recording_events=recording_events,
    )


def _decode_comment(packet: np.void, is_ptp: bool) -> dict:
    """Decode a comment packet (0xFFFF).

    With flag 1 the data field is the time the comment was started: a timestamp on the 30 kHz clock, and the
    microseconds from the start back to the packet on the PTP clock. Character set 255 marks a NeuroMotive
    region-of-interest crossing, whose data field is not a time.
    """
    char_set = int(packet["char_set"])
    raw_text = bytes(packet["text"])
    if char_set == 1:
        text = raw_text.decode("utf-16-le", errors="replace").split("\x00", 1)[0]
    else:
        text = raw_text.split(b"\x00", 1)[0].decode("latin-1")
    timestamp = int(packet["timestamp"])
    flag = int(packet["flag"])
    data = int(packet["data"])
    start_timestamp = None
    if flag == 1 and char_set != 255:
        start_timestamp = timestamp - data * 1000 if is_ptp else data
    return dict(
        timestamp=timestamp,
        char_set=char_set,
        flag=flag,
        data=data,
        text=text,
        start_timestamp=start_timestamp,
    )
