"""Base class for all auxiliary channels, e.g., analog signals, digital pulses, etc."""
from typing import List

import numpy as np

from .baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....tools.signal_processing import get_rising_frames_from_ttl


class BaseAuxiliaryExtractorInterface(BaseRecordingExtractorInterface):
    """Parent class for all RecordingExtractorInterfaces."""

    def get_channel_names(self) -> List[str]:
        """Return a list of channel names as set in the recording extractor."""
        return list(self.recording_extractor.get_channel_ids())

    def get_event_times_from_ttl(self, channel_name: str) -> np.ndarray:
        """
        Return the start of event times from the rising part of TTL pulses on one of the NIDQ channels.

        Parameters
        ----------
        channel_name : str
            Name of the channel in the .nidq.bin file.

        Returns
        -------
        rising_times : numpy.ndarray
            The times of the rising TTL pulses.
        """
        # TODO: consider RAM cost of these operations and implement safer buffering version
        rising_frames = get_rising_frames_from_ttl(
            trace=self.recording_extractor.get_traces(channel_ids=[channel_name])
        )

        timestamps = self.recording_extractor.get_times()
        rising_times = timestamps[rising_frames]

        return rising_times
