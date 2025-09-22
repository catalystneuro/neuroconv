import warnings
from pathlib import Path

import numpy as np
from pydantic import ConfigDict, DirectoryPath, FilePath, validate_call
from pynwb import NWBFile

from .spikeglx_utils import get_session_start_time
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
        return source_schema

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __init__(
        self,
        file_path: FilePath | None = None,
        verbose: bool = False,
        es_key: str = "ElectricalSeriesNIDQ",
        folder_path: DirectoryPath | None = None,
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

        super().__init__(
            verbose=verbose,
            es_key=es_key,
            folder_path=self.folder_path,
            file_path=file_path,
        )

        signal_info_key = (0, "nidq")  # Key format is (segment_index, stream_id)
        self._signals_info_dict = self.recording_extractor.neo_reader.signals_info_dict[signal_info_key]
        self.meta = self._signals_info_dict["meta"]

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        session_start_time = get_session_start_time(self.meta)
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Device metadata
        device = dict(
            name="NIDQBoard",
            description="A NIDQ board used in conjunction with SpikeGLX.",
            manufacturer="National Instruments",
        )

        metadata["Devices"] = [device]

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
            self._add_digital_channels(nwbfile=nwbfile)

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

        analog_recorder = recording.select_channels(channel_ids=self.analog_channel_ids)
        channel_names = analog_recorder.get_property(key="channel_names")

        # Create default metadata if not provided
        if metadata is None:
            metadata = self.get_metadata()

        # Prepare TimeSeries metadata
        time_series_name = "TimeSeriesNIDQ"
        description = f"Analog data from the NIDQ board. Channels are {channel_names} in that order."
        metadata["TimeSeries"][time_series_name] = dict(description=description)
        # Use add_recording_as_time_series_to_nwbfile to add the time series
        add_recording_as_time_series_to_nwbfile(
            recording=analog_recorder,
            nwbfile=nwbfile,
            metadata=metadata,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
            always_write_timestamps=always_write_timestamps,
            time_series_name=time_series_name,
        )

    def _add_digital_channels(self, nwbfile: NWBFile):
        """
        Add digital channels from the NIDQ board to the NWB file as events.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the digital channels to
        """
        from ndx_events import LabeledEvents

        event_channels = self.event_extractor.channel_ids
        for channel_id in event_channels:
            events_structure = self.event_extractor.get_events(channel_id=channel_id)
            timestamps = events_structure["time"]
            labels = events_structure["label"]

            # Some channels have no events
            if timestamps.size > 0:

                # Timestamps are not ordered, the ones for off are first and then the ones for on
                ordered_indices = np.argsort(timestamps)
                ordered_timestamps = timestamps[ordered_indices]
                ordered_labels = labels[ordered_indices]

                unique_labels = np.unique(ordered_labels)
                label_to_index = {label: index for index, label in enumerate(unique_labels)}
                data = [label_to_index[label] for label in ordered_labels]

                channel_name = channel_id.split("#")[-1]
                description = f"On and Off Events from channel {channel_name}"
                name = f"EventsNIDQDigitalChannel{channel_name}"
                labeled_events = LabeledEvents(
                    name=name, description=description, timestamps=ordered_timestamps, data=data, labels=unique_labels
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
