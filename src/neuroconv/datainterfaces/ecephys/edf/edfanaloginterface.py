from pathlib import Path

from pydantic import FilePath
from pynwb import NWBFile

from ....basedatainterface import BaseDataInterface
from ....utils import DeepDict, get_json_schema_from_method_signature


class EDFAnalogInterface(BaseDataInterface):
    """
    Primary data interface for converting auxiliary data streams from EDF files.

    This interface is designed to handle all the signals that should NOT be stored as ElectricalSeries,
    including physiological monitoring signals, triggers and any other auxiliary data which does not
    come from electrode channels.

    If your data consists of electrical recording channels you should use the
    :py:class:`~neuroconv.datainterfaces.ecephys.edf.edfdatainterface.EDFRecordingInterface`.
    """

    display_name = "EDF Analog"
    keywords = ("edf", "analog", "physiological", "trigger", "auxiliary")
    associated_suffixes = (".edf",)
    info = "Interface for converting EDF analog data (from auxiliary channels)."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__)
        source_schema["properties"]["file_path"]["description"] = "Path to the .edf file."
        return source_schema

    @staticmethod
    def get_available_channel_ids(file_path: FilePath) -> list:
        """
        Get all available channel names from an EDF file.

        Parameters
        ----------
        file_path : FilePath
            Path to the EDF file

        Returns
        -------
        list
            List of all channel names in the EDF file
        """
        from spikeinterface.extractors import read_edf

        recording = read_edf(file_path=file_path, all_annotations=True, use_names_as_ids=True)
        channel_ids = recording.get_channel_ids()

        # Clean up to avoid dangling references
        del recording

        return channel_ids.tolist()

    def __init__(
        self,
        *,
        file_path: FilePath,
        channels_to_include: list[str] | None = None,
        verbose: bool = False,
        metadata_key: str = "analog_edf_metadata_key",
    ):
        """
        Load and prepare analog data from EDF format.

        Parameters
        ----------
        file_path : FilePath
            Path to the EDF file
        channels_to_include : list of str, optional
            Specific channel IDs to include.
        verbose : bool, default: False
            Verbose output
        metadata_key : str, default: "analog_edf_metadata_key"
            Key for the TimeSeries metadata in the metadata dictionary.
        """
        from spikeinterface.extractors import read_edf

        self._file_path = Path(file_path)
        self.metadata_key = metadata_key

        full_recording = read_edf(file_path=self._file_path, all_annotations=True, use_names_as_ids=True)

        # Validate that the requested channels exist
        self._channels_to_include = channels_to_include or full_recording.get_channel_ids().tolist()
        available_channels = full_recording.get_channel_ids().astype(str)
        missing_channels = set(self._channels_to_include) - set(available_channels)
        if missing_channels:
            error_msg = (
                f"Channels not found in EDF file: {missing_channels}. "
                f"Available channels: {list(available_channels)}"
            )
            raise ValueError(error_msg)

        # Extract only the analog channels
        self.recording_extractor = full_recording.select_channels(channel_ids=self._channels_to_include)

        super().__init__(
            file_path=self._file_path,
            channels_to_include=self._channels_to_include,
            verbose=verbose,
        )

    @property
    def channel_ids(self):
        """Gets the channel ids of the data."""
        return self.recording_extractor.get_channel_ids()

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        # Add TimeSeries metadata
        channel_names = self.channel_ids
        channels_string = ", ".join(channel_names)
        description = f"Auxiliary signals from the EDF format. Channels: {channels_string}"

        metadata["TimeSeries"] = {
            self.metadata_key: dict(
                name="TimeSeriesAnalogEDF",
                description=description,
            )
        }

        return metadata

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

        add_recording_as_time_series_to_nwbfile(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
            always_write_timestamps=always_write_timestamps,
            metadata_key=self.metadata_key,
        )
