"""Read Blackrock event (`.nev`) and continuous (`.ns1` to `.ns6`) files.

The layouts follow the Blackrock file specification documents LB-0110 revision 7.0 (file spec 3.0) and LB-0023
revision 7.00, with the 2.x layouts as implemented by python-neo's `BlackrockRawIO`. Spec 2.0 event files share the
spec 2.1 layout.

Everything here reads headers and maps data; nothing loads samples or waveforms until asked.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_SAMPLE_CLOCK_FREQUENCY = 30_000
_PTP_TIMESTAMP_RESOLUTION = 1_000_000_000

_SYSTEMTIME_FIELDS = [
    ("year", "<u2"),
    ("month", "<u2"),
    ("weekday", "<u2"),
    ("day", "<u2"),
    ("hour", "<u2"),
    ("minute", "<u2"),
    ("second", "<u2"),
    ("millisecond", "<u2"),
]

_NSX_21_BASIC_HEADER = np.dtype([("file_id", "S8"), ("label", "S16"), ("period", "<u4"), ("channel_count", "<u4")])

_NSX_BASIC_HEADER = np.dtype(
    [
        ("file_id", "S8"),
        ("ver_major", "u1"),
        ("ver_minor", "u1"),
        ("bytes_in_headers", "<u4"),
        ("label", "S16"),
        ("comment", "S256"),
        ("period", "<u4"),
        ("timestamp_resolution", "<u4"),
        *_SYSTEMTIME_FIELDS,
        ("channel_count", "<u4"),
    ]
)

_NSX_EXTENDED_HEADER = np.dtype(
    [
        ("type", "S2"),
        ("electrode_id", "<u2"),
        ("electrode_label", "S16"),
        ("physical_connector", "u1"),
        ("connector_pin", "u1"),
        ("min_digital_value", "<i2"),
        ("max_digital_value", "<i2"),
        ("min_analog_value", "<i2"),
        ("max_analog_value", "<i2"),
        ("units", "S16"),
        ("high_frequency_corner", "<u4"),
        ("high_frequency_order", "<u4"),
        ("high_frequency_type", "<u2"),
        ("low_frequency_corner", "<u4"),
        ("low_frequency_order", "<u4"),
        ("low_frequency_type", "<u2"),
    ]
)

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
        *_SYSTEMTIME_FIELDS,
        ("application", "S32"),
        ("comment", "S256"),
        ("extended_header_count", "<u4"),
    ]
)

# Spec 2.1 and earlier have no spike width in NEUEVWAV; the field is part of the unused bytes there.
_NEV_EXTENDED_HEADERS = {
    b"NEUEVWAV": np.dtype(
        [
            ("packet_id", "S8"),
            ("electrode_id", "<u2"),
            ("physical_connector", "u1"),
            ("connector_pin", "u1"),
            ("digitization_factor", "<u2"),
            ("energy_threshold", "<u2"),
            ("high_threshold", "<i2"),
            ("low_threshold", "<i2"),
            ("sorted_unit_count", "u1"),
            ("bytes_per_waveform_sample", "u1"),
            ("spike_width", "<u2"),
            ("unused", "S8"),
        ]
    ),
    b"NEUEVLBL": np.dtype([("packet_id", "S8"), ("electrode_id", "<u2"), ("label", "S16"), ("unused", "S6")]),
    b"NEUEVFLT": np.dtype(
        [
            ("packet_id", "S8"),
            ("electrode_id", "<u2"),
            ("high_frequency_corner", "<u4"),
            ("high_frequency_order", "<u4"),
            ("high_frequency_type", "<u2"),
            ("low_frequency_corner", "<u4"),
            ("low_frequency_order", "<u4"),
            ("low_frequency_type", "<u2"),
            ("unused", "S2"),
        ]
    ),
    b"DIGLABEL": np.dtype([("packet_id", "S8"), ("label", "S16"), ("mode", "u1"), ("unused", "S7")]),
    b"VIDEOSYN": np.dtype(
        [
            ("packet_id", "S8"),
            ("video_source_id", "<u2"),
            ("video_source", "S16"),
            ("frame_rate", "<f4"),
            ("unused", "S2"),
        ]
    ),
    b"TRACKOBJ": np.dtype(
        [
            ("packet_id", "S8"),
            ("trackable_type", "<u2"),
            ("trackable_id", "<u2"),
            ("point_count", "<u2"),
            ("video_source", "S16"),
            ("unused", "S2"),
        ]
    ),
    b"ARRAYNME": np.dtype([("packet_id", "S8"), ("text", "S24")]),
    b"ECOMMENT": np.dtype([("packet_id", "S8"), ("text", "S24")]),
    b"CCOMMENT": np.dtype([("packet_id", "S8"), ("text", "S24")]),
    b"MAPFILE\x00": np.dtype([("packet_id", "S8"), ("text", "S24")]),
}

_DIGITAL_PACKET_ID = 0
_FIRST_SYSTEM_PACKET_ID = 0x8000
_COMMENT_PACKET_ID = 0xFFFF
_VIDEO_SYNC_PACKET_ID = 0xFFFE
_TRACKING_PACKET_ID = 0xFFFD
_BUTTON_TRIGGER_PACKET_ID = 0xFFFC
_LOG_PACKET_ID = 0xFFFB
_CONFIGURATION_PACKET_ID = 0xFFFA
_RECORDING_EVENT_PACKET_ID = 0xFFF9

_TRELLIS_LAST_RECORDING_ELECTRODE_ID = 5120

_RECORDING_EVENT_REASONS = {0: "start", 1: "stop", 2: "pause", 3: "resume"}

_UNITS_TO_MICROVOLTS = {"uV": 1.0, "µV": 1.0, "mV": 1_000.0, "V": 1_000_000.0}


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


def _read_struct(file_path: Path, dtype: np.dtype, offset: int, count: int = 1) -> np.ndarray:
    with open(file_path, "rb") as file:
        file.seek(offset)
        buffer = file.read(dtype.itemsize * count)
    if len(buffer) < dtype.itemsize * count:
        raise ValueError(
            f"'{file_path.name}' ends at byte {offset + len(buffer)}, inside a structure that runs to byte "
            f"{offset + dtype.itemsize * count}."
        )
    return np.frombuffer(buffer, dtype=dtype, count=count)


@dataclass
class _NSxDataBlock:
    """A run of samples spaced at the nominal sampling interval."""

    timestamp: int
    """Time of the first sample, in ticks of the file's timestamp resolution."""
    sample_count: int
    data_offset: int
    """Byte offset of the first sample."""


