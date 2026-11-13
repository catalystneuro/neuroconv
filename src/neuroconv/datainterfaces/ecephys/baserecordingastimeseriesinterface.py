from functools import partial
from typing import Literal

import numpy as np
from pynwb import NWBFile

from ..._temporal_alignment import _TemporalAlignment
from ...basedatainterface import BaseDataInterface


class BaseRecordingAsTimeSeriesInterface(BaseDataInterface):
    """
    Base for the interfaces that write a recording as a ``TimeSeries`` instead of an ``ElectricalSeries``.

    These are the channels an acquisition system records next to the electrodes: auxiliary and analog
    inputs, trigger and synchronization lines, and stimulation currents. They do not belong in an
    ``ElectricalSeries``, which is for electrical recordings from electrodes.

    A subclass reads its source into ``self.recording_extractor``, states ``self.metadata_key``, and
    names the series in its own ``get_metadata`` under ``metadata["TimeSeries"][self.metadata_key]``.
    What it does not state, the writer defaults.

    A ``TimeSeries`` states one unit for all of its channels, so an interface here holds channels of one
    unit. Where a source mixes them, select one unit per interface rather than writing them together.
    """

    # Where the series is written. A signal applied to the preparation is stimulus, a recorded one is
    # acquisition, and the writer defaults to acquisition.
    parent_container: Literal["acquisition", "stimulus"] = "acquisition"

    def __init__(self, verbose: bool = False, **source_data):
        super().__init__(verbose=verbose, **source_data)
        self._register_segments()

    def _register_segments(self) -> None:
        """Name every segment as a time-bearing object, keyed ``{metadata_key}_{segment_index}``.

        The key is the one a ``{metadata_key}_{segment_index}`` metadata entry uses to override the series of that
        segment, so one name addresses a segment for both. Registering reads nothing.
        """
        self._alignment = _TemporalAlignment()
        for segment_index in range(self.recording_extractor.get_num_segments()):
            self._alignment._register(
                key=f"{self.metadata_key}_{segment_index}",
                get_native_times=partial(self._get_segment_native_times, segment_index=segment_index),
                default_start_time=partial(self._get_segment_native_start_time, segment_index=segment_index),
                get_number_of_samples=partial(self._get_segment_number_of_samples, segment_index=segment_index),
            )

    @property
    def temporal_alignment(self) -> _TemporalAlignment:
        return self._alignment

    # The recording is read on every call because an interface replaces it when it drops channels
    def _get_segment_native_times(self, segment_index: int) -> np.ndarray:
        return self.recording_extractor.get_times(segment_index=segment_index)

    def _get_segment_native_start_time(self, segment_index: int) -> float:
        return self.recording_extractor.get_start_time(segment_index=segment_index)

    def _get_segment_number_of_samples(self, segment_index: int) -> int:
        return self.recording_extractor.get_num_samples(segment_index=segment_index)

    def get_channel_names(self) -> list[str]:
        """
        Get the names of the channels this interface holds.

        Returns
        -------
        list of str
            The channel names, in the order they are written.
        """
        return list(self.recording_extractor.get_channel_ids())

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        iterator_type: str | None = "v2",
        iterator_options: dict | None = None,
        always_write_timestamps: bool = False,
    ):
        """
        Write this interface's channels to the NWBFile as a ``TimeSeries``.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to write to.
        metadata : dict, optional
            Metadata dictionary. If None, ``get_metadata()`` is used.
        stub_test : bool, default: False
            If True, only a small amount of data is written.
        iterator_type : str, optional, default: "v2"
            Type of iterator to use for data streaming.
        iterator_options : dict, optional
            Additional options for the iterator.
        always_write_timestamps : bool, default: False
            If True, timestamps are always written instead of a sampling rate.
        """
        from ...tools.spikeinterface import _stub_recording
        from ...tools.spikeinterface.spikeinterface import (
            _add_recording_as_time_series_to_nwbfile,
        )

        if metadata is None:
            metadata = self.get_metadata()

        recording = self.recording_extractor
        if stub_test:
            recording = _stub_recording(recording=recording)

        # The aligned times are handed to the writer, never set on the recording. Timestamps when the times were
        # replaced or the segment has a time vector, otherwise the aligned start, so a shifted regular segment is
        # written as a start and a rate without building its times
        segment_timestamps, segment_starting_times = [], []
        for segment_index, key in enumerate(self.temporal_alignment.keys()):
            segment = self.temporal_alignment[key]
            if segment._times is not None or self.recording_extractor.has_time_vector(segment_index=segment_index):
                number_of_samples = recording.get_num_samples(segment_index=segment_index)
                segment_timestamps.append(segment.get_times()[:number_of_samples])
                segment_starting_times.append(None)
            else:
                segment_timestamps.append(None)
                segment_starting_times.append(segment._get_start_time())

        _add_recording_as_time_series_to_nwbfile(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            segment_timestamps=segment_timestamps,
            segment_starting_times=segment_starting_times,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
            always_write_timestamps=always_write_timestamps,
            metadata_key=self.metadata_key,
            parent_container=self.parent_container,
        )
