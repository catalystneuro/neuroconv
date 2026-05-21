"""SpikeInterface ``BaseRecording`` wrapping PVFS indexed channels.

A PVFS container can hold many indexed channels at heterogeneous sampling rates
(EEG, EMG, accelerometers, ...).  SpikeInterface requires a uniform sampling
frequency per :class:`spikeinterface.core.BaseRecording`, so the extractor only
ever exposes channels that share a rate.  Pass ``sampling_rate_hz`` to pick a
specific group, or omit it to use whichever rate has the most channels.

The extractor lazily extracts the full time-series for each selected channel
the first time it is accessed and caches it as ``float32``.  This matches how
typical Pinnacle EEG recordings are used (read once, write once) and keeps the
implementation small.  All channels are truncated to the shortest length so
they share a uniform frame axis.

This module imports SpikeInterface at module load.  Callers that need to
preserve neuroconv's minimal import surface should defer importing this module
until they actually need the extractor (see
``PvfsRecordingInterface.get_extractor_class``).
"""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from spikeinterface.core import BaseRecording, BaseRecordingSegment

from .._metadata import (
    _read_metadata_from_db,
    discover_video_stream_bases,
    extract_experiment_db,
    filter_indexed_channels,
    hightime_to_seconds,
    open_pvfs,
    resolve_channel_file_base,
)


def _channel_sampling_rate(info) -> float | None:
    """Return the float-precision sampling rate for a channel, or ``None``."""
    if info is None:
        return None
    if info.data_rate_float not in (None, ""):
        try:
            rate = float(info.data_rate_float)
            if rate > 0:
                return rate
        except (TypeError, ValueError):
            pass
    if info.data_rate is not None:
        try:
            rate = float(info.data_rate)
            if rate > 0:
                return rate
        except (TypeError, ValueError):
            pass
    return None


def _select_channels_for_rate(
    channels: dict, sampling_rate_hz: float | None, channel_names: list[str] | None
) -> tuple[float, list[str]]:
    """Pick channels that share a sampling rate; auto-pick the rate if needed.

    Returns ``(rate, ordered_channel_names)``.  Raises ``ValueError`` if no
    indexed channel can be found.
    """
    if not channels:
        raise ValueError("No channels found in PVFS file (experiment.db3 is empty).")

    rates = {name: _channel_sampling_rate(info) for name, info in channels.items()}
    candidate_names = list(rates.keys()) if channel_names is None else list(channel_names)

    if channel_names is not None:
        missing = [n for n in channel_names if n not in channels]
        if missing:
            raise ValueError(f"Channels not present in PVFS: {missing}")

    if sampling_rate_hz is None:
        rate_counts = Counter(rates[name] for name in candidate_names if rates[name] is not None)
        if not rate_counts:
            raise ValueError("None of the selected channels have a usable sampling rate.")
        sampling_rate_hz, _ = rate_counts.most_common(1)[0]

    tol = max(1e-6, abs(sampling_rate_hz) * 1e-6)
    selected = [
        name
        for name in candidate_names
        if rates[name] is not None and abs(rates[name] - sampling_rate_hz) <= tol
    ]
    if not selected:
        raise ValueError(f"No channels match the requested sampling rate {sampling_rate_hz} Hz.")
    return float(sampling_rate_hz), selected


