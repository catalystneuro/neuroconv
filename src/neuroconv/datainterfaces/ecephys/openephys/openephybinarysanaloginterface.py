from typing import Optional

from pydantic import ConfigDict, DirectoryPath, validate_call
from pynwb import NWBFile

from ._openephys_utils import _get_session_start_time, _read_settings_xml
from ....basedatainterface import BaseDataInterface
from ....utils import (
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
        time_series_name: str = "TimeSeriesOpenEphysAnalog",
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
        time_series_name : str, default: "TimeSeriesOpenEphysAnalog"
            The name of the TimeSeries object in the NWBFile and also
            the key of the associated metadata
        """
        from spikeinterface.extractors import OpenEphysBinaryRecordingExtractor

        self.folder_path = folder_path
        self._xml_root = _read_settings_xml(folder_path)
        self.time_series_name = time_series_name

        available_streams = OpenEphysBinaryRecordingExtractor.get_streams(folder_path=folder_path)[0]
        availble_adc_streams = [id for id in available_streams if "ADC" in id]
        if len(availble_adc_streams) > 1 and stream_name is None:
            raise ValueError(
                "More than one stream is detected! "
                "Please specify which stream you wish to load with the `stream_name` argument. "
                "To see what streams are available, call "
                " `OpenEphysRecordingInterface.get_stream_names(folder_path=...)`."
            )
        if stream_name is not None and stream_name not in availble_adc_streams:
            raise ValueError(
                f"The selected stream '{stream_name}' is not in the available adc streams are '{availble_adc_streams}'!"
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
        from ....tools.spikeinterface import add_recording_as_time_series_to_nwbfile

        if metadata is None:
            metadata = self.get_metadata()

        if stub_test:
            end_time = self.recording_extractor.get_end_time()
            end_time = min(end_time, 0.100)
            recording = self.recording_extractor.time_slice(start_time=0, end_time=end_time)
        else:
            recording = self.recording_extractor

        description = (
            f"ADC data acquired with OpenEphys system. \n Channels are {self.get_channel_names()} in that order."
        )
        metadata["TimeSeries"][self.time_series_name] = dict(description=description)

        add_recording_as_time_series_to_nwbfile(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
            always_write_timestamps=always_write_timestamps,
            time_series_name=self.time_series_name,
        )