@dataclass
class _NSxFile:
    file_path: Path
    spec: str
    is_ptp: bool
    label: str
    comment: str
    period: int
    timestamp_resolution: int
    time_origin: datetime | None
    channel_ids: np.ndarray
    channel_labels: list[str]
    units: list[str]
    gains: np.ndarray | None
    """Analog units per digital count, per channel, in the units of `units`. `None` for spec 2.1 files,
    which keep the scaling in the event file."""
    offsets: np.ndarray | None
    extended_header: np.ndarray | None
    data_blocks: list[_NSxDataBlock]
    frame_size: int
    """Bytes from one sample to the next, all channels and, for PTP files, the per-sample header."""
    notes: list[str] = field(default_factory=list)
    """What the reader had to recover from: zero-filled tails, blocks declaring zero points, partial frames."""

    @property
    def sampling_frequency(self) -> float:
        return _SAMPLE_CLOCK_FREQUENCY / self.period

    @property
    def channel_count(self) -> int:
        return len(self.channel_ids)

    def get_samples(self, block_index: int) -> np.ndarray:
        """A read-only memory map of one block, shaped (samples, channels), in digital counts."""
        block = self.data_blocks[block_index]
        if self.is_ptp:
            packets = np.memmap(
                self.file_path,
                dtype=_ptp_packet_dtype(self.channel_count),
                mode="r",
                offset=block.data_offset,
                shape=(block.sample_count,),
            )
            return packets["samples"]
        return np.memmap(
            self.file_path,
            dtype="<i2",
            mode="r",
            offset=block.data_offset,
            shape=(block.sample_count, self.channel_count),
        )

    def get_ptp_timestamps(self) -> np.ndarray:
        """The nanosecond timestamp of every sample of a PTP file, in file order."""
        assert self.is_ptp, "Only PTP files have one timestamp per sample."
        block = self.data_blocks[0]
        packets = np.memmap(
            self.file_path,
            dtype=_ptp_packet_dtype(self.channel_count),
            mode="r",
            offset=block.data_offset,
            shape=(block.sample_count,),
        )
        return np.asarray(packets["timestamp"])


