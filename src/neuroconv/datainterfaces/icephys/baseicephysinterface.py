"""Shared writing contract for modern intracellular-electrophysiology interfaces."""

from abc import abstractmethod

from pynwb import NWBFile

from ..._temporal_alignment import _TemporalAlignment
from ...basedatainterface import BaseDataInterface
from ...tools.icephys import (
    _add_intracellular_electrode_to_nwbfile,
    _add_intracellular_recordings_to_nwbfile,
    _add_patch_clamp_series_to_nwbfile,
    _IcephysSeriesData,
)


class BaseIcephysInterface(BaseDataInterface):
    """Base interface for patch-clamp data written as NWB icephys series.

    Concrete interfaces return source data through :meth:`_get_icephys_series_data`. This base owns NWB object
    construction, metadata-linked electrode resolution, and the per-sweep ``IntracellularRecordings`` rows.
    The hierarchy above those rows remains a converter responsibility, once every interface has contributed.
    """

    def __init__(self, *, verbose: bool = False, **source_data):
        super().__init__(verbose=verbose, **source_data)
        self._alignment = _TemporalAlignment()

    @property
    def alignment(self):
        return self._alignment

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None) -> None:
        """Write this interface's response, optional stimulus, and sweep rows to an NWB file."""
        if metadata is None:
            metadata = self.get_metadata()

        series_metadata_key = self._series_metadata_key
        response_metadata = metadata["Icephys"]["PatchClampSeries"][series_metadata_key]
        electrode = _add_intracellular_electrode_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            electrode_metadata_key=response_metadata["electrode_metadata_key"],
        )
        response_data, stimulus_data, sweep_sample_ranges = self._get_icephys_series_data()
        timestamps = self.alignment[self._alignment_key].get_times()
        if timestamps.ndim != 1 or len(timestamps) != len(response_data.data):
            raise ValueError("Intracellular timestamps must be one-dimensional with one time per response sample.")
        response_data.timestamps = timestamps
        if stimulus_data is not None:
            if len(stimulus_data.data) != len(timestamps):
                raise ValueError("The paired stimulus must have one sample per response timestamp.")
            stimulus_data.timestamps = timestamps
        response_series = _add_patch_clamp_series_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            series_metadata_key=series_metadata_key,
            series_data=response_data,
            electrode=electrode,
            mode=self._mode,
            is_stimulus=False,
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
                is_stimulus=True,
            )

        _add_intracellular_recordings_to_nwbfile(
            nwbfile=nwbfile,
            electrode=electrode,
            response_series=response_series,
            stimulus_series=stimulus_series,
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
