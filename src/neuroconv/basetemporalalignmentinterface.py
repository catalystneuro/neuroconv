from abc import abstractmethod

import numpy as np

from .basedatainterface import BaseDataInterface


class BaseTemporalAlignmentInterface(BaseDataInterface):
    """An extension of the BaseDataInterface that includes several methods for performing temporal alignment."""

    @abstractmethod
    def get_original_timestamps(self) -> np.ndarray:
        """
        Retrieve the original unaltered timestamps for the data in this interface.

        This function should retrieve the data on-demand by re-initializing the IO.

        Returns
        -------
        timestamps: numpy.ndarray
            The timestamps for the data stream.
        """
        raise NotImplementedError(
            "Unable to retrieve the original unaltered timestamps for this interface! "
            "Define the `get_original_timestamps` method for this interface."
        )

    @abstractmethod
    def get_timestamps(self) -> np.ndarray:
        """
        Retrieve the timestamps for the data in this interface.

        Returns
        -------
        timestamps: numpy.ndarray
            The timestamps for the data stream.
        """
        raise NotImplementedError(
            "Unable to retrieve timestamps for this interface! Define the `get_timestamps` method for this interface."
        )

    @abstractmethod
    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        """
        Replace all timestamps for this interface with those aligned to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_timestamps : numpy.ndarray
            The synchronized timestamps for data in this interface.
        """
        raise NotImplementedError(
            "The protocol for synchronizing the timestamps of this interface has not been specified!"
        )

    def set_aligned_starting_time(self, aligned_starting_time: float) -> None:
        """
        Align the starting time for this interface relative to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_starting_time : float
            The starting time for all temporal data in this interface.
        """
        self.set_aligned_timestamps(aligned_timestamps=self.get_timestamps() + aligned_starting_time)

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray) -> None:
        """
        Interpolate the timestamps of this interface using a mapping from some unaligned time basis to its aligned one.

        Use this method if the unaligned timestamps of the data in this interface are not directly tracked by a primary
        system, but are known to occur between timestamps that are tracked, then align the timestamps of this interface
        by interpolating between the two.

        An example could be a metronomic TTL pulse (e.g., every second) from a secondary data stream to the primary
        timing system; if the time references of this interface are recorded within the relative time of the secondary
        data stream, then their exact time in the primary system is inferred given the pulse times.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        unaligned_timestamps : numpy.ndarray
            The timestamps of the unaligned secondary time basis.
        aligned_timestamps : numpy.ndarray
            The timestamps aligned to the primary time basis.
        """
        self.set_aligned_timestamps(
            aligned_timestamps=np.interp(x=self.get_timestamps(), xp=unaligned_timestamps, fp=aligned_timestamps)
        )
