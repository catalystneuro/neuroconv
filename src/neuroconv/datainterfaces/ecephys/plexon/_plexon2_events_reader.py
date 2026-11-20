"""Read digital events from Plexon PL2 files.

The channel and footer layouts are documented in XSort's PL2 reader
(David Herzfeld and Scott A. Ruffner, MIT).
https://github.com/sruffner/XSort/blob/master/xsort/data/PL2.py
"""

import os
import struct
from datetime import datetime
from typing import BinaryIO

import numpy as np

from ._plexon_event_selection import _STROBED_WORD, _get_native_source_names
from ...events.baseeventsinterface import _EventsData


def _align_record(offset: int) -> int:
    return (offset + 15) & ~15


def _header_text(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("latin-1")


class _Plexon2EventsReader:
    def __init__(self, stream: BinaryIO):
        self._stream = stream
        self._file_size = stream.seek(0, os.SEEK_END)
        header = self._read(0, 0x480)
        if header[:16] != b"\xfe\x00\x00\x00\x00\x00\x00\x00\x03\x00PLEXON" or (
            header[0x10] != 0xD2 or header[0xD0] != 0xD3
        ):
            raise ValueError("Invalid Plexon PL2 file header.")

        headers_end, self._data_start, data_end, self._footer_start, self._start_ticks = struct.unpack_from(
            "<5Q", header, 0x20
        )
        self._data_end = data_end or self._footer_start or self._file_size
        self._timestamp_frequency = struct.unpack_from("<d", header, 0x258)[0]
        if not np.isfinite(self._timestamp_frequency) or self._timestamp_frequency <= 0:
            raise ValueError("Invalid Plexon PL2 timestamp frequency.")

        names = {}
        self._channel_kinds = {}
        position = 0x480
        header_limit = headers_end or self._data_start or self._file_size
        number_of_headers = struct.unpack_from("<I", header, 0x260)[0]
        for _ in range(number_of_headers):
            record_type, source, words = struct.unpack("<BBH", self._read(position, 4))
            end = position + 4 + 2 * words
            if end > header_limit:
                raise ValueError(f"Plexon PL2 channel header at {position} exceeds the header region.")
            if record_type == 0xD6:
                if end - position < 176:
                    raise ValueError(f"Truncated Plexon PL2 digital channel header at {position}.")
                record = self._read(position, 176)
                name = _header_text(record[16:80])
                header_source, channel = struct.unpack_from("<II", record, 80)
                identity = (source, channel)
                if source != header_source or identity in names:
                    raise ValueError(f"Invalid Plexon PL2 digital channel identity at {position}.")
                source_name = _header_text(record[112:176]).strip().lower()
                names[identity] = name
                self._channel_kinds[identity] = self._channel_kind(channel, source_name, header[0x11])
            position = _align_record(end)

        fallbacks = {identity: f"source{identity[0]}_channel{identity[1]}" for identity in names}
        self._channels = _get_native_source_names(names, fallbacks)
        self.source_info = {}
        for name, identity in self._channels.items():
            kind = self._channel_kinds[identity]
            entry = {"supported_operations": ["separation"] if kind == "word" else []}
            if kind is None:
                entry["unsupported_reason"] = "Only individual digital inputs and strobed words are supported."
            self.source_info[name] = entry
        self._block_offsets = None
        second, minute, hour, day, month, year = struct.unpack_from("<6i", header, 0x230)
        milliseconds = struct.unpack_from("<i", header, 0x254)[0]
        self.session_start_time = None
        if year:
            try:
                self.session_start_time = datetime(
                    year + 1900, month + 1, day, hour, minute, second, milliseconds * 1000
                )
            except ValueError:
                pass

    @staticmethod
    def _channel_kind(channel: int, source_name: str, variant: int) -> str | None:
        if source_name == "single-bit events":
            return "input"
        # OmniPlex User Guide, pp. 326 and A-56. The native channel, not its display name,
        # distinguishes a captured word from recording controls in the same source.
        if (source_name == "other events" and channel == 1) or (
            source_name == "multi-di strobed" and channel in (1, 2)
        ):
            return "word"
        if variant == 0x04 and not source_name:  # PlexUtil retains legacy PLX event channel numbers.
            if channel in (241, 242, 257):
                return "word"
            if 0 <= channel <= 256 and not (101 <= channel <= 109):
                return "input"
        return None

    def _read(self, offset: int, size: int) -> bytes:
        self._stream.seek(offset)
        data = self._stream.read(size)
        if len(data) != size:
            raise ValueError(f"Truncated Plexon PL2 file at byte {offset}.")
        return data

    def _index_blocks(self) -> dict[tuple[int, int], list[int]]:
        if self._block_offsets is not None:
            return self._block_offsets

        offsets = {identity: [] for identity, kind in self._channel_kinds.items() if kind is not None}
        if self._footer_start:
            position = self._footer_start
            while position < self._file_size:
                record_type, source, words, channel, _, count = struct.unpack("<BBHHHQ", self._read(position, 16))
                body = position + 16
                end = body + 2 * words
                if end > self._file_size:
                    raise ValueError(f"Truncated Plexon PL2 footer record at {position}.")
                identity = (source, channel)
                if record_type == 0xDF and identity in offsets and count:
                    blocks, remainder = divmod(words, 9)
                    if remainder:
                        raise ValueError(f"Invalid Plexon PL2 digital footer record at {position}.")
                    offsets[identity].extend(struct.unpack(f"<{blocks}Q", self._read(body, 8 * blocks)))
                position = _align_record(end)
        elif self._data_start:
            position = self._data_start
            while position < self._data_end:
                record_type, source, words, channel, count = self._read_block_header(position)
                identity = (source, channel)
                if record_type == 0x5A and identity in offsets and count:
                    offsets[identity].append(position)
                position = _align_record(position + 16 + 2 * words)

        self._block_offsets = offsets
        return offsets

    def _read_block_header(self, position: int) -> tuple[int, int, int, int, int]:
        if not self._data_start <= position <= self._data_end - 16:
            raise ValueError(f"Invalid Plexon PL2 data block offset {position}.")
        record_type, source, words, channel, count = struct.unpack_from("<BBHHQ", self._read(position, 16))
        if position + 16 + 2 * words > self._data_end or (record_type == 0x5A and 5 * count > words):
            raise ValueError(f"Invalid Plexon PL2 data block size at {position}.")
        return record_type, source, words, channel, count

    @property
    def populated_sources(self) -> list[str]:
        offsets = self._index_blocks()
        return [name for name, identity in self._channels.items() if offsets.get(identity)]

    def read_source(self, name: str) -> _EventsData:
        identity = self._channels[name]
        has_words = self._channel_kinds[identity] == "word"
        ticks, words = [], []
        for position in self._index_blocks()[identity]:
            record_type, source, _, channel, count = self._read_block_header(position)
            if record_type != 0x5A or (source, channel) != identity:
                raise ValueError(f"Plexon PL2 digital footer does not match the block at {position}.")
            data = self._read(position + 16, count * (10 if has_words else 8))
            ticks.append(np.frombuffer(data, dtype="<u8", count=count))
            if has_words:
                words.append(np.frombuffer(data, dtype="<u2", count=count, offset=8 * count))

        timestamps = np.empty(0, dtype=float)
        if ticks:
            # Block ticks are relative to the recording start. Use the same time origin
            # as Plexon2RecordingInterface by adding the recording start from the header.
            timestamps = (np.concatenate(ticks) + self._start_ticks) / self._timestamp_frequency
        payload = {}
        if has_words:
            payload[_STROBED_WORD] = np.concatenate(words) if words else np.empty(0, dtype=np.uint16)
        return _EventsData(event_type_source_id=name, timestamps=timestamps, payload=payload)