def _ptp_packet_dtype(channel_count: int) -> np.dtype:
    return np.dtype(
        [("header_flag", "u1"), ("timestamp", "<u8"), ("point_count", "<u4"), ("samples", "<i2", (channel_count,))]
    )


def _read_nsx_file_spec(file_path: Path) -> str:
    file_id = _read_struct(file_path, np.dtype([("file_id", "S8"), ("ver_major", "u1"), ("ver_minor", "u1")]), 0)[0]
    if file_id["file_id"] == b"NEURALSG":
        return "2.1"
    if file_id["file_id"] in (b"NEURALCD", b"BRSMPGRP"):
        return f"{file_id['ver_major']}.{file_id['ver_minor']}"
    raise ValueError(f"'{file_path.name}' does not start with a Blackrock continuous file identifier.")


def read_nsx(file_path: str | Path) -> _NSxFile:
    """Read the headers of a continuous file and locate its data blocks."""
    file_path = Path(file_path)
    file_size = file_path.stat().st_size
    spec = _read_nsx_file_spec(file_path)

    if spec == "2.1":
        basic_header = _read_struct(file_path, _NSX_21_BASIC_HEADER, 0)[0]
        channel_count = int(basic_header["channel_count"])
        channel_ids = _read_struct(file_path, np.dtype("<u4"), _NSX_21_BASIC_HEADER.itemsize, channel_count)
        bytes_in_headers = _NSX_21_BASIC_HEADER.itemsize + 4 * channel_count
        frame_size = 2 * channel_count
        sample_count = (file_size - bytes_in_headers) // frame_size
        nsx_file = _NSxFile(
            file_path=file_path,
            spec=spec,
            is_ptp=False,
            label=_decode_bytes(basic_header["label"]),
            comment="",
            period=int(basic_header["period"]),
            timestamp_resolution=_SAMPLE_CLOCK_FREQUENCY,
            time_origin=None,
            channel_ids=channel_ids.astype("int64"),
            channel_labels=[_spec_21_channel_label(int(channel_id)) for channel_id in channel_ids],
            units=["" for _ in channel_ids],
            gains=None,
            offsets=None,
            extended_header=None,
            data_blocks=[_NSxDataBlock(timestamp=0, sample_count=sample_count, data_offset=bytes_in_headers)],
            frame_size=frame_size,
        )
        trailing_bytes = (file_size - bytes_in_headers) % frame_size
        if trailing_bytes:
            nsx_file.notes.append(f"{trailing_bytes} bytes after the last whole sample were not read.")
        return nsx_file

    basic_header = _read_struct(file_path, _NSX_BASIC_HEADER, 0)[0]
    channel_count = int(basic_header["channel_count"])
    bytes_in_headers = int(basic_header["bytes_in_headers"])
    if file_size < bytes_in_headers:
        raise ValueError(
            f"'{file_path.name}' is {file_size} bytes long, shorter than the {bytes_in_headers} bytes its header "
            "declares, so it holds no data."
        )
    extended_header = _read_struct(file_path, _NSX_EXTENDED_HEADER, _NSX_BASIC_HEADER.itemsize, channel_count)

    analog_range = extended_header["max_analog_value"].astype("float64") - extended_header["min_analog_value"]
    digital_range = extended_header["max_digital_value"].astype("float64") - extended_header["min_digital_value"]
    gains = analog_range / digital_range
    offsets = extended_header["min_analog_value"] - gains * extended_header["min_digital_value"]

    timestamp_resolution = int(basic_header["timestamp_resolution"])
    nsx_file = _NSxFile(
        file_path=file_path,
        spec=spec,
        is_ptp=False,
        label=_decode_bytes(basic_header["label"]),
        comment=_decode_bytes(basic_header["comment"]),
        period=int(basic_header["period"]),
        timestamp_resolution=timestamp_resolution,
        time_origin=_read_time_origin(basic_header),
        channel_ids=extended_header["electrode_id"].astype("int64"),
        channel_labels=[_decode_bytes(label) for label in extended_header["electrode_label"]],
        units=[_decode_bytes(units) for units in extended_header["units"]],
        gains=gains,
        offsets=offsets,
        extended_header=extended_header,
        data_blocks=[],
        frame_size=2 * channel_count,
    )

    if spec == "3.0" and timestamp_resolution == _PTP_TIMESTAMP_RESOLUTION:
        packet_dtype = _ptp_packet_dtype(channel_count)
        first_packet = _read_struct(file_path, packet_dtype, bytes_in_headers)[0]
        if first_packet["point_count"] == 1:
            _locate_ptp_samples(nsx_file=nsx_file, file_size=file_size, bytes_in_headers=bytes_in_headers)
            return nsx_file

    _locate_data_blocks(nsx_file=nsx_file, file_size=file_size, bytes_in_headers=bytes_in_headers)
    return nsx_file


