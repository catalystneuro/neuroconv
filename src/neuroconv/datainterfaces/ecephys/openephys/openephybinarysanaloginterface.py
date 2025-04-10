from typing import Optional

from pydantic import ConfigDict, DirectoryPath, validate_call
from pynwb import NWBFile
from pynwb.base import TimeSeries

from ._openephys_utils import _get_session_start_time, _read_settings_xml
from ....basedatainterface import BaseDataInterface
from ....utils import (
    calculate_regular_series_rate,
    get_json_schema_from_method_signature,
)


class OpenEphysBinaryAnalogInterface(BaseDataInterface):
    """Primary data interface class for converting analog channels from OpenEphysBinary data."""

    display_name = "OpenEphysBinary Analog Recording"
    keywords = ("OpenEphys", "analog", "ADC")
    associated_suffixes = (".dat", ".oebin", ".npy")
    info = "Interface for OpenEphysBinary analog channel recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__)
        source_schema["properties"]["folder_path"]["description"] = "Path to OpenEphys directory (.dat files)."
        return source_schema

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __init__(
        self,
        folder_path: DirectoryPath,
        stream_name: Optional[str] = None,
        block_index: Optional[int] = None,
        verbose: bool = False,
        time_series_key: str = "TimeSeriesAnalog",
    ):
        """
        Read analog channel data from the OpenEphysBinary recording.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to directory containing OpenEphys binary files.
        stream_name : str, optional
            The name of the recording stream to load; only required if there is more than one stream detected.
            Call `OpenEphysRecordingInterface.get_stream_names(folder_path=...)` to see what streams are available.
        block_index : int, optional, default: None
            The index of the block to extract from the data.
        verbose : bool, default: False
            Controls verbosity.
        time_series_key : str, default: "TimeSeriesAnalog"
            The name of the TimeSeries object in the NWBFile.
        """
        from spikeinterface.extractors import OpenEphysBinaryRecordingExtractor

        self.folder_path = folder_path
        self._xml_root = _read_settings_xml(folder_path)

        available_streams = OpenEphysBinaryRecordingExtractor.get_streams(folder_path=folder_path)[0]
        if len(available_streams) > 1 and stream_name is None:
            raise ValueError(
                "More than one stream is detected! "
                "Please specify which stream you wish to load with the `stream_name` argument. "
                "To see what streams are available, call "
                " `OpenEphysRecordingInterface.get_stream_names(folder_path=...)`."
            )
        if stream_name is not None and stream_name not in available_streams:
            raise ValueError(
                f"The selected stream '{stream_name}' is not in the available streams '{available_streams}'!"
            )

        self.stream_name = stream_name or available_streams[0]
        self.block_index = block_index

        # Initialize the recording extractor
        self.recording_extractor = OpenEphysBinaryRecordingExtractor(
            folder_path=folder_path,
            stream_name=self.stream_name,
            block_index=block_index,
        )

        # Filter for only analog channels (ADC)
        channel_ids = self.recording_extractor.get_channel_ids()
        self.analog_channel_ids = [id for id in channel_ids if "ADC" in id]

        if not self.analog_channel_ids:
            raise ValueError(f"No analog channels (ADC) found in the selected stream '{self.stream_name}'!")

        # Select only analog channels
        self.recording_extractor = self.recording_extractor.select_channels(channel_ids=self.analog_channel_ids)

        super().__init__(
            folder_path=folder_path,
            stream_name=stream_name,
            block_index=block_index,
            verbose=verbose,
            time_series_key=time_series_key,
        )

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        session_start_time = _get_session_start_time(element=self._xml_root)
        if session_start_time is not None:
            metadata["NWBFile"].update(session_start_time=session_start_time)

        return metadata

    def get_channel_names(self) -> list[str]:
        """
        Get a list of analog channel names from the recording extractor.

        Returns
        -------
        list of str
            The names of all analog channels in the OpenEphys recording.
        """
        return list(self.analog_channel_ids)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        iterator_type: Optional[str] = "v2",
        iterator_opts: Optional[dict] = None,
        always_write_timestamps: bool = False,
    ):
        """
        Add analog channel data to an NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the analog data will be added
        metadata : Optional[dict], default: None
            Metadata dictionary with device information. If None, uses default metadata
        stub_test : bool, default: False
            If True, only writes a small amount of data for testing
        iterator_type : Optional[str], default: "v2"
            Type of iterator to use for data streaming
        iterator_opts : Optional[dict], default: None
            Additional options for the iterator
        always_write_timestamps : bool, default: False
            If True, always writes timestamps instead of using sampling rate
        """
        from ....tools.spikeinterface.spikeinterface import (
            _recording_traces_to_hdmf_iterator,
        )

        if metadata is None:
            metadata = self.get_metadata()

        # Add devices
        device_metadata = metadata.get("Devices", [])
        for device in device_metadata:
            if device["name"] not in nwbfile.devices:
                nwbfile.create_device(**device)

        if stub_test:
            end_time = self.recording_extractor.get_end_time()
            end_time = min(end_time, 0.100)
            recording = self.recording_extractor.time_slice(start_time=0, end_time=end_time)
        else:
            recording = self.recording_extractor

        channel_names = recording.get_property(key="channel_names")
        segment_index = 0
        analog_data_iterator = _recording_traces_to_hdmf_iterator(
            recording=recording,
            segment_index=segment_index,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
        )

        name = self.source_data["time_series_key"]
        description = f"Analog data from OpenEphys. Channels are {channel_names} in that order."
        time_series_kwargs = dict(name=name, data=analog_data_iterator, unit="a.u.", description=description)

        if always_write_timestamps:
            timestamps = recording.get_times(segment_index=segment_index)
            shifted_timestamps = timestamps
            time_series_kwargs.update(timestamps=shifted_timestamps)
        else:
            recording_has_timestamps = recording.has_time_vector(segment_index=segment_index)
            if recording_has_timestamps:
                timestamps = recording.get_times(segment_index=segment_index)
                rate = calculate_regular_series_rate(series=timestamps)
                recording_t_start = timestamps[0]
            else:
                rate = recording.get_sampling_frequency()
                recording_t_start = recording._recording_segments[segment_index].t_start or 0

            if rate:
                starting_time = float(recording_t_start)
                time_series_kwargs.update(starting_time=starting_time, rate=recording.get_sampling_frequency())
            else:
                shifted_timestamps = timestamps
                time_series_kwargs.update(timestamps=shifted_timestamps)

        time_series = TimeSeries(**time_series_kwargs)
        nwbfile.add_acquisition(time_series)