def _maybe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class PvfsRecordingExtractor(BaseRecording):
    """``BaseRecording`` exposing PVFS indexed channels at one sampling rate."""

    name = "pvfs"
    mode = "file"

    def __init__(
        self,
        file_path: str | os.PathLike,
        sampling_rate_hz: float | None = None,
        channel_names: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        # NeuroConv's BaseRecordingExtractorInterface injects ``all_annotations=True``
        # into every extractor constructor; accept-and-ignore unknown kwargs so the
        # extractor plugs in without an explicit signature change.
        kwargs.pop("all_annotations", None)
        kwargs.pop("es_key", None)

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PVFS file not found: {file_path}")

        with open_pvfs(file_path) as vfs:
            video_bases = discover_video_stream_bases(vfs)
            db_path = extract_experiment_db(vfs)
            try:
                meta = _read_metadata_from_db(db_path)
            finally:
                try:
                    db_path.unlink(missing_ok=True)
                except OSError:
                    pass

            indexed_channels = filter_indexed_channels(meta.channels, video_bases)
            rate, selected_names = _select_channels_for_rate(
                indexed_channels,
                sampling_rate_hz=sampling_rate_hz,
                channel_names=channel_names,
            )

            self._pvfs_metadata = meta
            self._selected_rate = rate
            self._selected_channel_names = list(selected_names)
            self._channel_units: list[str] = []
            self._channel_low_high: list[tuple[float | None, float | None]] = []
            self._channel_t_start_seconds: list[float] = []
            self._channel_num_samples: list[int] = []
            self._channel_file_bases: list[str] = []

            # Probe each channel for length + per-channel timing without loading
            # all samples; the heavy read happens lazily in the segment.
            from pvfs_tools.Core.indexed_data_file import IndexedDataFile

            min_samples = None
            earliest_start: float | None = None
            for ch_name in selected_names:
                info = meta.channels[ch_name]
                file_base = resolve_channel_file_base(info, ch_name)
                self._channel_file_bases.append(file_base)
                self._channel_units.append(info.unit or "uV")
                low = _maybe_float(info.low_range)
                high = _maybe_float(info.high_range)
                self._channel_low_high.append((low, high))

                idf = IndexedDataFile(vfs, file_base, channel_name=ch_name)
                try:
                    start_sec = hightime_to_seconds(idf.get_start_time()) or 0.0
                    end_sec = hightime_to_seconds(idf.get_end_time()) or start_sec
                    n = max(0, int(round((end_sec - start_sec) * rate)) + 1)
                    self._channel_t_start_seconds.append(start_sec)
                    self._channel_num_samples.append(n)
                    min_samples = n if min_samples is None else min(min_samples, n)
                    if earliest_start is None or start_sec < earliest_start:
                        earliest_start = start_sec
                finally:
                    idf.close()

            assert min_samples is not None
            self._common_num_samples = int(min_samples)
            self._common_t_start_seconds = (
                float(earliest_start) if earliest_start is not None else 0.0
            )

        BaseRecording.__init__(
            self,
            sampling_frequency=rate,
            channel_ids=list(selected_names),
            dtype=np.dtype("float32"),
        )

        gain_to_uV = np.ones(len(selected_names), dtype="float32")
        offset_to_uV = np.zeros(len(selected_names), dtype="float32")
        for idx, unit in enumerate(self._channel_units):
            unit_lower = (unit or "").strip().lower()
            if unit_lower == "v":
                gain_to_uV[idx] = 1e6
            elif unit_lower == "mv":
                gain_to_uV[idx] = 1e3
            elif unit_lower in ("uv", "\xb5v", "u v", "\u00b5v"):
                gain_to_uV[idx] = 1.0

        self.set_property("gain_to_uV", gain_to_uV)
        self.set_property("offset_to_uV", offset_to_uV)
        self.set_property(
            "physical_unit",
            np.array([u if u else "uV" for u in self._channel_units], dtype=object),
        )
        self.set_property(
            "channel_name",
            np.array(list(selected_names), dtype=object),
        )

        segment = PvfsRecordingSegment(
            file_path=str(file_path),
            channel_names=list(selected_names),
            channel_file_bases=self._channel_file_bases,
            sampling_frequency=rate,
            num_samples=self._common_num_samples,
            t_start=self._common_t_start_seconds,
        )
        self.add_recording_segment(segment)

        self._kwargs = {
            "file_path": str(file_path),
            "sampling_rate_hz": rate,
            "channel_names": list(selected_names),
        }

    @property
    def selected_sampling_rate(self) -> float:
        """Sampling rate (Hz) selected for this extractor."""
        return self._selected_rate

    @property
    def selected_channel_names(self) -> list[str]:
        """Channel names included in this extractor."""
        return list(self._selected_channel_names)

    @property
    def pvfs_metadata(self):
        """The :class:`PvfsMetadata` snapshot captured at construction time."""
        return self._pvfs_metadata


class PvfsRecordingSegment(BaseRecordingSegment):
    """One PVFS recording segment that lazily caches per-channel float32 traces."""

    def __init__(
        self,
        file_path: str,
        channel_names: list[str],
        channel_file_bases: list[str],
        sampling_frequency: float,
        num_samples: int,
        t_start: float,
    ) -> None:
        super().__init__(sampling_frequency=sampling_frequency, t_start=t_start, time_vector=None)
        self._file_path = file_path
        self._channel_names = list(channel_names)
        self._channel_file_bases = list(channel_file_bases)
        self._num_samples = int(num_samples)
        self._traces_cache: list[np.ndarray | None] = [None] * len(channel_names)

    def get_num_samples(self) -> int:
        """Return the number of samples (frames) in this segment."""
        return self._num_samples

    def _load_channel(self, channel_index: int) -> np.ndarray:
        cached = self._traces_cache[channel_index]
        if cached is not None:
            return cached

        from pvfs_tools.Core.indexed_data_file import IndexedDataFile

        ch_name = self._channel_names[channel_index]
        file_base = self._channel_file_bases[channel_index]
        with open_pvfs(self._file_path) as vfs:
            idf = IndexedDataFile(vfs, file_base, channel_name=ch_name)
            try:
                start = idf.get_start_time()
                end = idf.get_end_time()
                _, values = idf.get_data(start, end)
            finally:
                idf.close()

        arr = np.asarray(values, dtype=np.float32)
        if arr.size > self._num_samples:
            arr = arr[: self._num_samples]
        elif arr.size < self._num_samples:
            padded = np.zeros(self._num_samples, dtype=np.float32)
            padded[: arr.size] = arr
            arr = padded
        self._traces_cache[channel_index] = arr
        return arr

    def get_traces(
        self,
        start_frame: int | None = None,
        end_frame: int | None = None,
        channel_indices: list | np.ndarray | tuple | slice | None = None,
    ) -> np.ndarray:
        """Return ``(n_samples, n_channels)`` ``float32`` traces."""
        start = 0 if start_frame is None else int(start_frame)
        end = self._num_samples if end_frame is None else int(end_frame)
        start = max(0, start)
        end = max(start, min(end, self._num_samples))

        if channel_indices is None:
            indices = list(range(len(self._channel_names)))
        elif isinstance(channel_indices, slice):
            indices = list(range(len(self._channel_names)))[channel_indices]
        else:
            indices = [int(i) for i in channel_indices]

        n_samples = end - start
        out = np.empty((n_samples, len(indices)), dtype=np.float32)
        for col, ch_idx in enumerate(indices):
            out[:, col] = self._load_channel(ch_idx)[start:end]
        return out