def _spec_21_channel_label(channel_id: int) -> str:
    """Spec 2.1 files carry no labels; these are the names Central gives (and python-neo uses)."""
    return f"chan{channel_id}" if channel_id < 129 else f"ainp{channel_id - 128}"


def _locate_ptp_samples(nsx_file: _NSxFile, file_size: int, bytes_in_headers: int) -> None:
    """A PTP file stores every sample as a packet of its own, with a header carrying its nanosecond timestamp."""
    packet_dtype = _ptp_packet_dtype(nsx_file.channel_count)
    packet_count = (file_size - bytes_in_headers) // packet_dtype.itemsize
    packets = np.memmap(
        nsx_file.file_path, dtype=packet_dtype, mode="r", offset=bytes_in_headers, shape=(packet_count,)
    )
    point_counts = np.asarray(packets["point_count"])
    if not np.all(point_counts == 1):
        first_bad_packet = int(np.flatnonzero(point_counts != 1)[0])
        raise ValueError(
            f"'{nsx_file.file_path.name}' is a PTP file, where every packet holds one sample, but packet "
            f"{first_bad_packet} declares {point_counts[first_bad_packet]}."
        )
    nsx_file.is_ptp = True
    nsx_file.frame_size = packet_dtype.itemsize
    nsx_file.data_blocks.append(
        _NSxDataBlock(timestamp=int(packets["timestamp"][0]), sample_count=packet_count, data_offset=bytes_in_headers)
    )
    trailing_bytes = (file_size - bytes_in_headers) % packet_dtype.itemsize
    if trailing_bytes:
        nsx_file.notes.append(f"{trailing_bytes} bytes after the last whole sample packet were not read.")


