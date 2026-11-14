"""SpikeInterface extractors over the Blackrock reader in `_blackrock_reader.py`."""

from pathlib import Path

import numpy as np
from spikeinterface.core import BaseRecording, BaseRecordingSegment, BaseSorting, BaseSortingSegment

from ._blackrock_reader import (
    _SAMPLE_CLOCK_FREQUENCY,
    get_digitization_factors,
    read_nev,
    read_nsx,
    units_to_microvolts,
)

_OUT_OF_ORDER_TOLERANCE_SECONDS = 0.010
"""How far back a packet may be stamped and still count as written out of order instead of starting a new
acquisition cycle. Central on PTP rigs writes samples and spikes up to a few milliseconds out of order
(python-neo #1937), and 10 ms is the bound Chadwick Boulay proposed there."""


class _BlackrockRecordingExtractor(BaseRecording):
    """One continuous file.

    In a standard file each run of data blocks without a gap between them is a segment, starting at its first
    block's timestamp: the specification starts a new block whenever two samples are more than a sampling
    interval apart, so a block that starts exactly where the previous one ends continues it. Blocks without
    samples are skipped.

    A PTP file is one segment whose times are the per-sample timestamps, so a pause shows as a jump in its
    times. Samples written up to 10 ms out of order are put back in timestamp order.
    """

    def __init__(self, file_path: str | Path, nev_file_path: str | Path | None = None):
        file_path = Path(file_path)
        nsx_file = read_nsx(file_path)
        self._nsx_file = nsx_file

        channel_ids = [str(channel_id) for channel_id in nsx_file.channel_ids]
        BaseRecording.__init__(
            self, sampling_frequency=nsx_file.sampling_frequency, channel_ids=channel_ids, dtype=np.dtype("int16")
        )

        gains_to_uv, offsets_to_uv = self._get_scaling(nsx_file=nsx_file, nev_file_path=nev_file_path)
        if gains_to_uv is not None:
            self.set_channel_gains(gains_to_uv)
            self.set_channel_offsets(offsets_to_uv)
        self.set_property(key="channel_name", values=nsx_file.channel_labels)

        self.empty_block_indices = [
            block_index for block_index, block in enumerate(nsx_file.data_blocks) if block.sample_count == 0
        ]
        if nsx_file.is_ptp:
            timestamps = nsx_file.get_ptp_timestamps().astype("int64")
            sample_order = get_ptp_sample_order(
                timestamps=timestamps,
                tolerance_ticks=int(_OUT_OF_ORDER_TOLERANCE_SECONDS * nsx_file.timestamp_resolution),
                file_name=file_path.name,
            )
            if sample_order is not None:
                timestamps = timestamps[sample_order]
            self.add_recording_segment(
                _BlackrockRecordingSegment(
                    nsx_file=nsx_file,
                    block_indices=[0],
                    sample_order=sample_order,
                    time_vector=timestamps / nsx_file.timestamp_resolution,
                )
            )
        else:
            for block_indices in get_contiguous_block_runs(nsx_file):
                first_block = nsx_file.data_blocks[block_indices[0]]
                self.add_recording_segment(
                    _BlackrockRecordingSegment(
                        nsx_file=nsx_file,
                        block_indices=block_indices,
                        sampling_frequency=nsx_file.sampling_frequency,
                        t_start=first_block.timestamp / nsx_file.timestamp_resolution,
                    )
                )

        self._kwargs = dict(
            file_path=str(file_path.resolve()),
            nev_file_path=None if nev_file_path is None else str(Path(nev_file_path).resolve()),
        )

    @staticmethod
    def _get_scaling(nsx_file, nev_file_path):
        if nsx_file.spec != "2.1":
            factors = [units_to_microvolts(units) for units in nsx_file.units]
            if any(factor is None for factor in factors):
                return None, None
            factors = np.asarray(factors)
            return nsx_file.gains * factors, nsx_file.offsets * factors

        if nev_file_path is None:
            return None, None
        digitization_factors = get_digitization_factors(read_nev(nev_file_path))
        if not all(int(channel_id) in digitization_factors for channel_id in nsx_file.channel_ids):
            return None, None
        gains = np.array([digitization_factors[int(channel_id)] / 1000 for channel_id in nsx_file.channel_ids])
        return gains, np.zeros_like(gains)


def get_contiguous_block_runs(nsx_file) -> list[list[int]]:
    """Group the non-empty data blocks into runs where each block starts exactly where the previous one ends."""
    ticks_per_sample = nsx_file.period * nsx_file.timestamp_resolution / _SAMPLE_CLOCK_FREQUENCY
    runs = []
    expected_timestamp = None
    for block_index, block in enumerate(nsx_file.data_blocks):
        if block.sample_count == 0:
            continue
        if runs and block.timestamp == expected_timestamp:
            runs[-1].append(block_index)
        else:
            runs.append([block_index])
        expected_timestamp = block.timestamp + block.sample_count * ticks_per_sample
    return runs


def get_ptp_sample_order(timestamps: np.ndarray, tolerance_ticks: int, file_name: str) -> np.ndarray | None:
    """The permutation that puts PTP samples in timestamp order, or `None` when they already are.

    Raises when a sample steps back by more than the tolerance or two samples share a timestamp, since sorting
    would then interleave samples that do not belong together.
    """
    steps = np.diff(timestamps)
    backward_steps = steps[steps < 0]
    if len(backward_steps) == 0:
        return None
    largest_backward_step = int(-backward_steps.min())
    if largest_backward_step > tolerance_ticks:
        raise ValueError(
            f"A sample of '{file_name}' is stamped {largest_backward_step} ticks before the one written ahead of "
            f"it, more than the {tolerance_ticks} ticks that samples written out of order are seen to move."
        )
    sample_order = np.argsort(timestamps, kind="stable")
    if np.any(np.diff(timestamps[sample_order]) == 0):
        raise ValueError(f"Two samples of '{file_name}' share a timestamp.")
    return sample_order


