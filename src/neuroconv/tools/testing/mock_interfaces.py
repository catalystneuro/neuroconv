from datetime import datetime
from typing import Literal, Optional

import numpy as np
from pynwb import NWBFile
from pynwb.base import DynamicTable

from .mock_ttl_signals import generate_mock_ttl_signal
from ...basedatainterface import BaseDataInterface
from ...basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ...datainterfaces import SpikeGLXNIDQInterface
from ...datainterfaces.ecephys.baserecordingextractorinterface import (
    BaseRecordingExtractorInterface,
)
from ...datainterfaces.ecephys.basesortingextractorinterface import (
    BaseSortingExtractorInterface,
)
from ...datainterfaces.ophys.baseimagingextractorinterface import (
    BaseImagingExtractorInterface,
)
from ...datainterfaces.ophys.basesegmentationextractorinterface import (
    BaseSegmentationExtractorInterface,
)
from ...utils import ArrayType, get_json_schema_from_method_signature


class MockInterface(BaseDataInterface):
    """
    A mock interface for testing basic command passing without side effects.
    """

    def __init__(self, verbose: bool = False, **source_data):

        super().__init__(verbose=verbose, **source_data)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        session_start_time = datetime.now().astimezone()
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: Optional[dict], **conversion_options):

        return None


class MockBehaviorEventInterface(BaseTemporalAlignmentInterface):
    """
    A mock behavior event interface for testing purposes.
    """

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["event_times"])
        source_schema["additionalProperties"] = True
        return source_schema

    def __init__(self, event_times: Optional[ArrayType] = None):
        """
        Initialize the interface with event times for behavior.

        Parameters
        ----------
        event_times : list of floats, optional
            The event times to set as timestamps for this interface.
            The default is the array [1.2, 2.3, 3.4] to simulate a time series similar to the
            MockSpikeGLXNIDQInterface.
        """
        event_times = event_times or [1.2, 2.3, 3.4]
        self.event_times = np.array(event_times)
        self.original_event_times = np.array(event_times)  # Make a copy of the initial loaded timestamps

    def get_original_timestamps(self) -> np.ndarray:
        """
        Get the original event times before any alignment or transformation.

        Returns
        -------
        np.ndarray
            The original event times as a NumPy array.
        """
        return self.original_event_times

    def get_timestamps(self) -> np.ndarray:
        """
        Get the current (possibly aligned) event times.

        Returns
        -------
        np.ndarray
            The current event times as a NumPy array, possibly modified after alignment.
        """
        return self.event_times

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        """
        Set the event times after alignment.

        Parameters
        ----------
        aligned_timestamps : np.ndarray
            The aligned event timestamps to update the internal event times.
        """
        self.event_times = aligned_timestamps

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
        """
        Add the event times to an NWBFile as a DynamicTable.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the event times will be added.
        metadata : dict
            Metadata to describe the event times in the NWB file.

        Notes
        -----
        This method creates a DynamicTable to store event times and adds it to the NWBFile's acquisition.
        """
        table = DynamicTable(name="BehaviorEvents", description="Times of various classified behaviors.")
        table.add_column(name="event_time", description="Time of each event.")
        for timestamp in self.get_timestamps():
            table.add_row(event_time=timestamp)
        nwbfile.add_acquisition(table)


