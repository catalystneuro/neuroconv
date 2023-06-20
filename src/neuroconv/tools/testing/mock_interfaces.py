from datetime import datetime
from typing import List, Optional

import numpy as np
from pynwb import NWBFile
from pynwb.base import DynamicTable

from .mock_ttl_signals import generate_mock_ttl_signal
from ...basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ...datainterfaces import SpikeGLXNIDQInterface
from ...datainterfaces.ecephys.baserecordingextractorinterface import (
    BaseRecordingExtractorInterface,
)
from ...utils import ArrayType, get_schema_from_method_signature


class MockBehaviorEventInterface(BaseTemporalAlignmentInterface):
    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_schema_from_method_signature(method=cls.__init__, exclude=["event_times"])
        source_schema["additionalProperties"] = True
        return source_schema

    def __init__(self, event_times: Optional[ArrayType] = None):
        """
        Define event times for some behavior.

        Parameters
        ----------
        event_times : list of floats, optional
            The event times to set as timestamps for this interface.
            The default is the array [1.2, 2.3, 3.4] for similarity to the timescale of the MockSpikeGLXNIDQInterface.
        """
        event_times = event_times or [1.2, 2.3, 3.4]
        self.event_times = np.array(event_times)
        self.original_event_times = np.array(event_times)  # Make a copy of the initial loaded timestamps

    def get_original_timestamps(self) -> np.ndarray:
        return self.original_event_times

    def get_timestamps(self) -> np.ndarray:
        return self.event_times

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        self.event_times = aligned_timestamps

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        table = DynamicTable(name="BehaviorEvents", description="Times of various classified behaviors.")
        table.add_column(name="event_time", description="Time of each event.")
        for timestamp in self.get_timestamps():  # adding data by column gives error
            table.add_row(event_time=timestamp)
        nwbfile.add_acquisition(table)


class MockSpikeGLXNIDQInterface(SpikeGLXNIDQInterface):
    ExtractorName = "NumpyRecording"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_schema_from_method_signature(method=cls.__init__, exclude=["ttl_times"])
        source_schema["additionalProperties"] = True
        return source_schema

    def __init__(
        self, signal_duration: float = 7.0, ttl_times: Optional[List[List[float]]] = None, ttl_duration: float = 1.0
    ):
        """
        Define a mock SpikeGLXNIDQInterface by overriding the recording extractor to be a mock TTL signal.

        Parameters
        ----------
        signal_duration : float, default: 7.0
            The number of seconds to simulate.
        ttl_times : list of lists of floats, optional
            The times within the `signal_duration` to trigger the TTL pulse for each channel.
            The outer list is over channels, while each inner list is the set of TTL times for each specific channel.
            The default generates 8 channels with periodic on/off cycle (which start in the 'off' state)
            each of which is of length `ttl_duration` with a 0.1 second offset per channel.
        ttl_duration : float, default: 1.0
            How long the TTL pulses stays in the 'on' state when triggered, in seconds.
        """
        from spikeinterface.extractors import NumpyRecording

        if ttl_times is None:
            # Begin in 'off' state
            number_of_periods = int(np.ceil((signal_duration - ttl_duration) / (ttl_duration * 2)))
            default_periodic_ttl_times = [ttl_duration * (1 + 2 * period) for period in range(number_of_periods)]
            ttl_times = [[ttl_time + 0.1 * channel for ttl_time in default_periodic_ttl_times] for channel in range(8)]
        number_of_channels = len(ttl_times)
        channel_ids = [f"nidq#XA{channel_index}" for channel_index in range(number_of_channels)]  # NIDQ channel IDs
        channel_groups = ["NIDQChannelGroup"] * number_of_channels

        sampling_frequency = 25_000.0  # NIDQ sampling rate
        number_of_frames = int(signal_duration * sampling_frequency)
        traces = np.empty(shape=(number_of_frames, number_of_channels), dtype="int16")
        for channel_index in range(number_of_channels):
            traces[:, channel_index] = generate_mock_ttl_signal(
                signal_duration=signal_duration,
                ttl_times=ttl_times[channel_index],
                ttl_duration=ttl_duration,
                sampling_frequency_hz=sampling_frequency,
            )

        self.recording_extractor = NumpyRecording(
            traces_list=traces, sampling_frequency=sampling_frequency, channel_ids=channel_ids
        )
        # NIDQ channel gains
        self.recording_extractor.set_channel_gains(gains=[61.03515625] * self.recording_extractor.get_num_channels())
        self.recording_extractor.set_property(key="group_name", values=channel_groups)

        # Minimal meta so `get_metadata` works similarly to real NIDQ header
        self.meta = {"acqMnMaXaDw": "0,0,8,1", "fileCreateTime": "2020-11-03T10:35:10", "niDev1ProductName": "PCI-6259"}
        self.subset_channels = None
        self.verbose = None
        self.es_key = "ElectricalSeriesNIDQ"


class MockRecordingInterface(BaseRecordingExtractorInterface):
    """An interface with a spikeinterface recording object for testing purposes."""

    def __init__(
        self,
        num_channels=4,
        sampling_frequency=30_000.0,
        durations=[1.0],
        seed=0,
        verbose=True,
        es_key: str = "ElectricalSeries",
    ):
        from spikeinterface.core.generate import generate_recording

        # TODO: Use the true generator recording once spikeinterface is updated to 0.98
        self.recording_extractor = generate_recording(
            num_channels=num_channels, sampling_frequency=sampling_frequency, durations=durations, seed=seed
        )
        self.subset_channels = None
        self.verbose = verbose
        self.es_key = es_key

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        session_start_time = datetime.now().astimezone()
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata
