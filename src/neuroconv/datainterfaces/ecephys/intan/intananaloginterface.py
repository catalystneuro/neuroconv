from pathlib import Path

from pydantic import FilePath
from pynwb import NWBFile

from ....basedatainterface import BaseDataInterface
from ....utils import DeepDict, get_json_schema_from_method_signature


class IntanAnalogInterface(BaseDataInterface):
    """
    Primary data interface for converting non-amplifier analog data streams from Intan .rhd or .rhs files.

    This interface handles several types of analog signals that are not the primary neural recording channels,
    including auxiliary inputs, ADC inputs, and DC amplifier signals.

    If your data consists of the main amplifier channels (neural data), you should use the
    :py:class:`~neuroconv.datainterfaces.ecephys.intan.intandatainterface.IntanRecordingInterface`.
    """

    display_name = "Intan Analog"
    keywords = ("intan", "analog", "auxiliary", "ADC", "DC amplifier", "rhd", "rhs")
    associated_suffixes = (".rhd", ".rhs")
    info = "Interface for converting Intan non-amplifier analog data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__)
        source_schema["properties"]["file_path"]["description"] = "Path to either a .rhd or a .rhs file"
        return source_schema

    def __init__(
        self,
        file_path: FilePath,
        stream_name: str,
        verbose: bool = False,
        metadata_key: str = "TimeSeriesAnalogIntan",
    ):
        """
        Load and prepare analog data from Intan format (.rhd or .rhs files).

        Parameters
        ----------
        file_path : FilePath
            Path to either a rhd or a rhs file
        stream_name : str
            The stream name to load. Valid options include:
            - "RHD2000 auxiliary input channel": Auxiliary input channels (e.g., accelerometer data)
            - "RHD2000 supply voltage channel": Supply voltage channels
            - "USB board ADC input channel": ADC input channels (analog signals -10V to +10V)
            - "USB board ADC output channel": ADC output channels (analog signals -10V to +10V)
            - "DC Amplifier channel": DC amplifier channels (RHS system only)
        verbose : bool, default: False
            Verbose output
        metadata_key : str, default: "TimeSeriesAnalogIntan"
            Key for the TimeSeries metadata in the metadata dictionary.
        """
        from spikeinterface.extractors import read_intan

        self._file_path = Path(file_path)
        self._stream_name = stream_name
        self.metadata_key = metadata_key

        # Stream type descriptions and time series name mapping
        self.stream_info = {
            "RHD2000 auxiliary input channel": {
                "description": "RHD2000 auxiliary input channels (e.g., accelerometer data)",
                "time_series_name": "TimeSeriesIntanAuxiliary",
            },
            "RHD2000 supply voltage channel": {
                "description": "RHD2000 supply voltage channels",
                "time_series_name": "TimeSeriesIntanSupplyVoltage",
            },
            "USB board ADC input channel": {
                "description": "USB board ADC input channels (analog signals -10V to +10V)",
                "time_series_name": "TimeSeriesIntanADCInput",
            },
            "USB board ADC output channel": {
                "description": "USB board ADC output channels (analog signals -10V to +10V)",
                "time_series_name": "TimeSeriesIntanADCOutput",
            },
            "DC Amplifier channel": {
                "description": "DC amplifier channels (RHS system)",
                "time_series_name": "TimeSeriesIntanDC",
            },
        }

        # Validate stream_name
        if self._stream_name not in self.stream_info:
            raise ValueError(
                f"Invalid stream_name '{self._stream_name}'. "
                f"Valid analog stream names are: {list(self.stream_info.keys())}"
            )

        # Generate time series name
        self._time_series_name = self.stream_info[self._stream_name]["time_series_name"]

        # Load the recording extractor using stream_name
        self.recording_extractor = read_intan(
            file_path=self._file_path,
            stream_name=self._stream_name,
            all_annotations=True,
        )

        super().__init__(
            file_path=self._file_path,
            stream_name=self._stream_name,
            verbose=verbose,
        )

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        # Add device metadata (reuse from main Intan interface)
        system = self._file_path.suffix  # .rhd or .rhs
        device_description = {".rhd": "RHD Recording System", ".rhs": "RHS Stim/Recording System"}[system]

        intan_device = dict(
            name="Intan",
            description=device_description,
            manufacturer="Intan",
        )
        metadata["Devices"] = [intan_device]

        # Add TimeSeries metadata
        channel_names = self.get_channel_names()
        description = (
            f"{self.stream_info[self._stream_name]['description']}. " f"Channels are {channel_names} in that order."
        )

        metadata["TimeSeries"] = {
            self.metadata_key: dict(
                name=self._time_series_name,
                description=description,
            )
        }

        return metadata

    def get_channel_names(self) -> list[str]:
        """
        Get a list of channel names from the recording extractor.

        Returns
        -------
        list of str
            The names of all channels in the analog recording.
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
        Add analog channel data to an NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the analog data will be added
        metadata : dict, optional
            Metadata dictionary with device information. If None, uses default metadata
        stub_test : bool, default: False
            If True, only writes a small amount of data for testing
        iterator_type : str, optional, default: "v2"
            Type of iterator to use for data streaming
        iterator_opts : dict, optional
            Additional options for the iterator
        always_write_timestamps : bool, default: False
            If True, always writes timestamps instead of using sampling rate
        """
        from ....tools.spikeinterface import (
            _stub_recording,
            add_recording_as_time_series_to_nwbfile,
        )

        if metadata is None:
            metadata = self.get_metadata()

        recording = self.recording_extractor
        if stub_test:
            recording = _stub_recording(recording=recording)

        # Update metadata with description
        channel_names = self.get_channel_names()
        description = (
            f"{self.stream_info[self._stream_name]['description']}. " f"Channels are {channel_names} in that order."
        )
        metadata["TimeSeries"][self._time_series_name] = dict(description=description)

        add_recording_as_time_series_to_nwbfile(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
            always_write_timestamps=always_write_timestamps,
            time_series_name=self._time_series_name,
        )
