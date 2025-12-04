import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
from pydantic import ConfigDict, DirectoryPath, validate_call
from pynwb import NWBFile

from ....basedatainterface import BaseDataInterface
from ....tools.signal_processing import get_rising_frames_from_ttl
from ....utils import (
    DeepDict,
    get_json_schema_from_method_signature,
    to_camel_case,
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
        source_schema["properties"]["folder_path"]["description"] = "Path to the folder containing the .nidq.bin file."
        source_schema["properties"]["metadata_key"]["description"] = (
            "Key used to organize metadata in the metadata dictionary. This is especially useful "
            "when multiple NIDQ interfaces are used in the same conversion. The metadata_key is used "
            "to organize TimeSeries and Events metadata."
        )
        return source_schema

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        verbose: bool = False,
        es_key: str | None = None,
        metadata_key: str = "SpikeGLXNIDQ",
        analog_channel_groups: dict[str, dict] | None = None,
        digital_channel_groups: dict[str, dict] | None = None,
    ):
        """
        Read analog and digital channel data from the NIDQ board for the SpikeGLX recording.

        The NIDQ stream records both analog and digital (usually non-neural) signals.
        XD channels are converted to events directly.
        XA and MA channels can be organized into separate TimeSeries using analog_channel_groups.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing the .nidq.bin file.
        verbose : bool, default: False
            Whether to output verbose text.
        es_key : str, optional
            Deprecated. This parameter has no effect and will be removed on or after May 2026.
        metadata_key : str, default: "SpikeGLXNIDQ"
            Key used to organize metadata in the metadata dictionary. This is especially useful
            when multiple NIDQ interfaces are used in the same conversion. The metadata_key is used
            to organize TimeSeries and Events metadata.
        analog_channel_groups : dict[str, dict], optional
            Dictionary mapping group names to analog channel configurations.
            Each group specifies which channels to include and will be written as a separate
            TimeSeries in the NWB file.
            If None (default), all analog channels are written as a single TimeSeries.
            If empty dict {}, no analog channels are written.

            Structure:
                {
                    "group_key": {
                        "channels": ["channel_id_1", "channel_id_2", ...],
                    },
                }

            Example:
                {
                    "audio": {
                        "channels": ["nidq#XA0"],
                    },
                    "accel": {
                        "channels": ["nidq#XA3", "nidq#XA4", "nidq#XA5"],
                    },
                }
        digital_channel_groups : dict[str, dict], optional
            Dictionary mapping group names to digital channel configurations.
            Each group specifies which channels to include and their label mappings.
            If None (default), all digital channels are written with auto-generated defaults.
            If empty dict {}, no digital channels are written.

            Currently, only single-channel groups are supported (each group maps to one
            LabeledEvents object). Multi-channel groups will be supported in future versions
            when ndx-events EventsTable is integrated into NWB core.


            Structure:
                {
                    "group_key": {
                        "channels": {
                            "channel_id": {"labels_map": {0: "label_a", 1: "label_b"}},
                        },
                    },
                }

            Example:
                {
                    "camera": {
                        "channels": {
                            "nidq#XD0": {"labels_map": {0: "exposure_end", 1: "frame_start"}},
                        },
                    },
                    "lick": {
                        "channels": {
                            "nidq#XD1": {"labels_map": {0: "no_lick", 1: "lick_detected"}},
                        },
                    },
                }

        """

        if es_key is not None:
            warnings.warn(
                "The 'es_key' parameter is deprecated and will be removed on or after May 2026. "
                "This parameter has no effect as SpikeGLXNIDQInterface writes analog data as TimeSeries "
                "and digital data as LabeledEvents, not ElectricalSeries.",
                FutureWarning,
                stacklevel=2,
            )

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

        # Resolve to defaults if None, then validate
        self._analog_channel_groups = (
            analog_channel_groups if analog_channel_groups is not None else self._get_default_analog_channel_groups()
        )
        self._validate_analog_channel_groups()

        self._digital_channel_groups = (
            digital_channel_groups if digital_channel_groups is not None else self._get_default_digital_channel_groups()
        )
        self._validate_digital_channel_groups()

        super().__init__(
            verbose=verbose,
            es_key=es_key,
            folder_path=self.folder_path,
        )

        signal_info_key = (0, "nidq")  # Key format is (segment_index, stream_id)
        self._signals_info_dict = self.recording_extractor.neo_reader.signals_info_dict[signal_info_key]
        self.meta = self._signals_info_dict["meta"]

    def _validate_analog_channel_groups(self) -> None:
        """Validate analog_channel_groups structure and channel IDs."""
        all_analog_ids_set = set(self.analog_channel_ids)
        for group_key, group_config in self._analog_channel_groups.items():
            if "channels" not in group_config:
                raise ValueError(f"Analog group '{group_key}' missing required 'channels' field.")

            channels = group_config["channels"]
            invalid_channels = set(channels) - all_analog_ids_set
            if invalid_channels:
                raise ValueError(
                    f"Invalid channels in group '{group_key}': {invalid_channels}. "
                    f"Available analog channels: {self.analog_channel_ids}"
                )

    def _validate_digital_channel_groups(self) -> None:
        """Validate digital_channel_groups structure, channel IDs, and labels_map."""
        if not self.has_digital_channels:
            return

        all_digital_ids = set(self.event_extractor.channel_ids)
        for group_key, group_config in self._digital_channel_groups.items():
            if "channels" not in group_config:
                raise ValueError(f"Digital group '{group_key}' missing required 'channels' field.")

            channels_config = group_config["channels"]

            # Validate single-channel groups (temporary limitation)
            if len(channels_config) != 1:
                raise ValueError(
                    f"Digital group '{group_key}' has {len(channels_config)} channels. "
                    f"Currently only single-channel groups are supported. "
                    f"Multi-channel groups will be supported when ndx-events EventsTable "
                    f"is integrated into NWB core."
                )

            # Validate each channel in the group
            for channel_id, channel_config in channels_config.items():
                if channel_id not in all_digital_ids:
                    available_channels = sorted([str(ch) for ch in all_digital_ids])
                    raise ValueError(
                        f"Invalid digital channel '{channel_id}' in group '{group_key}'. "
                        f"Available digital channels: {available_channels}"
                    )
                if "labels_map" not in channel_config:
                    raise ValueError(
                        f"Channel '{channel_id}' in group '{group_key}' "
                        f"missing required 'labels_map' field. "
                        f"Example: {{'{channel_id}': {{'labels_map': {{0: 'off', 1: 'on'}}}}}}"
                    )

                # Validate labels_map covers all unique values from extractor
                labels_map = channel_config["labels_map"]
                events_structure = self.event_extractor.get_events(channel_id=channel_id)
                raw_labels = events_structure["label"]
                if raw_labels.size > 0:
                    num_unique_values = len(np.unique(raw_labels))
                    expected_keys = set(range(num_unique_values))
                    provided_keys = set(labels_map.keys())
                    if provided_keys != expected_keys:
                        example_labels = {i: f"label_{i}" for i in range(num_unique_values)}
                        raise ValueError(
                            f"Incomplete labels_map for channel '{channel_id}' in group '{group_key}'. "
                            f"Expected keys {expected_keys}, got {provided_keys}. "
                            f"labels_map must cover all {num_unique_values} unique values from the extractor. "
                            f"Example: {example_labels}"
                        )

    def _get_default_digital_channel_groups(self) -> dict:
        """
        Return default digital channel groups configuration.

        Creates one group per digital channel with auto-generated labels_map.
        Used when digital_channel_groups is None (backward compatibility).

        Returns
        -------
        dict
            Dictionary with one group per channel, each containing channels config with labels_map.
        """
        if not self.has_digital_channels:
            return {}

        groups = {}
        for channel_id in self.event_extractor.channel_ids:
            events_structure = self.event_extractor.get_events(channel_id=channel_id)
            raw_labels = events_structure["label"]

            if raw_labels.size > 0:
                unique_labels = np.unique(raw_labels)
                labels_map = {idx: str(label) for idx, label in enumerate(unique_labels)}
            else:
                labels_map = {}

            groups[channel_id] = {
                "channels": {
                    channel_id: {"labels_map": labels_map},
                },
            }
        return groups

    def _get_default_analog_channel_groups(self) -> dict:
        """
        Return default analog channel groups configuration.

        Creates a single group with all analog channels.
        Used when analog_channel_groups is None (backward compatibility).

        Returns
        -------
        dict
            Dictionary with single "nidq_analog" group containing all analog channels.
        """
        if not self.has_analog_channels:
            return {}

        return {
            "nidq_analog": {
                "channels": list(self.analog_channel_ids),
            }
        }

    def _get_default_events_metadata(self) -> dict:
        """
        Returns default metadata for digital channel events.

        Single source of truth for default digital channel event metadata.
        Each call returns a new instance to prevent accidental mutation of global state.

        Returns
        -------
        dict
            Dictionary mapping group keys to their NWB metadata (name, description).
        """
        default_metadata = {}
        for group_key, group_config in self._digital_channel_groups.items():
            channels_config = group_config["channels"]
            channel_id = next(iter(channels_config.keys()))
            channel_name = channel_id.split("#")[-1]

            # For auto-generated groups (key = channel_id), use legacy naming
            if group_key.startswith("nidq#"):
                default_name = f"EventsNIDQDigitalChannel{channel_name}"
            else:
                default_name = to_camel_case(group_key)

            default_metadata[group_key] = {
                "name": default_name,
                "description": f"On and Off Events from channel {channel_name}",
            }

        return default_metadata

    def _get_default_analog_metadata(self) -> dict:
        """
        Returns default metadata for analog channel TimeSeries.

        Structure depends on whether analog_channel_groups was provided at init.
        If grouping specified, creates metadata for each group.
        Otherwise, returns single TimeSeries configuration for all channels.

        Returns
        -------
        dict
            Dictionary with analog channel TimeSeries metadata.
        """
        metadata = {}

        # Get channel names for descriptions
        channel_names_property = self.recording_extractor.get_property(key="channel_names")

        for group_key, group_config in self._analog_channel_groups.items():
            channels = group_config["channels"]

            # Get names for these specific channels
            if channel_names_property is not None:
                indices = [i for i, ch_id in enumerate(self.analog_channel_ids) if ch_id in channels]
                group_channel_names = [str(channel_names_property[i]) for i in indices]
            else:
                group_channel_names = list(channels)

            # For default group, use legacy naming
            if group_key == "nidq_analog":
                default_name = "TimeSeriesNIDQ"
                description = f"Analog data from the NIDQ board. Channels are {group_channel_names} in that order."
            else:
                default_name = to_camel_case(group_key)
                description = (
                    f"Analog data from NIDQ board, group '{group_key}'. "
                    f"Channels are {group_channel_names} in that order."
                )

            metadata[group_key] = {
                "name": default_name,
                "description": description,
            }

        return metadata

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
        )

        metadata["Devices"] = [device]

        # TimeSeries metadata for analog channels
        if self.has_analog_channels:
            metadata["TimeSeries"][self.metadata_key] = self._get_default_analog_metadata()

        # Events metadata for digital channels
        if self.has_digital_channels:
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

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        iterator_type: str | None = "v2",
        iterator_options: dict | None = None,
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
        iterator_options : dict | None, default: None
            Additional options for the iterator
        iterator_opts : dict | None, default: None
            Deprecated. Use 'iterator_options' instead.
        always_write_timestamps : bool, default: False
            If True, always writes timestamps instead of using sampling rate
        """
        # Handle deprecated iterator_opts parameter
        if iterator_opts is not None:
            warnings.warn(
                "The 'iterator_opts' parameter is deprecated and will be removed in May 2026 or after. "
                "Use 'iterator_options' instead.",
                FutureWarning,
                stacklevel=2,
            )
            if iterator_options is not None:
                raise ValueError("Cannot specify both 'iterator_opts' and 'iterator_options'. Use 'iterator_options'.")
            iterator_options = iterator_opts

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
                iterator_options=iterator_options,
                always_write_timestamps=always_write_timestamps,
                metadata=metadata,
            )

        if self.has_digital_channels:
            self._add_digital_channels(nwbfile=nwbfile, metadata=metadata)

    def _add_analog_channels(
        self,
        nwbfile: NWBFile,
        recording,  # we pass the recording because it might be stubbed
        iterator_type: str | None,
        iterator_options: dict | None,
        always_write_timestamps: bool,
        metadata: dict,
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
        iterator_options : dict | None
            Additional options for the iterator
        always_write_timestamps : bool
            If True, always writes timestamps instead of using sampling rate
        metadata : dict
            Metadata dictionary with TimeSeries information
        """
        from ....tools.spikeinterface import add_recording_as_time_series_to_nwbfile

        if not self._analog_channel_groups:
            return

        # Get TimeSeries configurations from metadata
        time_series_metadata = metadata.get("TimeSeries", {}).get(self.metadata_key, {})

        # Write each group as a TimeSeries
        for group_key, group_config in self._analog_channel_groups.items():
            # Check if this group has metadata
            if group_key not in time_series_metadata:
                continue

            channels = group_config["channels"]
            channel_recording = recording.select_channels(channel_ids=channels)

            # Get metadata for this group
            ts_metadata = {"TimeSeries": {group_key: time_series_metadata[group_key]}}

            # Write TimeSeries
            add_recording_as_time_series_to_nwbfile(
                recording=channel_recording,
                nwbfile=nwbfile,
                metadata=ts_metadata,
                iterator_type=iterator_type,
                iterator_options=iterator_options,
                always_write_timestamps=always_write_timestamps,
                metadata_key=group_key,
            )

    def _add_digital_channels(
        self,
        nwbfile: NWBFile,
        metadata: dict,
    ):
        """
        Add digital channels from the NIDQ board to the NWB file as events.

        Data structure (which channels, labels_map) comes from channel groups config.
        NWB properties (name, description, meanings) come from metadata.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the digital channels to
        metadata : dict
            Metadata dictionary containing channel configurations.
        """
        from ndx_events import LabeledEvents

        if not self._digital_channel_groups:
            return

        events_metadata = metadata.get("Events", {}).get(self.metadata_key, {})

        for group_key, group_config in self._digital_channel_groups.items():
            channels_config = group_config["channels"]
            # Get the single channel (validated at init to be single-channel for user groups)
            channel_id, channel_config = next(iter(channels_config.items()))

            # Get labels_map from config (data structure)
            labels_map = channel_config["labels_map"]

            # Get NWB properties from metadata
            group_metadata = events_metadata.get(group_key, {})
            default_metadata = self._get_default_events_metadata().get(group_key, {})
            name = group_metadata.get("name", default_metadata.get("name", to_camel_case(group_key)))
            description = group_metadata.get("description", default_metadata.get("description", ""))

            # Append meanings to description if provided
            # Future: when ndx-events MeaningsTable is integrated into NWB core,
            # these will be written to MeaningsTable instead of the description
            meanings = group_metadata.get("meanings", {})
            if meanings:
                meanings_text = "\n".join(f"  - {label}: {meaning}" for label, meaning in meanings.items())
                description = f"{description}\n\nLabel meanings:\n{meanings_text}"

            # Get event data
            events_structure = self.event_extractor.get_events(channel_id=channel_id)
            timestamps = events_structure["time"]
            raw_labels = events_structure["label"]

            if timestamps.size == 0:
                continue

            # Sort by timestamp
            ordered_indices = np.argsort(timestamps)
            ordered_timestamps = timestamps[ordered_indices]
            ordered_raw_labels = raw_labels[ordered_indices]

            # Map raw labels to data values
            unique_raw_labels = np.unique(raw_labels)
            extractor_label_to_value = {str(label): index for index, label in enumerate(unique_raw_labels)}
            data = [extractor_label_to_value[str(label)] for label in ordered_raw_labels]

            # Build labels list from labels_map
            sorted_items = sorted(labels_map.items())
            labels_list = [label for _, label in sorted_items]

            labeled_events = LabeledEvents(
                name=name,
                description=description,
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
