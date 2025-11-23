import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
from pydantic import ConfigDict, DirectoryPath, FilePath, validate_call
from pynwb import NWBFile

from ....basedatainterface import BaseDataInterface
from ....tools.signal_processing import get_rising_frames_from_ttl
from ....utils import (
    DeepDict,
    get_json_schema_from_method_signature,
)


class SpikeGLXNIDQInterface(BaseDataInterface):
    """Primary data interface class for converting the high-pass (ap) SpikeGLX format."""

    display_name = "NIDQ Recording"
    keywords = ("Neuropixels", "nidq", "NIDQ", "SpikeGLX")
    associated_suffixes = (".nidq", ".meta", ".bin")
    info = "Interface for NIDQ board recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=[])
        source_schema["properties"]["file_path"]["description"] = "Path to SpikeGLX .nidq file."
        source_schema["properties"]["metadata_key"]["description"] = (
            "Key used to organize metadata in the metadata dictionary. This is especially useful "
            "when multiple NIDQ interfaces are used in the same conversion. The metadata_key is used "
            "to organize TimeSeries and Events metadata."
        )
        return source_schema

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __init__(
        self,
        file_path: FilePath | None = None,
        verbose: bool = False,
        es_key: str = "ElectricalSeriesNIDQ",
        folder_path: DirectoryPath | None = None,
        metadata_key: str = "SpikeGLXNIDQ",
    ):
        """
        Read analog and digital channel data from the NIDQ board for the SpikeGLX recording.

        The NIDQ stream records both analog and digital (usually non-neural) signals.
        XD channels are converted to events directly.
        XA, MA and MD channels are all written together to a single TimeSeries at the moment.
        Note that the multiplexed channels MA and MD are written multiplexed at the moment.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing the .nidq.bin file.
        file_path : FilePath
            Path to .nidq.bin file.
        verbose : bool, default: False
            Whether to output verbose text.
        es_key : str, default: "ElectricalSeriesNIDQ"
        metadata_key : str, default: "SpikeGLXNIDQ"
            Key used to organize metadata in the metadata dictionary. This is especially useful
            when multiple NIDQ interfaces are used in the same conversion. The metadata_key is used
            to organize TimeSeries and Events metadata.
        """

        if file_path is not None:
            warnings.warn(
                "file_path is deprecated and will be removed by the end of 2025. "
                "The first argument of this interface will be `folder_path` afterwards. "
                "Use folder_path and stream_id instead.",
                DeprecationWarning,
                stacklevel=2,
            )

        if file_path is None and folder_path is None:
            raise ValueError("Either 'file_path' or 'folder_path' must be provided.")

        if file_path is not None:
            file_path = Path(file_path)
            self.folder_path = file_path.parent

        if folder_path is not None:
            self.folder_path = Path(folder_path)

        from spikeinterface.extractors.extractor_classes import (
            SpikeGLXRecordingExtractor,
        )

        self.recording_extractor = SpikeGLXRecordingExtractor(
            folder_path=self.folder_path,
            stream_id="nidq",
            all_annotations=True,
        )

        channel_ids = self.recording_extractor.get_channel_ids()
        # analog_channel_signatures are "XA" and "MA"
        self.analog_channel_ids = [ch for ch in channel_ids if "XA" in ch or "MA" in ch]
        self.has_analog_channels = len(self.analog_channel_ids) > 0
        self.has_digital_channels = len(self.analog_channel_ids) < len(channel_ids)
        if self.has_digital_channels:
            import ndx_events  # noqa: F401
            from spikeinterface.extractors.extractor_classes import (
                SpikeGLXEventExtractor,
            )

            self.event_extractor = SpikeGLXEventExtractor(folder_path=self.folder_path)

        self.metadata_key = metadata_key

        super().__init__(
            verbose=verbose,
            es_key=es_key,
            folder_path=self.folder_path,
            file_path=file_path,
        )

        signal_info_key = (0, "nidq")  # Key format is (segment_index, stream_id)
        self._signals_info_dict = self.recording_extractor.neo_reader.signals_info_dict[signal_info_key]
        self.meta = self._signals_info_dict["meta"]

    def _get_default_events_metadata(self) -> dict:
        """
        Returns default metadata for digital channel events.

        Single source of truth for default digital channel event metadata.
        Each call returns a new instance to prevent accidental mutation of global state.

        Returns
        -------
        dict
            Dictionary mapping channel IDs to their default metadata configurations.
        """
        default_metadata = {}

        if self.has_digital_channels:
            for channel_id in self.event_extractor.channel_ids:
                channel_name = channel_id.split("#")[-1]

                # Get extractor labels for this channel
                events_structure = self.event_extractor.get_events(channel_id=channel_id)
                raw_labels = events_structure["label"]

                # Build default labels_map from extractor (data value -> label string)
                if raw_labels.size > 0:
                    unique_labels = np.unique(raw_labels)
                    labels_map = {idx: str(label) for idx, label in enumerate(unique_labels)}
                else:
                    labels_map = {}

                default_metadata[channel_id] = {
                    "name": f"EventsNIDQDigitalChannel{channel_name}",
                    "description": f"On and Off Events from channel {channel_name}",
                    "labels_map": labels_map,
                }

        return default_metadata

    def _get_default_analog_metadata(self) -> dict:
        """
        Returns default metadata for analog channel TimeSeries.

        Single source of truth for default analog channel metadata.
        Uses NEW format with nested configuration structure.

        Returns
        -------
        dict
            Dictionary with default analog channel configuration in NEW format.
        """
        if not self.has_analog_channels:
            return {}

        # Try to get channel names, fall back to channel IDs if not available
        channel_names_property = self.recording_extractor.get_property(key="channel_names")
        if channel_names_property is not None:
            channel_names = [channel_names_property[i] for i in range(len(self.analog_channel_ids))]
        else:
            channel_names = list(self.analog_channel_ids)

        # NEW FORMAT - single configuration with all channels
        return {
            "nidq_analog": {
                "channels": list(self.analog_channel_ids),
                "name": "TimeSeriesNIDQ",
                "description": f"Analog data from the NIDQ board. Channels are {channel_names} in that order.",
            }
        }

    def _get_session_start_time(self) -> "datetime | None":
        """
        Fetches the session start time from the recording metadata.

        Returns
        -------
        datetime or None
            the session start time in datetime format.
        """

        session_start_time = self.meta.get("fileCreateTime", None)
        if session_start_time.startswith("0000-00-00"):
            # date was removed. This sometimes happens with human data to protect the
            # anonymity of medical patients.
            return
        if session_start_time:
            session_start_time = datetime.fromisoformat(session_start_time)

        return session_start_time

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        session_start_time = self._get_session_start_time()
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Device metadata
        device = dict(
            name="NIDQBoard",
            description="A NIDQ board used in conjunction with SpikeGLX.",
            manufacturer="National Instruments",
        )

        metadata["Devices"] = [device]

        # TimeSeries metadata for analog channels
        if self.has_analog_channels:
            if "TimeSeries" not in metadata:
                metadata["TimeSeries"] = {}

            metadata["TimeSeries"][self.metadata_key] = self._get_default_analog_metadata()

        # Events metadata for digital channels
        if self.has_digital_channels:
            if "Events" not in metadata:
                metadata["Events"] = {}

            metadata["Events"][self.metadata_key] = self._get_default_events_metadata()

        return metadata

    def get_channel_names(self) -> list[str]:
        """
        Get a list of channel names from the recording extractor.

        Returns
        -------
        list of str
            The names of all channels in the NIDQ recording.
        """
        return list(self.recording_extractor.get_channel_ids())

    def _get_digital_channel_config(self, channel_id: str, metadata: dict | None = None) -> dict:
        """
        Get configuration for a digital channel from metadata or use defaults.

        This method can be overridden in subclasses to provide custom channel configurations.

        Parameters
        ----------
        channel_id : str
            The channel ID (e.g., "nidq#XD0")
        metadata : dict | None, default: None
            The metadata dictionary that may contain custom channel configurations.
            If None or missing required entries, defaults are used.

        Returns
        -------
        dict
            Configuration dictionary with keys:
            - name: str, name for the LabeledEvents object
            - description: str, description of what the channel represents
            - labels_map: dict, maps data values (int) to semantic label strings
        """
        # Get default configuration
        default_events_metadata = self._get_default_events_metadata()
        default_config = default_events_metadata.get(channel_id, {})

        # Check if custom configuration exists in metadata (don't modify it)
        if metadata is not None:
            events_metadata = metadata.get("Events", {})
            interface_events = events_metadata.get(self.metadata_key, {})
            custom_config = interface_events.get(channel_id, {})
        else:
            custom_config = {}

        # Merge custom config with defaults (custom takes precedence)
        config = {
            "name": custom_config.get("name", default_config.get("name")),
            "description": custom_config.get("description", default_config.get("description")),
            "labels_map": custom_config.get("labels_map", default_config.get("labels_map")),
        }

        return config

    def _get_analog_channel_groups(self, metadata: dict | None = None) -> list[tuple[list[str], dict]]:
        """
        Transform metadata TimeSeries configurations into (channel_list, metadata) tuples for writing.

        This method extracts channel groupings from the metadata dictionary and restructures them
        into a format suitable for creating individual NWB TimeSeries objects. Each configuration
        in the metadata becomes one TimeSeries in the output NWB file.

        Returns
        -------
        list[tuple[list[str], dict]]
            List of (channel_ids, metadata_dict) tuples, one per TimeSeries.
            Only returns explicitly configured channels.

        Examples
        --------
        Input metadata:
            metadata["TimeSeries"]["SpikeGLXNIDQ"] = {
                "audio": {
                    "channels": ["nidq#XA0"],
                    "name": "AudioSignal",
                    "description": "Microphone audio"
                },
                "accel": {
                    "channels": ["nidq#XA3", "nidq#XA4"],
                    "name": "Accelerometer",
                    "description": "2-axis accelerometer"
                }
            }

        Output:
            [
                (["nidq#XA0"], {"name": "AudioSignal", "description": "Microphone audio"}),
                (["nidq#XA3", "nidq#XA4"], {"name": "Accelerometer", "description": "2-axis accelerometer"})
            ]
        """
        if metadata is None:
            metadata = self.get_metadata()

        ts_configs = metadata.get("TimeSeries", {}).get(self.metadata_key, {})

        if not ts_configs:
            # No config = no channels written
            return []

        # Detect OLD format (backward compatibility)
        # OLD format has "name" at top level and no "channels" field
        if "name" in ts_configs and "channels" not in ts_configs:
            # OLD FORMAT - single TimeSeries for all channels
            import warnings

            warnings.warn(
                "The old metadata format for NIDQ analog channels is deprecated and will be removed on or after May 2026. "
                "Please update to the new format where metadata is organized as a dictionary with channel configurations. "
                "New format example: "
                'metadata["TimeSeries"]["SpikeGLXNIDQ"] = {"audio": {"channels": ["nidq#XA0"], "name": "AudioSignal", "description": "..."}}'
                ". See the documentation for more examples.",
                FutureWarning,
                stacklevel=2,
            )
            return [(self.analog_channel_ids, ts_configs)]

        groups = []

        # TODO: remove _get_analog_channel_groups once the deprecation in in-place and
        # we implement metadata validation for the channels and name fields
        for config_key, config in ts_configs.items():
            # Validate required fields
            if "channels" not in config:
                raise ValueError(f"Configuration '{config_key}' missing required 'channels' field")
            if "name" not in config:
                raise ValueError(f"Configuration '{config_key}' missing required 'name' field")

            channels = config["channels"]

            # Prepare TimeSeries metadata (remove "channels" field)
            ts_metadata = {k: v for k, v in config.items() if k != "channels"}

            groups.append((channels, ts_metadata))

        return groups

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        stub_test: bool = False,
        iterator_type: str | None = "v2",
        iterator_opts: dict | None = None,
        always_write_timestamps: bool = False,
    ):
        """
        Add NIDQ board data to an NWB file, including both analog and digital channels if present.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the NIDQ data will be added
        metadata : dict | None, default: None
            Metadata dictionary with device information. If None, uses default metadata
        stub_test : bool, default: False
            If True, only writes a small amount of data for testing
        iterator_type : str | None, default: "v2"
            Type of iterator to use for data streaming
        iterator_opts : dict | None, default: None
            Additional options for the iterator
        always_write_timestamps : bool, default: False
            If True, always writes timestamps instead of using sampling rate
        """

        from ....tools.spikeinterface import _stub_recording

        recording = self.recording_extractor
        if stub_test:
            recording = _stub_recording(recording=self.recording_extractor)

        metadata = metadata or self.get_metadata()

        # Add devices
        device_metadata = metadata.get("Devices", [])
        for device in device_metadata:
            if device["name"] not in nwbfile.devices:
                nwbfile.create_device(**device)

        # Add analog and digital channels
        if self.has_analog_channels:
            self._add_analog_channels(
                nwbfile=nwbfile,
                recording=recording,
                iterator_type=iterator_type,
                iterator_opts=iterator_opts,
                always_write_timestamps=always_write_timestamps,
                metadata=metadata,
            )

        if self.has_digital_channels:
            self._add_digital_channels(nwbfile=nwbfile, metadata=metadata)

    def _add_analog_channels(
        self,
        nwbfile: NWBFile,
        recording,
        iterator_type: str | None,
        iterator_opts: dict | None,
        always_write_timestamps: bool,
        metadata: dict | None = None,
    ):
        """
        Add analog channels from the NIDQ board to the NWB file.


        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the analog channels to
        recording : BaseRecording
            The recording extractor containing the analog channels
        iterator_type : str | None
            Type of iterator to use for data streaming
        iterator_opts : dict | None
            Additional options for the iterator
        always_write_timestamps : bool
            If True, always writes timestamps instead of using sampling rate
        metadata : dict | None, default: None
            Metadata dictionary with TimeSeries information
        """
        from ....tools.spikeinterface import add_recording_as_time_series_to_nwbfile

        if metadata is None:
            metadata = self.get_metadata()

        # Get channel groups from metadata
        channel_groups = self._get_analog_channel_groups(metadata)

        if not channel_groups:
            # No configuration = no analog channels written
            return

        # Create a TimeSeries for each group
        for channels, ts_metadata in channel_groups:
            # Select subset of channels
            channel_recording = recording.select_channels(channel_ids=channels)

            # Create metadata structure for this TimeSeries
            ts_name = ts_metadata["name"]
            temp_metadata_key = f"{self.metadata_key}_{ts_name}"

            temp_metadata = {"TimeSeries": {temp_metadata_key: ts_metadata}}

            # Write this group as a TimeSeries
            add_recording_as_time_series_to_nwbfile(
                recording=channel_recording,
                nwbfile=nwbfile,
                metadata=temp_metadata,
                iterator_type=iterator_type,
                iterator_opts=iterator_opts,
                always_write_timestamps=always_write_timestamps,
                metadata_key=temp_metadata_key,
            )

    def _add_digital_channels(self, nwbfile: NWBFile, metadata: dict | None = None):
        """
        Add digital channels from the NIDQ board to the NWB file as events.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the digital channels to
        metadata : dict | None, default: None
            Metadata dictionary that may contain custom channel configurations.
            If None or missing required entries, defaults from get_metadata() are used.
        """
        from ndx_events import LabeledEvents

        event_channels = self.event_extractor.channel_ids
        for channel_id in event_channels:
            events_structure = self.event_extractor.get_events(channel_id=channel_id)
            timestamps = events_structure["time"]
            raw_labels = events_structure["label"]

            # Some channels have no events
            if timestamps.size > 0:

                # Timestamps are not ordered, the ones for off are first and then the ones for on
                ordered_indices = np.argsort(timestamps)
                ordered_timestamps = timestamps[ordered_indices]
                ordered_raw_labels = raw_labels[ordered_indices]

                # Get configuration for this channel
                # _get_digital_channel_config will check metadata first, then fall back to defaults
                config = self._get_digital_channel_config(channel_id, metadata)

                # Get labels_map: {data_value: label_string}
                labels_map = config["labels_map"]

                # Build reverse mapping from extractor labels to data values
                # First, get unique extractor labels and map them to consecutive integers
                unique_raw_labels = np.unique(raw_labels)
                extractor_label_to_value = {str(label): idx for idx, label in enumerate(unique_raw_labels)}

                # Map ordered raw labels to data values
                data = [extractor_label_to_value[str(label)] for label in ordered_raw_labels]

                # Fill missing mappings with default labels from extractor
                # This ensures all data values have a corresponding label
                num_unique_values = len(unique_raw_labels)
                complete_labels_map = dict(labels_map)  # Copy user-provided mappings
                default_events_metadata = self._get_default_events_metadata()
                default_labels_map = default_events_metadata.get(channel_id, {}).get("labels_map", {})

                for data_value in range(num_unique_values):
                    if data_value not in complete_labels_map:
                        # Fill with default if available, otherwise use generic label
                        complete_labels_map[data_value] = default_labels_map.get(data_value, f"unknown_{data_value}")

                # Derive labels list from complete labels_map for LabeledEvents
                # Sort by data value to ensure correct ordering
                sorted_items = sorted(complete_labels_map.items())
                labels_list = [label for _, label in sorted_items]

                labeled_events = LabeledEvents(
                    name=config["name"],
                    description=config["description"],
                    timestamps=ordered_timestamps,
                    data=data,
                    labels=labels_list,
                )
                nwbfile.add_acquisition(labeled_events)

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

        nidq_timestamps = self.recording_extractor.get_times()
        rising_times = nidq_timestamps[rising_frames]

        return rising_times
