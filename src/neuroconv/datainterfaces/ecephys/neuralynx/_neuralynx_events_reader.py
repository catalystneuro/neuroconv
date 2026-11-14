"""Read Neuralynx event files (`.nev`).

An event file is a 16 KiB text header (some Pegasus files leave out its `########` first line) followed by fixed 184-byte event records (Neuralynx Data File Formats,
revision 1.1, 2013, page 2). Each record carries a microsecond timestamp, an event id naming the source of the
event, the value of the TTL port and a text string. The TTL value is the whole 16-bit port word, written when
any line of the port changes, so the reader keeps it as one value and does not split it by line or by value.

Which port a TTL record belongs to appears only in the text Cheetah writes for it, so the reader also decodes
that text for the writers seen in the test data.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

_HEADER_SIZE = 2**14

_EVENT_RECORD = np.dtype(
    [
        ("reserved", "<i2"),
        ("system_id", "<i2"),
        ("data_size", "<i2"),
        ("timestamp", "<u8"),
        ("event_id", "<i2"),
        ("ttl_value", "<u2"),
        ("crc", "<i2"),
        ("dummy_1", "<i2"),
        ("dummy_2", "<i2"),
        ("extra", "<i4", (8,)),
        ("event_string", "S128"),
    ]
)
"""The manual types the TTL value as Int16. It is read as unsigned here because it is a 16-bit port word: a
port with its highest line set is 0x8000 and above, which Int16 turns negative."""

_TTL_STRING_PATTERNS = [
    # Cheetah 5.5 and later, Pegasus: "TTL Input on AcqSystem1_0 board 0 port 3 value (0x0004)."
    re.compile(
        r"TTL (?P<direction>Input|Output) on (?P<device>\S+) board (?P<board>\d+) port (?P<port>\d+) "
        r"value \((?P<value>0x[0-9A-Fa-f]+)\)"
    ),
    # Cheetah 4: "RecID: 4098 Port: 0 TTL Value: 0x0001"
    re.compile(r"RecID: (?P<device>\d+) Port: (?P<port>\d+) TTL Value: (?P<value>0x[0-9A-Fa-f]+)"),
    # Cheetah 5.4 on Cheetah64 hardware: "Cheetah 32 DIO board 0 input TTL (0x0002)"
    re.compile(
        r"(?P<device>Cheetah \d+ DIO) board (?P<board>\d+) (?P<direction>input|output) TTL \((?P<value>0x[0-9A-Fa-f]+)\)"
    ),
    # Cheetah 5.2: "Digital Lynx Parallel Input Port TTL (0x0001)"
    re.compile(r"(?P<device>Digital Lynx Parallel) (?P<direction>Input|Output) Port TTL \((?P<value>0x[0-9A-Fa-f]+)\)"),
]

_OPENED_PATTERNS = [
    re.compile(
        r"## (?:Time|Date) Opened:* \((?:m/d/y|mm/dd/yyy)\): (?P<date>\S+)\s+(?:\(h:m:s\.ms\)|At Time:) (?P<time>\S+)"
    ),
    re.compile(r"-TimeCreated (?P<date>\S+) (?P<time>\S+)"),
]
_CLOSED_PATTERNS = [
    re.compile(
        r"## (?:Time|Date) Closed:* \((?:m/d/y|mm/dd/yyy)\): (?P<date>\S+)\s+(?:\(h:m:s\.ms\)|At Time:) (?P<time>\S+)"
    ),
    re.compile(r"-TimeClosed (?P<date>\S+) (?P<time>\S+)"),
]
_NOT_CLOSED_TEXT = "File was not closed properly"


@dataclass
class _NeuralynxEventFile:
    file_path: Path
    header_text: str
    properties: dict[str, str]
    """Every `-Key value` line of the header, values as written (quotes removed)."""
    time_opened: datetime | None
    time_closed: datetime | None
    closed_properly: bool
    """False when Cheetah wrote "File was not closed properly" in place of the closing time."""
    records: np.ndarray
    """Structured, one row per record in file order: `timestamp` (microseconds), `system_id`, `event_id`,
    `ttl_value` (the 16-bit port word), `extra`, `event_string`, and from the string of a TTL record
    `ttl_direction` ("input", "output" or ""), `device`, `board` and `port` (-1 when the string does not say)."""
    trailing_bytes: int


def read_event_file(file_path: str | Path) -> _NeuralynxEventFile:
    """Read the header and every record of a Neuralynx event file."""
    file_path = Path(file_path)
    file_size = file_path.stat().st_size
    if file_size < _HEADER_SIZE:
        raise ValueError(
            f"'{file_path.name}' is {file_size} bytes long, shorter than the {_HEADER_SIZE}-byte Neuralynx header."
        )
    with open(file_path, "rb") as file:
        header_text = file.read(_HEADER_SIZE).split(b"\x00", 1)[0].decode("latin-1")
    record_count = (file_size - _HEADER_SIZE) // _EVENT_RECORD.itemsize
    trailing_bytes = (file_size - _HEADER_SIZE) % _EVENT_RECORD.itemsize
    if record_count > 0:
        raw_records = np.fromfile(file_path, dtype=_EVENT_RECORD, count=record_count, offset=_HEADER_SIZE)
    else:
        raw_records = np.zeros(0, dtype=_EVENT_RECORD)

    return _NeuralynxEventFile(
        file_path=file_path,
        header_text=header_text,
        properties=_read_properties(header_text),
        time_opened=_read_header_time(header_text, _OPENED_PATTERNS),
        time_closed=_read_header_time(header_text, _CLOSED_PATTERNS),
        closed_properly=_NOT_CLOSED_TEXT not in header_text,
        records=_decode_records(raw_records),
        trailing_bytes=int(trailing_bytes),
    )


def _read_properties(header_text: str) -> dict[str, str]:
    properties = {}
    for line in header_text.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        parts = line[1:].split(maxsplit=1)
        key = parts[0]
        value = parts[1].strip().strip('"') if len(parts) > 1 else ""
        properties[key] = value
    return properties


def _read_header_time(header_text: str, patterns: list[re.Pattern]) -> datetime | None:
    for pattern in patterns:
        match = pattern.search(header_text)
        if match is not None:
            return _parse_header_datetime(date_text=match["date"], time_text=match["time"])
    return None


def _parse_header_datetime(date_text: str, time_text: str) -> datetime | None:
    """Dates are month/day/year in the `## Time Opened` lines and year/month/day in `-TimeCreated`, and the
    clock is hours:minutes:seconds with optional milliseconds, none of them zero padded."""
    date_parts = date_text.split("/")
    time_parts = time_text.split(":")
    if len(date_parts) != 3 or len(time_parts) != 3:
        return None
    if len(date_parts[0]) == 4:
        year, month, day = (int(part) for part in date_parts)
    else:
        month, day, year = (int(part) for part in date_parts)
        if year < 100:
            year += 2000
    seconds_text, _, fraction_text = time_parts[2].partition(".")
    microsecond = int(round(float(f"0.{fraction_text}") * 1_000_000)) if fraction_text else 0
    return datetime(
        year=year,
        month=month,
        day=day,
        hour=int(time_parts[0]),
        minute=int(time_parts[1]),
        second=int(seconds_text),
        microsecond=min(microsecond, 999_999),
    )


def _decode_records(raw_records: np.ndarray) -> np.ndarray:
    records = np.zeros(
        len(raw_records),
        dtype=[
            ("timestamp", "<u8"),
            ("system_id", "<i2"),
            ("event_id", "<i2"),
            ("ttl_value", "<u2"),
            ("extra", "<i4", (8,)),
            ("event_string", object),
            ("ttl_direction", object),
            ("device", object),
            ("board", "<i4"),
            ("port", "<i4"),
        ],
    )
    for name in ("timestamp", "system_id", "event_id", "ttl_value", "extra"):
        records[name] = raw_records[name]
    for index, raw_string in enumerate(raw_records["event_string"]):
        event_string = raw_string.split(b"\x00", 1)[0].decode("latin-1")
        source = _decode_ttl_string(event_string)
        records[index]["event_string"] = event_string
        records[index]["ttl_direction"] = source["direction"]
        records[index]["device"] = source["device"]
        records[index]["board"] = source["board"]
        records[index]["port"] = source["port"]
    return records


def _decode_ttl_string(event_string: str) -> dict:
    for pattern in _TTL_STRING_PATTERNS:
        match = pattern.search(event_string)
        if match is None:
            continue
        fields = match.groupdict()
        return dict(
            direction=fields.get("direction", "").lower(),
            device=fields.get("device", ""),
            board=int(fields["board"]) if fields.get("board") is not None else -1,
            port=int(fields["port"]) if fields.get("port") is not None else -1,
            value=int(fields["value"], 16),
        )
    return dict(direction="", device="", board=-1, port=-1, value=None)
