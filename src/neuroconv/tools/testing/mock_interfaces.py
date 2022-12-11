"""Authors: Cody Baker."""
import numpy as np
from pynwb import NWBFile
from pynwb.base import DynamicTable

from ..signal_processing import synchronize_timestamps_between_systems
from ...basedatainterface import BaseDataInterface
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