def _locate_data_blocks(nsx_file: _NSxFile, file_size: int, bytes_in_headers: int) -> None:
    """Walk the data block headers of a spec 2.2, 2.3 or 3.0 file.

    Recovers three states a file can be left in: a block that declares 0 points and runs to the end of the
    file (the count was never written back), a block that declares more samples than the file holds, and
    zero bytes after the last complete block.
    """
    timestamp_type = "<u8" if nsx_file.spec == "3.0" else "<u4"
    block_header_dtype = np.dtype([("header_flag", "u1"), ("timestamp", timestamp_type), ("point_count", "<u4")])
    frame_size = nsx_file.frame_size
    file_name = nsx_file.file_path.name

    offset = bytes_in_headers
    while offset < file_size:
        if file_size - offset < block_header_dtype.itemsize:
            nsx_file.notes.append(f"{file_size - offset} bytes after the last data block were not read.")
            break
        block_header = _read_struct(nsx_file.file_path, block_header_dtype, offset)[0]
        if block_header["header_flag"] != 1:
            if _is_zero_filled(nsx_file.file_path, offset, file_size):
                nsx_file.notes.append(
                    f"The {file_size - offset} bytes after data block {len(nsx_file.data_blocks) - 1} are all "
                    "zero and were not read."
                )
                break
            raise ValueError(
                f"'{file_name}' has no data block header at byte {offset}, where block "
                f"{len(nsx_file.data_blocks)} should start: the header flag is {block_header['header_flag']} "
                "instead of 1."
            )

        data_offset = offset + block_header_dtype.itemsize
        declared_sample_count = int(block_header["point_count"])
        available_sample_count = (file_size - data_offset) // frame_size
        sample_count = declared_sample_count

        next_offset = data_offset + declared_sample_count * frame_size
        if declared_sample_count == 0 and not _is_block_header_at(nsx_file.file_path, data_offset, file_size):
            sample_count = available_sample_count
            nsx_file.notes.append(
                f"Data block {len(nsx_file.data_blocks)} declares 0 points but data follows it; read "
                f"{sample_count} samples from the file size."
            )
            next_offset = file_size
        elif declared_sample_count > available_sample_count:
            sample_count = available_sample_count
            nsx_file.notes.append(
                f"Data block {len(nsx_file.data_blocks)} declares {declared_sample_count} samples but the file "
                f"holds {available_sample_count}."
            )
            next_offset = file_size

        nsx_file.data_blocks.append(
            _NSxDataBlock(timestamp=int(block_header["timestamp"]), sample_count=sample_count, data_offset=data_offset)
        )
        if next_offset == file_size:
            trailing_bytes = (file_size - data_offset) - sample_count * frame_size
            if trailing_bytes:
                nsx_file.notes.append(f"{trailing_bytes} bytes after the last whole sample were not read.")
        offset = next_offset


def _is_block_header_at(file_path: Path, offset: int, file_size: int) -> bool:
    if offset >= file_size:
        return True
    with open(file_path, "rb") as file:
        file.seek(offset)
        return file.read(1) == b"\x01"


def _is_zero_filled(file_path: Path, offset: int, file_size: int, chunk_size: int = 2**24) -> bool:
    with open(file_path, "rb") as file:
        file.seek(offset)
        while offset < file_size:
            chunk = file.read(min(chunk_size, file_size - offset))
            if np.frombuffer(chunk, dtype="u1").any():
                return False
            offset += len(chunk)
    return True


