"""Read the tags of Axon Binary Format (ABF) files.

Tags are the only events an ABF file holds: timestamped markers written during acquisition, each with a time
(`lTagTime`), a comment and a type (`nTagType`). ABF1 keeps the Tag section at a fixed header pointer and ABF2
locates it through the section map; both use the same 64-byte entry (`ABFTag` in the vendor's `ABFHEADR.H`).

`lTagTime` counts `fSynchTimeUnit` microseconds, or samples of the interleaved data (all channels) when
`fSynchTimeUnit` is 0. The start of each sweep in the synch array uses the same clock, so a tag is placed in a
sweep by comparing the two directly.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zlib import crc32

import numpy as np

_BLOCK_SIZE = 512

_TAG_ENTRY = np.dtype([("time", "<i4"), ("comment", "S56"), ("type", "<i2"), ("voice_tag_or_annotation_index", "<i2")])

_STRING_TABLE_HEADER = np.dtype(
    [
        ("signature", "S4"),
        ("version", "<u4"),
        ("string_count", "<u4"),
        ("longest_string", "<u4"),
        ("text_bytes", "<u4"),
        ("reserved", "S24"),
    ]
)

_SYNCH_ENTRY = np.dtype([("start", "<i4"), ("length", "<i4")])

_VOICE_ENTRY = np.dtype(
    [
        ("tag_number", "<i4"),
        ("file_offset", "<i4"),
        ("uncompressed_size", "<i4"),
        ("compressed_size", "<i4"),
        ("compression", "<i2"),
        ("sample_bytes", "<i2"),
        ("rate", "<i4"),
        ("crc", "<u4"),
        ("channels", "<u2"),
        ("unused", "<u2"),
    ]
)

_TAG_TYPE_NAMES = {
    0: "time",
    1: "comment",
    2: "external",
    3: "voice",
    4: "new_file",
    5: "annotation",
}
"""The `ABF_*TAG` constants of `ABFHEADR.H`."""

_ANNOTATION_TAG_TYPE = 5

_ABF2_SECTION_NAMES = [
    "ProtocolSection",
    "ADCSection",
    "DACSection",
    "EpochSection",
    "ADCPerDACSection",
    "EpochPerDACSection",
    "UserListSection",
    "StatsRegionSection",
    "MathSection",
    "StringsSection",
    "DataSection",
    "TagSection",
    "ScopeSection",
    "DeltaSection",
    "VoiceTagSection",
    "SynchArraySection",
    "AnnotationSection",
    "StatsSection",
]
_ABF2_SECTION_MAP_OFFSET = 76
_ABF2_SECTION = np.dtype([("block_index", "<u4"), ("bytes", "<u4"), ("entry_count", "<i8")])

_ABF2_PROTOCOL_START = np.dtype(
    [
        ("operation_mode", "<i2"),
        ("adc_sequence_interval", "<f4"),
        ("enable_file_compression", "i1"),
        ("unused", "S3"),
        ("file_compression_ratio", "<u4"),
        ("synch_time_unit", "<f4"),
    ]
)

_ABF1_FIELDS = {
    "operation_mode": (8, "<i2"),
    "data_sample_count": (10, "<i4"),
    "start_date": (20, "<i4"),
    "start_seconds": (24, "<i4"),
    "tag_section_pointer": (44, "<i4"),
    "tag_count": (48, "<i4"),
    "voice_pointer": (80, "<i4"),
    "voice_count": (84, "<i4"),
    "synch_array_pointer": (92, "<i4"),
    "synch_array_size": (96, "<i4"),
    "annotation_pointer": (108, "<i4"),
    "annotation_count": (112, "<i4"),
    "channel_count": (120, "<i2"),
    "adc_sample_interval": (122, "<f4"),
    "synch_time_unit": (130, "<f4"),
    "start_milliseconds": (366, "<i2"),
}


@dataclass
class _VoiceTag:
    samples: np.ndarray
    sampling_frequency: float
    bits_per_sample: int


@dataclass
class _ABFTags:
    file_path: Path
    version: float
    operation_mode: int
    channel_count: int
    sampling_frequency: float
    """Samples per second of each channel."""
    seconds_per_tag_count: float
    session_start_time: datetime | None
    voice_tags: dict[int, _VoiceTag]
    tags: np.ndarray
    """Structured, one row per tag in file order: `time` (the raw `lTagTime`), `time_in_seconds`, `type`,
    `type_name`, `comment`, `voice_tag_or_annotation_index`, `annotation` (the text an annotation tag points
    to) and `sweep_index` (-1 for a tag outside the recorded sweeps)."""
    sweep_starts_in_seconds: np.ndarray
    sweep_durations_in_seconds: np.ndarray


def read_abf_tags(file_path: str | Path) -> _ABFTags:
    file_path = Path(file_path)
    with open(file_path, "rb") as file:
        signature = file.read(4)
    if signature == b"ABF ":
        header = _read_abf1_header(file_path)
    elif signature == b"ABF2":
        header = _read_abf2_header(file_path)
    else:
        raise ValueError(f"'{file_path.name}' does not start with an ABF signature.")

    channel_count = header["channel_count"]
    sampling_frequency = header["sampling_frequency"]
    synch_time_unit = header["synch_time_unit"]
    if synch_time_unit == 0:
        seconds_per_tag_count = 1.0 / (sampling_frequency * channel_count)
    else:
        seconds_per_tag_count = synch_time_unit * 1e-6

    raw_tags = _read_entries(file_path, _TAG_ENTRY, header["tag_offset"], header["tag_count"])
    synch_entries = _read_entries(file_path, _SYNCH_ENTRY, header["synch_offset"], header["synch_count"])

    if len(synch_entries) == 0:
        data_sample_count = header["data_sample_count"]
        sweep_starts = np.zeros(1, dtype="int64")
        sweep_durations = np.array([data_sample_count / channel_count / sampling_frequency])
    else:
        sweep_starts = synch_entries["start"].astype("int64")
        # `lLength` counts samples of the interleaved data ("in multiplexed samples", ABFHEADR.H struct ABFSynch).
        sweep_durations = synch_entries["length"] // channel_count / sampling_frequency
    sweep_starts_in_seconds = sweep_starts * seconds_per_tag_count

    tags = np.zeros(
        len(raw_tags),
        dtype=[
            ("time", "<i8"),
            ("time_in_seconds", "<f8"),
            ("type", "<i2"),
            ("type_name", object),
            ("comment", object),
            ("voice_tag_or_annotation_index", "<i2"),
            ("annotation", object),
            ("sweep_index", "<i8"),
        ],
    )
    tags["time"] = raw_tags["time"]
    tags["time_in_seconds"] = raw_tags["time"] * seconds_per_tag_count
    tags["type"] = raw_tags["type"]
    tags["voice_tag_or_annotation_index"] = raw_tags["voice_tag_or_annotation_index"]
    annotations = []
    if np.any(raw_tags["type"] == _ANNOTATION_TAG_TYPE):
        annotations = _read_annotations(file_path, header["annotation_offset"], header["annotation_count"])
    voice_tags = {}
    for index, raw_tag in enumerate(raw_tags):
        tag_type = int(raw_tag["type"])
        tags[index]["type_name"] = _TAG_TYPE_NAMES.get(tag_type, f"unknown_tag_{tag_type}")
        tags[index]["comment"] = raw_tag["comment"].split(b"\x00", 1)[0].decode("latin-1").rstrip(" ")
        reference = int(raw_tag["voice_tag_or_annotation_index"])
        tags[index]["annotation"] = ""
        if tag_type == _ANNOTATION_TAG_TYPE:
            if not 0 <= reference < len(annotations):
                raise ValueError(f"Tag {index} in '{file_path.name}' references missing annotation {reference}.")
            tags[index]["annotation"] = annotations[reference]
        elif tag_type == 3 and reference not in voice_tags:
            if not 0 <= reference < header["voice_count"]:
                raise ValueError(f"Tag {index} in '{file_path.name}' references missing voice tag {reference}.")
            voice_tags[reference] = _read_voice_tag(file_path, header["voice_offset"], reference)
    sweep_stops_in_seconds = sweep_starts_in_seconds + sweep_durations
    tags["sweep_index"] = [
        _find_sweep(time, sweep_starts_in_seconds, sweep_stops_in_seconds) for time in tags["time_in_seconds"]
    ]

    return _ABFTags(
        file_path=file_path,
        version=header["version"],
        operation_mode=header["operation_mode"],
        channel_count=channel_count,
        sampling_frequency=sampling_frequency,
        seconds_per_tag_count=seconds_per_tag_count,
        session_start_time=_session_start_time(header["start_date"], header["start_milliseconds"]),
        voice_tags=voice_tags,
        tags=tags,
        sweep_starts_in_seconds=sweep_starts_in_seconds,
        sweep_durations_in_seconds=np.asarray(sweep_durations, dtype="float64"),
    )


def _find_sweep(time: float, starts: np.ndarray, stops: np.ndarray) -> int:
    inside = np.flatnonzero((starts <= time) & (time < stops))
    return int(inside[0]) if len(inside) else -1


def _session_start_time(date: int, milliseconds: int) -> datetime | None:
    if date in (0, -1, 0xFFFFFFFF) or not 0 <= milliseconds < 86_400_000:
        return None
    year, month_day = divmod(date, 10000)
    month, day = divmod(month_day, 100)
    if year < 100:  # ABFU_FixFileStartDate uses 1980 as the century pivot.
        year += 2000 if year < 80 else 1900
    try:
        return datetime(year, month, day) + timedelta(milliseconds=milliseconds)
    except ValueError:
        return None


def _read_entries(file_path: Path, dtype: np.dtype, offset: int, count: int) -> np.ndarray:
    if count <= 0:
        return np.zeros(0, dtype=dtype)
    with open(file_path, "rb") as file:
        file.seek(offset)
        buffer = file.read(dtype.itemsize * count)
    if len(buffer) < dtype.itemsize * count:
        raise ValueError(
            f"'{file_path.name}' ends at byte {offset + len(buffer)}, before the {count} entries at byte {offset} "
            "its header declares."
        )
    return np.frombuffer(buffer, dtype=dtype, count=count)


def _read_abf1_header(file_path: Path) -> dict:
    with open(file_path, "rb") as file:
        raw_header = file.read(2048)
    fields = {
        name: np.frombuffer(raw_header, dtype=field_type, count=1, offset=offset)[0].item()
        for name, (offset, field_type) in _ABF1_FIELDS.items()
    }
    version = float(np.frombuffer(raw_header, dtype="<f4", count=1, offset=4)[0])
    channel_count = int(fields["channel_count"])
    return dict(
        version=round(version, 2),
        operation_mode=int(fields["operation_mode"]),
        channel_count=channel_count,
        start_date=fields["start_date"],
        start_milliseconds=fields["start_seconds"] * 1000 + fields["start_milliseconds"],
        sampling_frequency=1e6 / (fields["adc_sample_interval"] * channel_count),
        synch_time_unit=float(fields["synch_time_unit"]),
        tag_offset=fields["tag_section_pointer"] * _BLOCK_SIZE,
        tag_count=int(fields["tag_count"]),
        synch_offset=fields["synch_array_pointer"] * _BLOCK_SIZE,
        synch_count=int(fields["synch_array_size"]),
        data_sample_count=fields["data_sample_count"],
        annotation_offset=fields["annotation_pointer"] * _BLOCK_SIZE,
        annotation_count=fields["annotation_count"],
        voice_offset=fields["voice_pointer"] * _BLOCK_SIZE,
        voice_count=fields["voice_count"],
    )


def _read_abf2_header(file_path: Path) -> dict:
    with open(file_path, "rb") as file:
        raw_header = file.read(_ABF2_SECTION_MAP_OFFSET + _ABF2_SECTION.itemsize * len(_ABF2_SECTION_NAMES))
    version_bytes = np.frombuffer(raw_header, dtype="i1", count=4, offset=4)
    version = float(f"{version_bytes[3]}.{version_bytes[2]}{version_bytes[1]}{version_bytes[0]}")
    section_entries = np.frombuffer(
        raw_header, dtype=_ABF2_SECTION, count=len(_ABF2_SECTION_NAMES), offset=_ABF2_SECTION_MAP_OFFSET
    )
    sections = dict(zip(_ABF2_SECTION_NAMES, section_entries))
    protocol = _read_entries(
        file_path, _ABF2_PROTOCOL_START, int(sections["ProtocolSection"]["block_index"]) * _BLOCK_SIZE, 1
    )[0]
    data_section = sections["DataSection"]
    start_date, start_milliseconds = np.frombuffer(raw_header, dtype="<u4", count=2, offset=16).tolist()
    return dict(
        version=version,
        operation_mode=int(protocol["operation_mode"]),
        channel_count=int(sections["ADCSection"]["entry_count"]),
        start_date=start_date,
        start_milliseconds=start_milliseconds,
        sampling_frequency=1e6 / float(protocol["adc_sequence_interval"]),
        synch_time_unit=float(protocol["synch_time_unit"]),
        tag_offset=int(sections["TagSection"]["block_index"]) * _BLOCK_SIZE,
        tag_count=int(sections["TagSection"]["entry_count"]),
        synch_offset=int(sections["SynchArraySection"]["block_index"]) * _BLOCK_SIZE,
        synch_count=int(sections["SynchArraySection"]["entry_count"]),
        data_sample_count=int(data_section["entry_count"]),
        annotation_offset=int(sections["AnnotationSection"]["block_index"]) * _BLOCK_SIZE,
        annotation_count=int(sections["AnnotationSection"]["entry_count"]),
        voice_offset=int(sections["VoiceTagSection"]["block_index"]) * _BLOCK_SIZE,
        voice_count=int(sections["VoiceTagSection"]["entry_count"]),
    )


def _read_annotations(file_path: Path, offset: int, count: int) -> list[str]:
    """Read the null-terminated annotation string table shared by both file versions."""
    if count == 0 or offset == 0:
        return []
    table_header = _read_entries(file_path, _STRING_TABLE_HEADER, offset, 1)[0]
    if table_header["signature"] != b"SSCH":
        raise ValueError(f"The annotation section of '{file_path.name}' does not start with 'SSCH'.")
    data = _read_entries(
        file_path, np.dtype("u1"), offset + _STRING_TABLE_HEADER.itemsize, int(table_header["text_bytes"])
    )
    strings = data.tobytes().split(b"\x00")
    string_count = int(table_header["string_count"])
    if len(strings) <= string_count:
        raise ValueError(f"Incomplete annotation string table in '{file_path.name}'.")
    return [string.decode("latin-1") for string in strings[:string_count]]


def _read_voice_tag(file_path: Path, catalog_offset: int, number: int) -> _VoiceTag:
    info = _read_entries(file_path, _VOICE_ENTRY, catalog_offset + number * _VOICE_ENTRY.itemsize, 1)[0]
    audio = _read_entries(file_path, np.dtype("u1"), int(info["file_offset"]), int(info["compressed_size"])).tobytes()
    compression = int(info["compression"])
    if compression == 1:
        from dclimplode import decompressobj

        decoder = decompressobj()
        audio = decoder.decompress(audio)
        if not decoder.eof:
            raise ValueError(f"Incomplete compressed audio for voice tag {number} in '{file_path.name}'.")
    elif compression != 0:
        raise ValueError(f"Unsupported compression {compression} for voice tag {number} in '{file_path.name}'.")
    if len(audio) != info["uncompressed_size"] or (info["crc"] and crc32(audio) != info["crc"]):
        raise ValueError(f"Audio size or checksum mismatch for voice tag {number} in '{file_path.name}'.")
    sample_bytes = int(info["sample_bytes"])
    if sample_bytes == 3:
        # NumPy has no signed 24-bit dtype. Sign-extend the high byte into the fourth byte.
        octets = np.frombuffer(audio, dtype="u1").reshape(-1, 3).astype("i4")
        samples = ((octets[:, 2] << 24) >> 8) | (octets[:, 1] << 8) | octets[:, 0]
    elif sample_bytes in (1, 2, 4):
        dtype = "u1" if sample_bytes == 1 else f"<i{sample_bytes}"
        samples = np.frombuffer(audio, dtype=dtype)
    else:
        raise ValueError(f"Unsupported {sample_bytes}-byte samples for voice tag {number} in '{file_path.name}'.")
    return _VoiceTag(
        samples=samples.reshape(-1, int(info["channels"])),
        sampling_frequency=float(info["rate"]),
        bits_per_sample=8 * sample_bytes,
    )
