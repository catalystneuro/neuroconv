"""Authors: Cody Baker."""
from typing import Optional

import numpy as np

from .mock_ttl_signals import generate_mock_ttl_signal
from ...datainterfaces import SpikeGLXNIDQInterface
from ...utils import ArrayType


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
        from spikeinterface.extractors import NumpyRecording

        self.recording_extractor = NumpyRecording(
            traces_list=generate_mock_ttl_signal(
                signal_duration=signal_duration, ttl_times=ttl_times, ttl_duration=ttl_duration
            )[..., np.newaxis],
            sampling_frequency=25000.0,
        )