@dataclass
class _NEVFile:
    file_path: Path
    spec: str
    timestamp_resolution: int
    sample_resolution: int
    time_origin: datetime | None
    application: str
    comment: str
    packet_size: int
    waveforms_are_16_bit: bool
    extended_headers: dict[str, np.ndarray]
    spikes: np.ndarray
    """Structured: `timestamp`, `electrode_id`, `unit_class` and `packet_index`, in file order."""
    stimulation_events: np.ndarray
    """Stimulation waveform packets of Trellis files, on electrode ids from 5121 (the stimulating electrode
    plus 5120, per Ripple's Trellis NEV specification R01838_07). Structured: `timestamp`, `electrode_id` and
    `packet_index`."""
    digital_events: np.ndarray
    """Structured: `timestamp`, `insertion_reason` and `value`, the 16-bit word of the digital input port."""
    comments: list[dict]
    video_sync_events: np.ndarray
    tracking_events: np.ndarray
    button_trigger_events: np.ndarray
    log_events: list[dict]
    configuration_events: list[dict]
    recording_events: list[dict]
    other_packet_counts: dict[int, int]
    """Packets of identifiers the specification documents nowhere, such as Central's preview packets
    (0x8000 plus the channel) in spec 3.0 files."""
    continuation_packet_count: int
    trailing_bytes: int

    @property
    def is_ptp(self) -> bool:
        return self.timestamp_resolution == _PTP_TIMESTAMP_RESOLUTION

    @property
    def data_offset(self) -> int:
        return int(_read_struct(self.file_path, _NEV_BASIC_HEADER, 0)[0]["bytes_in_headers"])

    def get_spike_waveforms(self, packet_indices: np.ndarray) -> np.ndarray:
        """Raw waveform bytes of the given spike packets as int16 (or int8 when the header says so)."""
        timestamp_size = 8 if self.spec == "3.0" else 4
        waveform_offset = timestamp_size + 4
        packets = np.memmap(self.file_path, dtype=f"V{self.packet_size}", mode="r", offset=self.data_offset)
        raw = np.frombuffer(packets[packet_indices].tobytes(), dtype="u1").reshape(len(packet_indices), -1)
        waveform_bytes = raw[:, waveform_offset:]
        bytes_per_sample = 2 if self.waveforms_are_16_bit else self._get_bytes_per_waveform_sample(packet_indices)
        sample_dtype = "<i2" if bytes_per_sample == 2 else "i1"
        return np.ascontiguousarray(waveform_bytes).view(sample_dtype)

    def _get_bytes_per_waveform_sample(self, packet_indices: np.ndarray) -> int:
        waveform_headers = self.extended_headers["NEUEVWAV"]
        bytes_by_electrode = dict(zip(waveform_headers["electrode_id"], waveform_headers["bytes_per_waveform_sample"]))
        electrode_ids = self.spikes["electrode_id"][np.isin(self.spikes["packet_index"], packet_indices)]
        sample_sizes = {max(int(bytes_by_electrode.get(electrode_id, 1)), 1) for electrode_id in electrode_ids}
        assert len(sample_sizes) <= 1, "The requested spikes mix 8-bit and 16-bit waveforms."
        return sample_sizes.pop() if sample_sizes else 2


def read_nev(file_path: str | Path) -> _NEVFile:
    """Read the headers and every packet of an event file."""
    file_path = Path(file_path)
    file_size = file_path.stat().st_size
    basic_header = _read_struct(file_path, _NEV_BASIC_HEADER, 0)[0]
    if basic_header["file_id"] not in (b"NEURALEV", b"BREVENTS"):
        raise ValueError(f"'{file_path.name}' does not start with a Blackrock event file identifier.")
    spec = f"{basic_header['ver_major']}.{basic_header['ver_minor']}"
    bytes_in_headers = int(basic_header["bytes_in_headers"])
    packet_size = int(basic_header["bytes_in_data_packets"])

    extended_header_count = int(basic_header["extended_header_count"])
    raw_extended_headers = _read_struct(
        file_path, np.dtype([("packet_id", "S8"), ("info", "S24")]), _NEV_BASIC_HEADER.itemsize, extended_header_count
    )
    raw_packet_ids = np.array([bytes(header)[:8] for header in raw_extended_headers], dtype="S8")
    extended_headers = {}
    for header_id in np.unique(raw_packet_ids):
        header_dtype = _NEV_EXTENDED_HEADERS.get(header_id.ljust(8, b"\x00"))
        name = _decode_bytes(header_id)
        if header_dtype is None:
            extended_headers[name] = raw_extended_headers[raw_packet_ids == header_id]
            continue
        extended_headers[name] = raw_extended_headers[raw_packet_ids == header_id].view(header_dtype)

    timestamp_type = "<u8" if spec == "3.0" else "<u4"
    packet_count = max(file_size - bytes_in_headers, 0) // packet_size
    trailing_bytes = max(file_size - bytes_in_headers, 0) - packet_count * packet_size
    common_dtype = np.dtype(
        [
            ("timestamp", timestamp_type),
            ("packet_id", "<u2"),
            ("body", f"V{packet_size - np.dtype(timestamp_type).itemsize - 2}"),
        ]
    )
    if packet_count == 0:
        packets = np.zeros(0, dtype=common_dtype)
    else:
        packets = np.memmap(file_path, dtype=common_dtype, mode="r", offset=bytes_in_headers, shape=(packet_count,))

    timestamps = np.asarray(packets["timestamp"])
    packet_ids = np.asarray(packets["packet_id"])
    continuation_mask = timestamps == np.iinfo(timestamp_type).max
    timestamp_size = np.dtype(timestamp_type).itemsize

    def body_view(mask: np.ndarray, fields: list) -> np.ndarray:
        used_size = np.dtype(fields).itemsize
        remainder = packet_size - timestamp_size - 2 - used_size
        dtype = np.dtype(
            [("timestamp", timestamp_type), ("packet_id", "<u2"), *fields]
            + ([("unused", f"V{remainder}")] if remainder > 0 else [])
        )
        return np.asarray(packets[mask]).view(dtype)

    is_electrode_packet = (
        (packet_ids > _DIGITAL_PACKET_ID) & (packet_ids < _FIRST_SYSTEM_PACKET_ID) & ~continuation_mask
    )
    application = _decode_bytes(basic_header["application"])
    is_stimulation = np.zeros_like(is_electrode_packet)
    if application.startswith("Trellis"):
        is_stimulation = is_electrode_packet & (packet_ids > _TRELLIS_LAST_RECORDING_ELECTRODE_ID)
    is_spike = is_electrode_packet & ~is_stimulation
    spike_packets = body_view(is_spike, [("unit_class", "u1"), ("reserved", "u1")])
    spikes = np.zeros(
        len(spike_packets),
        dtype=[("timestamp", "<u8"), ("electrode_id", "<u2"), ("unit_class", "u1"), ("packet_index", "<u8")],
    )
    spikes["timestamp"] = spike_packets["timestamp"]
    spikes["electrode_id"] = spike_packets["packet_id"]
    spikes["unit_class"] = spike_packets["unit_class"]
    spikes["packet_index"] = np.flatnonzero(is_spike)

    stimulation_packets = body_view(is_stimulation, [("unit_class", "u1"), ("reserved", "u1")])
    stimulation_events = np.zeros(
        len(stimulation_packets), dtype=[("timestamp", "<u8"), ("electrode_id", "<u2"), ("packet_index", "<u8")]
    )
    stimulation_events["timestamp"] = stimulation_packets["timestamp"]
    stimulation_events["electrode_id"] = stimulation_packets["packet_id"]
    stimulation_events["packet_index"] = np.flatnonzero(is_stimulation)

    is_digital = (packet_ids == _DIGITAL_PACKET_ID) & ~continuation_mask
    digital_packets = body_view(is_digital, [("insertion_reason", "u1"), ("reserved", "u1"), ("value", "<u2")])
    digital_events = np.zeros(
        len(digital_packets), dtype=[("timestamp", "<u8"), ("insertion_reason", "u1"), ("value", "<u2")]
    )
    for name in digital_events.dtype.names:
        digital_events[name] = digital_packets[name]

    comment_packets = body_view(
        (packet_ids == _COMMENT_PACKET_ID) & ~continuation_mask,
        [("char_set", "u1"), ("flag", "u1"), ("data", "<u4"), ("text", f"S{packet_size - timestamp_size - 2 - 6}")],
    )
    comments = [
        _decode_comment(packet, is_ptp=int(basic_header["timestamp_resolution"]) == _PTP_TIMESTAMP_RESOLUTION)
        for packet in comment_packets
    ]

    video_sync_events = body_view(
        (packet_ids == _VIDEO_SYNC_PACKET_ID) & ~continuation_mask,
        [("file_number", "<u2"), ("frame_number", "<u4"), ("elapsed_time", "<u4"), ("source_id", "<u4")],
    )
    tracking_events = body_view(
        (packet_ids == _TRACKING_PACKET_ID) & ~continuation_mask,
        [
            ("parent_id", "<u2"),
            ("node_id", "<u2"),
            ("node_count", "<u2"),
            ("point_count", "<u2"),
            ("points", "<u2", ((packet_size - timestamp_size - 10) // 2,)),
        ],
    )
    button_trigger_events = body_view(
        (packet_ids == _BUTTON_TRIGGER_PACKET_ID) & ~continuation_mask, [("trigger_type", "<u2")]
    )
    log_packets = body_view(
        (packet_ids == _LOG_PACKET_ID) & ~continuation_mask,
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
        (packet_ids == _CONFIGURATION_PACKET_ID) & ~continuation_mask,
        [("change_type", "<u2"), ("text", f"S{packet_size - timestamp_size - 4}")],
    )
    configuration_events = [
        dict(
            timestamp=int(packet["timestamp"]),
            change_type=int(packet["change_type"]),
            text=_decode_bytes(packet["text"]),
        )
        for packet in configuration_packets
    ]
    recording_packets = body_view((packet_ids == _RECORDING_EVENT_PACKET_ID) & ~continuation_mask, [("reason", "<u2")])
    recording_events = [
        dict(
            timestamp=int(packet["timestamp"]),
            reason=_RECORDING_EVENT_REASONS.get(int(packet["reason"]), f"unknown ({int(packet['reason'])})"),
        )
        for packet in recording_packets
    ]

    known_system_ids = [
        _COMMENT_PACKET_ID,
        _VIDEO_SYNC_PACKET_ID,
        _TRACKING_PACKET_ID,
        _BUTTON_TRIGGER_PACKET_ID,
        _LOG_PACKET_ID,
        _CONFIGURATION_PACKET_ID,
        _RECORDING_EVENT_PACKET_ID,
    ]
    is_other = (packet_ids >= _FIRST_SYSTEM_PACKET_ID) & ~np.isin(packet_ids, known_system_ids) & ~continuation_mask
    other_ids, other_counts = np.unique(packet_ids[is_other], return_counts=True)

    return _NEVFile(
        file_path=file_path,
        spec=spec,
        timestamp_resolution=int(basic_header["timestamp_resolution"]),
        sample_resolution=int(basic_header["sample_resolution"]),
        time_origin=_read_time_origin(basic_header),
        application=application,
        comment=_decode_bytes(basic_header["comment"]),
        packet_size=packet_size,
        waveforms_are_16_bit=bool(basic_header["additional_flags"] & 1),
        extended_headers=extended_headers,
        spikes=spikes,
        stimulation_events=stimulation_events,
        digital_events=digital_events,
        comments=comments,
        video_sync_events=video_sync_events,
        tracking_events=tracking_events,
        button_trigger_events=button_trigger_events,
        log_events=log_events,
        configuration_events=configuration_events,
        recording_events=recording_events,
        other_packet_counts={int(packet_id): int(count) for packet_id, count in zip(other_ids, other_counts)},
        continuation_packet_count=int(continuation_mask.sum()),
        trailing_bytes=int(trailing_bytes),
    )


def _decode_comment(packet: np.void, is_ptp: bool) -> dict:
    """Decode a comment packet (0xFFFF).

    With flag 1 the data field is the time the comment was started: a timestamp on the 30 kHz clock, and the
    microseconds from the start back to the packet on the PTP clock (see the vault note
    `blackrock_comment_start_time`). Character set 255 marks a NeuroMotive region-of-interest crossing.
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


def get_digitization_factors(nev_file: _NEVFile) -> dict[int, float]:
    """Nanovolts per count of each electrode, from the NEUEVWAV headers.

    Spec 2.1 continuous files carry no scaling, so it comes from here. 21516 is the value buggy Cerebus
    firmware wrote for 152,592.547 nV, corrected as NPMK `openNEV.m` does.
    """
    waveform_headers = nev_file.extended_headers.get("NEUEVWAV")
    if waveform_headers is None:
        return {}
    factors = {}
    for electrode_id, factor in zip(waveform_headers["electrode_id"], waveform_headers["digitization_factor"]):
        factors[int(electrode_id)] = 152_592.547 if factor == 21516 else float(factor)
    return factors


def units_to_microvolts(units: str) -> float | None:
    return _UNITS_TO_MICROVOLTS.get(units)
