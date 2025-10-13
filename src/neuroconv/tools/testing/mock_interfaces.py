from datetime import datetime
from typing import Literal

import numpy as np
from pynwb import NWBFile
from pynwb.base import DynamicTable
from pynwb.device import Device

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
from ...tools.nwb_helpers import get_module
from ...utils import ArrayType, get_json_schema_from_method_signature
from ...utils.dict import DeepDict


class MockInterface(BaseDataInterface):
    """
    A mock interface for testing basic command passing without side effects.
    """

    def __init__(self, verbose: bool = False, **source_data):

        super().__init__(verbose=verbose, **source_data)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        session_start_time = datetime.now().astimezone()
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None, **conversion_options):

        return None


class MockTimeSeriesInterface(BaseDataInterface):
    """
    A mock TimeSeries interface for testing purposes.

    This interface uses pynwb's mock_TimeSeries to create synthetic time series data
    without only pynwb as a dependency.
    """

    def __init__(
        self,
        *,
        num_channels: int = 4,
        sampling_frequency: float = 30_000.0,
        duration: float = 1.0,
        seed: int = 0,
        verbose: bool = False,
        metadata_key: str = "TimeSeries",
    ):
        """
        Initialize a mock TimeSeries interface.

        Parameters
        ----------
        num_channels : int, optional
            Number of channels to generate, by default 4.
        sampling_frequency : float, optional
            Sampling frequency in Hz, by default 30,000.0 Hz.
        duration : float, optional
            Duration of the data in seconds, by default 1.0.
        seed : int, optional
            Seed for the random number generator, by default 0.
        verbose : bool, optional
            Control verbosity, by default False.
        metadata_key : str, optional
            Key for the TimeSeries metadata in the metadata dictionary, by default "TimeSeries".
        """
        self.num_channels = num_channels
        self.sampling_frequency = sampling_frequency
        self.duration = duration
        self.seed = seed
        self.metadata_key = metadata_key

        super().__init__(verbose=verbose)

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the TimeSeries interface.

        Returns
        -------
        dict
            The metadata dictionary containing NWBFile and TimeSeries metadata.
        """
        metadata = super().get_metadata()
        session_start_time = datetime.now().astimezone()
        metadata["NWBFile"]["session_start_time"] = session_start_time

        # Add TimeSeries metadata using the metadata_key
        metadata["TimeSeries"] = {
            self.metadata_key: {
                "name": self.metadata_key,
                "description": f"Mock TimeSeries data with {self.num_channels} channels",
                "unit": "n.a.",
            }
        }

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
    ):
        """
        Add mock TimeSeries data to an NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the TimeSeries data will be added.
        metadata : dict, optional
            Metadata dictionary. If None, uses default metadata.
        """
        from pynwb.testing.mock.base import mock_TimeSeries

        if metadata is None:
            metadata = self.get_metadata()

        # Generate mock data
        rng = np.random.default_rng(self.seed)
        num_samples = int(self.duration * self.sampling_frequency)
        data = rng.standard_normal(size=(num_samples, self.num_channels)).astype("float32")

        # Get TimeSeries kwargs from metadata
        time_series_metadata = metadata.get("TimeSeries", {}).get(self.metadata_key, {})

        tseries_kwargs = {
            "name": time_series_metadata.get("name", "MockTimeSeries"),
            "description": time_series_metadata.get("description", "Mock TimeSeries data"),
            "unit": time_series_metadata.get("unit", "n.a."),
            "data": data,
            "starting_time": 0.0,
            "rate": self.sampling_frequency,
        }

        # Apply any additional metadata
        for key in ["comments", "conversion", "offset"]:
            if key in time_series_metadata:
                tseries_kwargs[key] = time_series_metadata[key]

        time_series = mock_TimeSeries(**tseries_kwargs)
        nwbfile.add_acquisition(time_series)


class MockBehaviorEventInterface(BaseTemporalAlignmentInterface):
    """
    A mock behavior event interface for testing purposes.
    """

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["event_times"])
        source_schema["additionalProperties"] = True
        return source_schema

    def __init__(self, event_times: ArrayType | None = None):
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
        self, signal_duration: float = 7.0, ttl_times: list[list[float]] | None = None, ttl_duration: float = 1.0
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
        set_probe: bool = False,
    ):
        super().__init__(
            num_channels=num_channels,
            sampling_frequency=sampling_frequency,
            durations=durations,
            set_probe=set_probe,
            seed=seed,
            verbose=verbose,
            es_key=es_key,
        )

        self.recording_extractor.set_channel_gains(gains=[1.0] * self.recording_extractor.get_num_channels())
        self.recording_extractor.set_channel_offsets(offsets=[0.0] * self.recording_extractor.get_num_channels())

        # If probe was set, customize contact IDs to use "e0", "e1", etc. format for testing
        if set_probe and self.recording_extractor.has_probe():
            probe = self.recording_extractor.get_probe()
            contact_ids = [f"e{i}" for i in range(num_channels)]
            probe.set_contact_ids(contact_ids)
            self.recording_extractor = self.recording_extractor.set_probe(probe, group_mode="by_probe")

    def get_metadata(self) -> DeepDict:
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

    def get_metadata(self) -> DeepDict:
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
        num_samples: int | None = None,
        num_frames: int | None = None,
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
        num_samples : int, optional
            The number of samples (frames) in the mock imaging data, by default 30.
        num_frames : int, optional
            Deprecated. Use num_samples instead. Will be removed after February 2025.
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

        # Handle deprecation of num_frames parameter
        if num_frames is not None and num_samples is not None:
            raise ValueError("Cannot specify both num_frames and num_samples. Use num_samples only.")
        elif num_frames is not None:
            import warnings

            warnings.warn(
                "The 'num_frames' parameter is deprecated and will be removed after February 2025. "
                "Use 'num_samples' instead.",
                FutureWarning,
                stacklevel=2,
            )
            num_samples = num_frames
        elif num_samples is None:
            num_samples = 30  # Default value

        self.seed = seed
        super().__init__(
            num_samples=num_samples,
            num_rows=num_rows,
            num_columns=num_columns,
            sampling_frequency=sampling_frequency,
            dtype=dtype,
            verbose=verbose,
            seed=seed,
        )

        self.verbose = verbose
        self.photon_series_type = photon_series_type

    def get_metadata(self) -> DeepDict:
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
        num_samples: int | None = None,
        num_frames: int | None = None,
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
        num_samples : int, optional
            number of samples (frames), by default 30.
        num_frames : int, optional
            Deprecated. Use num_samples instead. Will be removed after February 2025.
            number of frames, by default 30.
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

        # Handle deprecation of num_frames parameter
        if num_frames is not None and num_samples is not None:
            raise ValueError("Cannot specify both num_frames and num_samples. Use num_samples only.")
        elif num_frames is not None:
            import warnings

            warnings.warn(
                "The 'num_frames' parameter is deprecated and will be removed after February 2025. "
                "Use 'num_samples' instead.",
                FutureWarning,
                stacklevel=2,
            )
            num_samples = num_frames
        elif num_samples is None:
            num_samples = 30  # Default value

        super().__init__(
            num_rois=num_rois,
            num_samples=num_samples,
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

    def get_metadata(self) -> DeepDict:
        session_start_time = datetime.now().astimezone()
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata


class MockPoseEstimationInterface(BaseTemporalAlignmentInterface):
    """
    A mock pose estimation interface for testing purposes.
    """

    display_name = "Mock Pose Estimation"
    keywords = (
        "behavior",
        "pose estimation",
        "mock",
    )
    associated_suffixes = []
    info = "Mock interface for pose estimation data testing."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["timestamps", "confidence"])
        source_schema["additionalProperties"] = True
        return source_schema

    def __init__(
        self,
        num_samples: int = 1000,
        num_nodes: int = 3,
        pose_estimation_metadata_key: str = "MockPoseEstimation",
        seed: int = 0,
        verbose: bool = False,
    ):
        """
        Initialize a mock pose estimation interface.

        Parameters
        ----------
        num_samples : int, optional
            Number of samples to generate, by default 1000.
        num_nodes : int, optional
            Number of nodes/body parts to track, by default 3.
        pose_estimation_metadata_key : str, optional
            Key for pose estimation metadata container, by default "MockPoseEstimation".
        seed : int, optional
            Random seed for reproducible data generation, by default 0.
        verbose : bool, optional
            Control verbosity, by default False.
        """
        self.num_samples = num_samples
        self.num_nodes = num_nodes
        self.pose_estimation_metadata_key = pose_estimation_metadata_key
        self.seed = seed
        self.verbose = verbose

        # Set metadata defaults
        self.scorer = "MockScorer"
        self.source_software = "MockSourceSoftware"

        # Generate random nodes and edges
        orbital_body_parts = [
            "head",
            "neck",
            "left_shoulder",
            "right_shoulder",
            "chest",
            "left_elbow",
            "right_elbow",
            "left_wrist",
            "right_wrist",
            "pelvis",
        ]

        # Use orbital body parts if we have enough, otherwise generate generic nodes
        if num_nodes <= len(orbital_body_parts):
            self.nodes = orbital_body_parts[:num_nodes]
        else:
            self.nodes = orbital_body_parts + [f"node_{i}" for i in range(len(orbital_body_parts), num_nodes)]

        # Generate random edges (connect some nodes randomly)
        np.random.seed(seed)  # For reproducible edge generation
        num_edges = min(num_nodes - 1, max(1, num_nodes // 2))  # Reasonable number of edges
        possible_edges = [(i, j) for i in range(num_nodes) for j in range(i + 1, num_nodes)]
        selected_edges = np.random.choice(len(possible_edges), size=num_edges, replace=False)
        self.edges = np.array([possible_edges[i] for i in selected_edges], dtype="uint8")

        # Generate timestamps (private attributes)
        self._original_timestamps = np.linspace(0.0, float(num_samples) / 30.0, num_samples)
        self._timestamps = np.copy(self._original_timestamps)

        # Generate pose estimation data
        self.pose_data = self._generate_pose_data()

        super().__init__(verbose=verbose)

        # Import ndx_pose to ensure it's available
        import ndx_pose  # noqa: F401

    def _generate_pose_data(self) -> np.ndarray:
        """Generate pose estimation data with center following Lissajous trajectory and nodes fixed on circle."""
        # Fixed to 2D for now
        shape = (self.num_samples, self.num_nodes, 2)

        # Generate Lissajous trajectory for the center
        time_points = np.linspace(0, 4 * np.pi, self.num_samples)
        center_x = 320 + 80 * np.sin(1.2 * time_points)  # Center follows Lissajous
        center_y = 240 + 60 * np.sin(1.7 * time_points + np.pi / 3)

        # Generate data for all nodes
        data = np.zeros(shape)
        circle_radius = 50  # Radius of circle around center

        for node_index in range(self.num_nodes):
            # Position each node equally spaced around a circle relative to center
            angle = 2 * np.pi * node_index / self.num_nodes

            # Fixed position on circle relative to center (no oscillations)
            offset_x = circle_radius * np.cos(angle)
            offset_y = circle_radius * np.sin(angle)

            # Final position: center + fixed circle position
            data[:, node_index, 0] = center_x + offset_x
            data[:, node_index, 1] = center_y + offset_y

        return data

    def get_original_timestamps(self) -> np.ndarray:
        """Get the original timestamps before any alignment."""
        return self._original_timestamps

    def get_timestamps(self) -> np.ndarray:
        """Get the current (possibly aligned) timestamps."""
        return self._timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        """Set aligned timestamps."""
        self._timestamps = aligned_timestamps

    def get_metadata(self) -> DeepDict:
        """Get metadata for the mock pose estimation interface."""
        metadata = super().get_metadata()
        session_start_time = datetime.now().astimezone()
        metadata["NWBFile"]["session_start_time"] = session_start_time

        # Create metadata following the DeepLabCut pattern
        container_name = self.pose_estimation_metadata_key
        skeleton_name = f"Skeleton{container_name}"
        device_name = f"Camera{container_name}"

        # Create PoseEstimation metadata structure
        pose_estimation_metadata = DeepDict()

        # Add Skeleton as a dictionary
        pose_estimation_metadata["Skeletons"] = {
            skeleton_name: {"name": skeleton_name, "nodes": self.nodes, "edges": self.edges.tolist()}
        }

        # Add Device as a dictionary
        pose_estimation_metadata["Devices"] = {
            device_name: {"name": device_name, "description": "Mock camera device for pose estimation testing."}
        }

        # Add PoseEstimation container
        pose_estimation_metadata["PoseEstimationContainers"] = {
            container_name: {
                "name": container_name,
                "description": f"Mock pose estimation data from {self.source_software}.",
                "source_software": self.source_software,
                "dimensions": [[640, 480]],
                "skeleton": skeleton_name,
                "devices": [device_name],
                "scorer": self.scorer,
                "original_videos": ["mock_video.mp4"],
                "PoseEstimationSeries": {},
            }
        }

        # Add a series for each node
        for node in self.nodes:
            # Convert node name to PascalCase for the series name
            pascal_case_node = "".join(word.capitalize() for word in node.replace("_", " ").split())
            series_name = f"PoseEstimationSeries{pascal_case_node}"

            pose_estimation_metadata["PoseEstimationContainers"][container_name]["PoseEstimationSeries"][node] = {
                "name": series_name,
                "description": f"Mock pose estimation series for {node}.",
                "unit": "pixels",
                "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                "confidence_definition": "Softmax output of the deep neural network.",
            }

        # Add PoseEstimation metadata to the main metadata
        metadata["PoseEstimation"] = pose_estimation_metadata

        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, **conversion_options):
        """Add mock pose estimation data to NWBFile using ndx-pose."""
        from ndx_pose import PoseEstimation, PoseEstimationSeries, Skeleton, Skeletons

        # Create or get behavior processing module
        behavior_module = get_module(nwbfile, "behavior")

        # Create device
        device = Device(name="MockCamera", description="Mock camera device for pose estimation testing")
        nwbfile.add_device(device)

        # Create skeleton
        skeleton = Skeleton(name="MockSkeleton", nodes=self.nodes, edges=self.edges)

        # Create pose estimation series for each node
        pose_estimation_series = []
        for index, node_name in enumerate(self.nodes):
            # Convert node name to PascalCase for the series name
            pascal_case_node = "".join(word.capitalize() for word in node_name.replace("_", " ").split())
            series_name = f"PoseEstimationSeries{pascal_case_node}"

            series = PoseEstimationSeries(
                name=series_name,
                description=f"Pose estimation for {node_name}",
                data=self.pose_data[:, index, :],
                unit="pixels",
                reference_frame="top left corner of video frame",
                timestamps=self.get_timestamps(),
                confidence=np.ones(self.num_samples),
                confidence_definition="definition of confidence",
            )
            pose_estimation_series.append(series)

        # Create pose estimation container
        pose_estimation = PoseEstimation(
            name="MockPoseEstimation",
            description=f"Mock pose estimation data from {self.source_software}",
            pose_estimation_series=pose_estimation_series,
            skeleton=skeleton,
            devices=[device],
            scorer=self.scorer,
            source_software=self.source_software,
            dimensions=np.array([[640, 480]], dtype="uint16"),
            original_videos=["mock_video.mp4"],
            labeled_videos=["mock_video_labeled.mp4"],
        )

        behavior_module.add(pose_estimation)
        if "Skeletons" not in behavior_module.data_interfaces:
            skeletons = Skeletons(skeletons=[skeleton])
            behavior_module.add(skeletons)
        else:
            skeletons = behavior_module["Skeletons"]
            skeletons.add_skeletons(skeleton)
