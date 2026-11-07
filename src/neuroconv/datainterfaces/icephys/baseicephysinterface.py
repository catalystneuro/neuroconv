"""Shared writing contract for modern intracellular-electrophysiology interfaces."""

from abc import abstractmethod

import numpy as np
from pynwb import NWBFile

from ..._temporal_alignment import _TemporalAlignment
from ...basedatainterface import BaseDataInterface
from ...tools.icephys import (
    _add_intracellular_electrode_to_nwbfile,
    _add_intracellular_recordings_to_nwbfile,
    _add_patch_clamp_series_to_nwbfile,
    _IcephysSeriesData,
)
from ...tools.nwb_helpers._metadata_and_file_helpers import _validate_metadata_key


class BaseIcephysInterface(BaseDataInterface):
    """Base interface for patch-clamp data written as NWB icephys series.

    Concrete interfaces return source data through :meth:`_get_icephys_series_data`, and a stimulus template through
    :meth:`_get_icephys_stimulus_template_data` when the source specifies one. This base owns NWB object
    construction, metadata-linked electrode resolution, and the per-sweep ``IntracellularRecordings`` rows.
    The hierarchy above those rows remains a converter responsibility, once every interface has contributed.
    """

    def __init__(self, *, verbose: bool = False, **source_data):
        super().__init__(verbose=verbose, **source_data)
        self._alignment = _TemporalAlignment()

    @property
    def temporal_alignment(self):
        return self._alignment

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None) -> None:
        """Write this interface's response, optional stimulus and stimulus template, and sweep rows to an NWB file."""
        if metadata is None:
            metadata = self.get_metadata()

        series_metadata_key = self._series_metadata_key
        _validate_metadata_key(
            metadata,
            metadata_path=("Icephys", "PatchClampSeries"),
            metadata_key=series_metadata_key,
        )
        response_metadata = metadata["Icephys"]["PatchClampSeries"][series_metadata_key]
        electrode = _add_intracellular_electrode_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            electrode_metadata_key=response_metadata["electrode_metadata_key"],
        )
        response_data, stimulus_data, sweep_sample_ranges = self._get_icephys_series_data()
        stimulus_template_data = self._get_icephys_stimulus_template_data()
        timestamps = self.temporal_alignment[self._alignment_key].get_times()
        if timestamps.ndim != 1 or len(timestamps) != len(response_data.data):
            raise ValueError("Intracellular timestamps must be one-dimensional with one time per response sample.")
        native_timestamps = response_data.timestamps
        response_data.timestamps = timestamps
        stimulus_sweep_sample_ranges = None
        if stimulus_data is not None:
            stimulus_sweep_sample_ranges = _align_paired_series(
                paired_data=stimulus_data,
                native_timestamps=native_timestamps,
                timestamps=timestamps,
                sweep_sample_ranges=sweep_sample_ranges,
                name="stimulus",
            )
        stimulus_template_sweep_sample_ranges = None
        if stimulus_template_data is not None:
            stimulus_template_sweep_sample_ranges = _align_paired_series(
                paired_data=stimulus_template_data,
                native_timestamps=native_timestamps,
                timestamps=timestamps,
                sweep_sample_ranges=sweep_sample_ranges,
                name="stimulus template",
            )
        response_series = _add_patch_clamp_series_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            series_metadata_key=series_metadata_key,
            series_data=response_data,
            electrode=electrode,
            mode=self._mode,
            role="response",
        )

        stimulus_series = None
        if stimulus_data is not None:
            stimulus_series = _add_patch_clamp_series_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                series_metadata_key=series_metadata_key,
                series_data=stimulus_data,
                electrode=electrode,
                mode=self._mode,
                role="stimulus",
            )

        stimulus_template_series = None
        if stimulus_template_data is not None:
            stimulus_template_series = _add_patch_clamp_series_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                series_metadata_key=series_metadata_key,
                series_data=stimulus_template_data,
                electrode=electrode,
                mode=self._mode,
                role="stimulus_template",
            )

        _add_intracellular_recordings_to_nwbfile(
            nwbfile=nwbfile,
            electrode=electrode,
            response_series=response_series,
            stimulus_series=stimulus_series,
            stimulus_sweep_sample_ranges=stimulus_sweep_sample_ranges,
            stimulus_template_series=stimulus_template_series,
            stimulus_template_sweep_sample_ranges=stimulus_template_sweep_sample_ranges,
            sweep_sample_ranges=sweep_sample_ranges,
            sequence=self._run_identity,
            stimulus_type=self._get_stimulus_type(),
            repetition=self._repetition,
            condition=self._condition,
        )

    @abstractmethod
    def _get_icephys_series_data(self) -> tuple[_IcephysSeriesData, _IcephysSeriesData | None, list[tuple[int, int]]]:
        """Return response, optional stimulus, and sweep ranges in the standard internal representation."""

    def _get_stimulus_type(self) -> str | None:
        """Return the run's source-described stimulus type, if any."""
        return None

    def _get_icephys_stimulus_template_data(self) -> _IcephysSeriesData | None:
        """Return the stimulus template the source specifies, if any, in the standard internal representation."""
        return None


def _align_paired_series(
    paired_data: _IcephysSeriesData,
    native_timestamps: np.ndarray,
    timestamps: np.ndarray,
    sweep_sample_ranges: list[tuple[int, int]],
    name: str,
) -> list[tuple[int, int]] | None:
    """Move a stimulus or stimulus template onto its response's aligned times, and return its own sweep ranges.

    A paired series with its own sweep ranges keeps its own times, each sweep mapped the way its response sweep
    was: the same shift, and the same stretch from the sweep's first to last sample. One without them shares the
    response's samples, so it takes the response's times.
    """
    if paired_data.sweep_sample_ranges is not None:
        native_paired_timestamps = np.asarray(paired_data.timestamps, dtype="float64")
        paired_timestamps = native_paired_timestamps.copy()
        for (response_start_index, response_count), (paired_start_index, paired_count) in zip(
            sweep_sample_ranges, paired_data.sweep_sample_ranges, strict=True
        ):
            response_stop_index = response_start_index + response_count - 1
            native_start = native_timestamps[response_start_index]
            native_span = native_timestamps[response_stop_index] - native_start
            aligned_span = timestamps[response_stop_index] - timestamps[response_start_index]
            stretch = aligned_span / native_span if native_span > 0 else 1.0
            paired_window = slice(paired_start_index, paired_start_index + paired_count)
            paired_timestamps[paired_window] = timestamps[response_start_index] + stretch * (
                native_paired_timestamps[paired_window] - native_start
            )
        paired_data.timestamps = paired_timestamps
        return paired_data.sweep_sample_ranges
    if len(paired_data.data) != len(timestamps):
        raise ValueError(f"The paired {name} must have one sample per response timestamp.")
    paired_data.timestamps = timestamps
    return None