class MockSpikeGLXNIDQInterface(SpikeGLXNIDQInterface):
    """
    A mock SpikeGLX interface for testing purposes.
    """

    ExtractorName = "NumpyRecording"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["ttl_times"])
        source_schema["additionalProperties"] = True
        return source_schema

    def __init__(
        self, signal_duration: float = 7.0, ttl_times: Optional[list[list[float]]] = None, ttl_duration: float = 1.0
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

        self.has_analog_channels = True
        self.has_digital_channels = False

        if ttl_times is None:
            # Begin in 'off' state
            number_of_periods = int(np.ceil((signal_duration - ttl_duration) / (ttl_duration * 2)))
            default_periodic_ttl_times = [ttl_duration * (1 + 2 * period) for period in range(number_of_periods)]
            ttl_times = [[ttl_time + 0.1 * channel for ttl_time in default_periodic_ttl_times] for channel in range(8)]
        number_of_channels = len(ttl_times)
        channel_ids = [f"nidq#XA{channel_index}" for channel_index in range(number_of_channels)]  # NIDQ channel IDs
        channel_groups = ["NIDQChannelGroup"] * number_of_channels
        self.analog_channel_ids = channel_ids

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

    ExtractorModuleName = "spikeinterface.core.generate"
    ExtractorName = "generate_recording"

    def __init__(
        self,
        num_channels: int = 4,
        sampling_frequency: float = 30_000.0,
        durations: tuple[float, ...] = (1.0,),
        seed: int = 0,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ):
        super().__init__(
            num_channels=num_channels,
            sampling_frequency=sampling_frequency,
            durations=durations,
            seed=seed,
            verbose=verbose,
            es_key=es_key,
        )

        # Adding this as a safeguard before the spikeinterface changes are merged:
        # https://github.com/SpikeInterface/spikeinterface/pull/3588
        channel_ids = self.recording_extractor.get_channel_ids()
        channel_ids_as_strings = [str(id) for id in channel_ids]
        self.recording_extractor = self.recording_extractor.rename_channels(new_channel_ids=channel_ids_as_strings)

    def get_metadata(self) -> dict:
        """
        Get metadata for the recording interface.

        Returns
        -------
        dict
            The metadata dictionary containing NWBFile metadata with session start time.
        """
        metadata = super().get_metadata()
        session_start_time = datetime.now().astimezone()
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata


class MockSortingInterface(BaseSortingExtractorInterface):
    """A mock sorting extractor interface for generating synthetic sorting data."""

    # TODO: Implement this class with the lazy generator once is merged
    # https://github.com/SpikeInterface/spikeinterface/pull/2227

    ExtractorModuleName = "spikeinterface.core.generate"
    ExtractorName = "generate_sorting"

    def __init__(
        self,
        num_units: int = 4,
        sampling_frequency: float = 30_000.0,
        durations: tuple[float, ...] = (1.0,),
        seed: int = 0,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        num_units : int, optional
            Number of units to generate, by default 4.
        sampling_frequency : float, optional
            Sampling frequency of the generated data in Hz, by default 30,000.0 Hz.
        durations : tuple of float, optional
            Durations of the segments in seconds, by default (1.0,).
        seed : int, optional
            Seed for the random number generator, by default 0.
        verbose : bool, optional
            Control whether to display verbose messages during writing, by default True.

        """

        super().__init__(
            num_units=num_units,
            sampling_frequency=sampling_frequency,
            durations=durations,
            seed=seed,
            verbose=verbose,
        )

        # Sorting extractor to have string unit ids until is changed in SpikeInterface
        # https://github.com/SpikeInterface/spikeinterface/pull/3588
        string_unit_ids = [str(id) for id in self.sorting_extractor.unit_ids]
        self.sorting_extractor = self.sorting_extractor.rename_units(new_unit_ids=string_unit_ids)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        session_start_time = datetime.now().astimezone()
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata


class MockImagingInterface(BaseImagingExtractorInterface):
    """
    A mock imaging interface for testing purposes.
    """

    ExtractorModuleName = "roiextractors.testing"
    ExtractorName = "generate_dummy_imaging_extractor"

    def __init__(
        self,
        num_frames: int = 30,
        num_rows: int = 10,
        num_columns: int = 10,
        sampling_frequency: float = 30,
        dtype: str = "uint16",
        verbose: bool = False,
        seed: int = 0,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
    ):
        """
        Parameters
        ----------
        num_frames : int, optional
            The number of frames in the mock imaging data, by default 30.
        num_rows : int, optional
            The number of rows (height) in each frame of the mock imaging data, by default 10.
        num_columns : int, optional
            The number of columns (width) in each frame of the mock imaging data, by default 10.
        sampling_frequency : float, optional
            The sampling frequency of the mock imaging data in Hz, by default 30.
        dtype : str, optional
            The data type of the generated imaging data (e.g., 'uint16'), by default 'uint16'.
        seed : int, optional
            Random seed for reproducibility, by default 0.
        photon_series_type : Literal["OnePhotonSeries", "TwoPhotonSeries"], optional
            The type of photon series for the mock imaging data, either "OnePhotonSeries" or
            "TwoPhotonSeries", by default "TwoPhotonSeries".
        verbose : bool, default False
            controls verbosity
        """

        self.seed = seed
        super().__init__(
            num_frames=num_frames,
            num_rows=num_rows,
            num_columns=num_columns,
            sampling_frequency=sampling_frequency,
            dtype=dtype,
            verbose=verbose,
            seed=seed,
        )

        self.verbose = verbose
        self.photon_series_type = photon_series_type

    def get_metadata(self) -> dict:
        session_start_time = datetime.now().astimezone()
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata


class MockSegmentationInterface(BaseSegmentationExtractorInterface):
    """A mock segmentation interface for testing purposes."""

    ExtractorModuleName = "roiextractors.testing"
    ExtractorName = "generate_dummy_segmentation_extractor"

    def __init__(
        self,
        num_rois: int = 10,
        num_frames: int = 30,
        num_rows: int = 25,
        num_columns: int = 25,
        sampling_frequency: float = 30.0,
        has_summary_images: bool = True,
        has_raw_signal: bool = True,
        has_dff_signal: bool = True,
        has_deconvolved_signal: bool = True,
        has_neuropil_signal: bool = True,
        seed: int = 0,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        num_rois : int, optional
            number of regions of interest, by default 10.
        num_frames : int, optional
            description, by default 30.
        num_rows : int, optional
            number of rows in the hypothetical video from which the data was extracted, by default 25.
        num_columns : int, optional
            number of columns in the hypothetical video from which the data was extracted, by default 25.
        sampling_frequency : float, optional
            sampling frequency of the hypothetical video from which the data was extracted, by default 30.0.
        has_summary_images : bool, optional
            whether the dummy segmentation extractor has summary images or not (mean and correlation).
        has_raw_signal : bool, optional
            whether a raw fluorescence signal is desired in the object, by default True.
        has_dff_signal : bool, optional
            whether a relative (df/f) fluorescence signal is desired in the object, by default True.
        has_deconvolved_signal : bool, optional
            whether a deconvolved signal is desired in the object, by default True.
        has_neuropil_signal : bool, optional
            whether a neuropil signal is desired in the object, by default True.
        seed: int, default 0
            seed for the random number generator, by default 0
        verbose : bool, optional
            controls verbosity, by default False.
        """

        super().__init__(
            num_rois=num_rois,
            num_frames=num_frames,
            num_rows=num_rows,
            num_columns=num_columns,
            sampling_frequency=sampling_frequency,
            has_summary_images=has_summary_images,
            has_raw_signal=has_raw_signal,
            has_dff_signal=has_dff_signal,
            has_deconvolved_signal=has_deconvolved_signal,
            has_neuropil_signal=has_neuropil_signal,
            verbose=verbose,
            seed=seed,
        )

    def get_metadata(self) -> dict:
        session_start_time = datetime.now().astimezone()
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata
