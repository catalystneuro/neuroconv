"""Read event records from Plexon PLX files.

The layouts are defined in Plexon's Plexon.h as PL_FileHeader, PL_EventHeader,
and PL_DataBlockHeader.
"""

from collections import defaultdict
from datetime import datetime
from mmap import ACCESS_READ, mmap
from pathlib import Path
from struct import Struct

import numpy as np

from ._plexon_event_selection import _get_native_source_names

_FILE_HEADER_SIZE = 7504
_SPIKE_HEADER_SIZE = 1020
_EVENT_HEADER_SIZE = 296
_CONTINUOUS_HEADER_SIZE = 296
_CLOCK_AND_COUNTS = Struct("<4i")
_DATE = Struct("<6i")
_EVENT_HEADER = Struct("<32si")
_DATA_BLOCK = Struct("<hHIhHhh")
_EVENT_BLOCK_TYPE = 4

_STROBED_CHANNELS = {241, 242, 257}
_DEFERRED_CHANNELS = {*range(101, 110), 258, 259, 260, 261}


def _read_header(file_path: Path, data) -> tuple[int, int, dict[str, int], datetime | None]:
    if len(data) < _FILE_HEADER_SIZE or data[:4] != b"PLEX":
        raise ValueError(f"{file_path}: invalid Plexon PLX file header.")

    frequency, spike_count, event_count, continuous_count = _CLOCK_AND_COUNTS.unpack_from(data, 136)
    if frequency <= 0 or min(spike_count, event_count, continuous_count) < 0:
        raise ValueError(f"{file_path}: invalid Plexon timestamp frequency or channel count.")

    event_start = _FILE_HEADER_SIZE + spike_count * _SPIKE_HEADER_SIZE
    event_end = event_start + event_count * _EVENT_HEADER_SIZE
    block_start = event_end + continuous_count * _CONTINUOUS_HEADER_SIZE
    if block_start > len(data):
        raise ValueError(f"{file_path}: truncated Plexon channel headers.")

    names = {}
    for offset in range(event_start, event_end, _EVENT_HEADER_SIZE):
        raw_name, channel = _EVENT_HEADER.unpack_from(data, offset)
        names[channel] = raw_name.split(b"\0", 1)[0].decode("latin-1")

    sources = _get_native_source_names(names, {channel: str(channel) for channel in names})

    try:
        session_start_time = datetime(*_DATE.unpack_from(data, 160))
    except ValueError:
        session_start_time = None
    return block_start, frequency, sources, session_start_time


def _read_plx_event_sources(file_path: Path) -> dict[str, int]:
    with file_path.open("rb") as stream:
        if not stream.peek(1):
            raise ValueError(f"{file_path}: empty Plexon PLX file.")
        with mmap(stream.fileno(), length=0, access=ACCESS_READ) as data:
            _, _, sources, _ = _read_header(file_path, data)
    return sources


def _read_plx_events(
    file_path: Path,
) -> tuple[dict[str, int], dict[str, tuple[np.ndarray, np.ndarray | None]], datetime | None]:
    with file_path.open("rb") as stream:
        if not stream.peek(1):
            raise ValueError(f"{file_path}: empty Plexon PLX file.")
        with mmap(stream.fileno(), length=0, access=ACCESS_READ) as data:
            position, frequency, sources, session_start_time = _read_header(file_path, data)
            supported = set(sources.values()) - _DEFERRED_CHANNELS
            ticks_by_channel = defaultdict(list)
            words_by_channel = defaultdict(list)
            size = len(data)
            while position < size:
                if size - position < _DATA_BLOCK.size:
                    raise ValueError(f"{file_path}: truncated Plexon block header at byte {position}.")
                block_type, upper, lower, channel, word, waveforms, words_per_waveform = _DATA_BLOCK.unpack_from(
                    data, position
                )
                next_position = position + _DATA_BLOCK.size + 2 * waveforms * words_per_waveform
                if min(waveforms, words_per_waveform) < 0 or next_position > size:
                    raise ValueError(f"{file_path}: invalid Plexon block size at byte {position}.")
                if block_type == _EVENT_BLOCK_TYPE and channel in supported:
                    ticks_by_channel[channel].append((upper << 32) | lower)
                    if channel in _STROBED_CHANNELS:
                        words_by_channel[channel].append(word)
                position = next_position

    events = {}
    for source, channel in sources.items():
        if channel in supported:
            timestamps = np.asarray(ticks_by_channel[channel], dtype=np.float64) / frequency
            words = np.asarray(words_by_channel[channel], dtype=np.uint16) if channel in _STROBED_CHANNELS else None
            events[source] = (timestamps, words)
    return sources, events, session_start_time