class _BlackrockRecordingSegment(BaseRecordingSegment):
    def __init__(
        self, nsx_file, block_indices, sampling_frequency=None, t_start=None, time_vector=None, sample_order=None
    ):
        BaseRecordingSegment.__init__(
            self, sampling_frequency=sampling_frequency, t_start=t_start, time_vector=time_vector
        )
        self._nsx_file = nsx_file
        self._block_indices = block_indices
        self._sample_order = sample_order
        sample_counts = [nsx_file.data_blocks[block_index].sample_count for block_index in block_indices]
        self._block_starts = np.concatenate([[0], np.cumsum(sample_counts)])

    def get_num_samples(self) -> int:
        return int(self._block_starts[-1])

    def get_traces(self, start_frame=None, end_frame=None, channel_indices=None):
        start_frame = 0 if start_frame is None else start_frame
        end_frame = self.get_num_samples() if end_frame is None else end_frame
        if channel_indices is None:
            channel_indices = slice(None)

        if self._sample_order is not None:
            samples = self._nsx_file.get_samples(self._block_indices[0])
            return np.asarray(samples[self._sample_order[start_frame:end_frame]])[:, channel_indices]

        pieces = []
        for position, block_index in enumerate(self._block_indices):
            block_start, block_stop = self._block_starts[position], self._block_starts[position + 1]
            if block_stop <= start_frame or block_start >= end_frame:
                continue
            samples = self._nsx_file.get_samples(block_index)
            pieces.append(samples[max(start_frame - block_start, 0) : min(end_frame, block_stop) - block_start])
        if not pieces:
            return np.zeros((0, self._nsx_file.channel_count), dtype="int16")[:, channel_indices]
        return np.concatenate([np.asarray(piece)[:, channel_indices] for piece in pieces], axis=0)


class _BlackrockSortingExtractor(BaseSorting):
    """The spike packets of an event file. Units are electrode and unit class pairs, as `ch<electrode>#<unit>`.

    Each acquisition cycle of the spikes is a segment: a spike stamped more than 10 ms before the latest one so
    far starts a new cycle (a clock reset). Frames are ticks of the file's timestamp resolution, counted from
    the start of the cycle's clock, so the sampling frequency is that resolution.
    """

    def __init__(self, file_path: str | Path):
        file_path = Path(file_path)
        nev_file = read_nev(file_path)
        self._nev_file = nev_file
        spikes = nev_file.spikes

        unit_keys = np.unique(spikes[["electrode_id", "unit_class"]]) if len(spikes) else []
        unit_ids = [f"ch{int(key['electrode_id'])}#{int(key['unit_class'])}" for key in unit_keys]
        BaseSorting.__init__(self, sampling_frequency=float(nev_file.timestamp_resolution), unit_ids=unit_ids)

        cycle_starts = find_clock_restarts(
            timestamps=spikes["timestamp"],
            tolerance_ticks=int(_OUT_OF_ORDER_TOLERANCE_SECONDS * nev_file.timestamp_resolution),
        )
        cycle_bounds = np.append(cycle_starts, len(spikes))
        for cycle_start, cycle_stop in zip(cycle_bounds[:-1], cycle_bounds[1:]):
            self.add_sorting_segment(_BlackrockSortingSegment(spikes=spikes[cycle_start:cycle_stop], unit_ids=unit_ids))
        if len(spikes) == 0:
            self.add_sorting_segment(_BlackrockSortingSegment(spikes=spikes, unit_ids=unit_ids))

        self._kwargs = dict(file_path=str(file_path.resolve()))


def find_clock_restarts(timestamps: np.ndarray, tolerance_ticks: int) -> np.ndarray:
    """Indices where an acquisition cycle starts: the first packet, and every packet stamped more than
    `tolerance_ticks` before the latest timestamp of its cycle."""
    if len(timestamps) == 0:
        return np.zeros(0, dtype="int64")
    timestamps = timestamps.astype("int64")
    starts = [0]
    running_maximum = timestamps[0]
    for index in range(1, len(timestamps)):
        timestamp = timestamps[index]
        if timestamp < running_maximum - tolerance_ticks:
            starts.append(index)
            running_maximum = timestamp
        elif timestamp > running_maximum:
            running_maximum = timestamp
    return np.asarray(starts, dtype="int64")


class _BlackrockSortingSegment(BaseSortingSegment):
    def __init__(self, spikes: np.ndarray, unit_ids: list[str]):
        BaseSortingSegment.__init__(self)
        self._spike_frames_by_unit = {unit_id: np.zeros(0, dtype="int64") for unit_id in unit_ids}
        if len(spikes) == 0:
            return
        spikes = spikes[np.argsort(spikes["timestamp"], kind="stable")]
        for unit_id in unit_ids:
            electrode_text, unit_text = unit_id[2:].split("#")
            mask = (spikes["electrode_id"] == int(electrode_text)) & (spikes["unit_class"] == int(unit_text))
            self._spike_frames_by_unit[unit_id] = spikes["timestamp"][mask].astype("int64")

    def get_unit_spike_train(self, unit_id, start_frame, end_frame):
        frames = self._spike_frames_by_unit[unit_id]
        start_index = 0 if start_frame is None else np.searchsorted(frames, start_frame, side="left")
        end_index = len(frames) if end_frame is None else np.searchsorted(frames, end_frame, side="left")
        return frames[start_index:end_index]
