"""Authors: Cody Baker."""
from typing import Optional

import numpy as np
from pynwb import NWBFile
from pynwb.base import DynamicTable
from spikeinterface.extractors import NumpyRecording

from .mock_ttl_signals import generate_mock_ttl_signal
from ..signal_processing import synchronize_timestamps_between_systems
from ...basedatainterface import BaseDataInterface
from ...datainterfaces import SpikeGLXNIDQInterface
from ...utils import ArrayType


class MockBehaviorEventInterface(BaseDataInterface):
    def __init__(self):
        """
        Define event times in the time basis of the DeepLacCut secondary acquisition system.

        The primary system is the SpikeGLX recording.
        Pulses are sent from the DLC to the NIDQ board on each frame capture.
        """
        self.event_times = [5.6, 7.3, 9.7]

    def get_timestamps(self) -> np.ndarray:
        return self.event_times

    def synchronize_between_systems(
        self, primary_reference_timestamps: ArrayType, secondary_reference_timestamps: ArrayType
    ):
        synchronized_times = synchronize_timestamps_between_systems(
            times=self.event_times,
            primary_reference_timestamps=primary_reference_timestamps,
            secondary_reference_timestamps=secondary_reference_timestamps,
        )
        self.event_times = synchronized_times

    def run_conversion(self, nwbfile: NWBFile):
        table = DynamicTable(name="BehaviorEvents", description="Times of various classified behaviors.")
        table.add_column(name="event_times", description="Time of each event.", data=self.event_timess)
        self.nwbfile.add_acquisition(table)


class MockSpikeGLXNIDQInterface(SpikeGLXNIDQInterface):
    def __init__(
        self,
        signal_duration: float = 7.0,
        ttl_times: Optional[ArrayType] = None,
        ttl_duration: float = 1.0,
    ):
        """
        Define a mock SpikeGLXNIDQInterface by overriding the recording extractor to be a mock TTL signal.

        # TODO, allow definition of channel names and more than one TTL, if desired.
        # TODO, make the metadata of this mock mimic the true thing

        Parameters
        ----------
        signal_duration: float, optional
            The number of seconds to simulate.
            The default is 5.5 seconds.
        ttl_times: array of floats, optional
            The times within the `signal_duration` to trigger the TTL pulse.
            In conjunction with the `ttl_duration`, these must produce disjoint 'on' intervals.
            The default generates a periodic 1 second on, 1 second off pattern.
        ttl_duration: float, optional
            How long the TTL pulse stays in the 'on' state when triggered, in seconds.
            In conjunction with the `ttl_times`, these must produce disjoint 'on' intervals.
            The default is 1 second.
        """
        self.recording_extractor = NumpyRecording(
            traces_list=generate_mock_ttl_signal(
                signal_duration=signal_duration, ttl_times=ttl_times, ttl_duration=ttl_duration
            )[..., np.newaxis],
            sampling_frequency=25000.0,
        )
