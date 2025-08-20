from pathlib import Path

from pydantic import FilePath
from pynwb import NWBFile

from ....basedatainterface import BaseDataInterface
from ....utils import DeepDict, get_json_schema_from_method_signature


class EDFAnalogInterface(BaseDataInterface):
    """
    Primary data interface for converting non-electrical analog data streams from EDF files.

    This interface handles non-electrical signals that should not be stored as ElectricalSeries,
    including physiological monitoring signals, triggers, and auxiliary data.

    If your data consists of electrical recording channels (neural data), you should use the
    :py:class:`~neuroconv.datainterfaces.ecephys.edf.edfdatainterface.EDFRecordingInterface`.
    """

    display_name = "EDF Analog"
    keywords = ("edf", "analog", "physiological", "trigger", "auxiliary")
    associated_suffixes = (".edf",)
    info = "Interface for converting EDF non-electrical analog data."

    # Class variable to track instances for unique naming
    _instance_counter = 0

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__)
        source_schema["properties"]["file_path"]["description"] = "Path to the .edf file."
        return source_schema

    def __init__(
        self,
        *,
        file_path: FilePath,
        channels_to_include: list[str] | None = None,
        verbose: bool = False,
        metadata_key: str = "TimeSeriesAnalogEDF",
    ):
        """
        Load and prepare analog data from EDF format.

        Parameters
        ----------
        file_path : FilePath
            Path to the EDF file
        channels_to_include : list of str, optional
            Specific channel IDs to include. If None, will include all non-electrical channels.
        verbose : bool, default: False
            Verbose output
        metadata_key : str, default: "TimeSeriesAnalogEDF"
            Key for the TimeSeries metadata in the metadata dictionary.
        """
        from spikeinterface.extractors import read_edf

        self._file_path = Path(file_path)
        self.metadata_key = metadata_key

        # Load the full recording first
        full_recording = read_edf(file_path=self._file_path, all_annotations=True, use_names_as_ids=True)

        # Determine which channels to include
        if channels_to_include is None:
            # Auto-detect non-electrical channels based on physical units
            physical_units = full_recording.get_property("physical_unit")
            channel_ids = full_recording.get_channel_ids()
            channels_to_include = [str(ch_id) for ch_id, unit in zip(channel_ids, physical_units) if unit != "uV"]

            if not channels_to_include:
                raise ValueError(
                    "No non-electrical channels found in the EDF file. "
                    "All channels have 'uV' units. Use EDFRecordingInterface instead."
                )

        self._channels_to_include = channels_to_include

        # Validate that the requested channels exist
        available_channels = full_recording.get_channel_ids().astype(str)
        missing_channels = set(self._channels_to_include) - set(available_channels)
        if missing_channels:
            raise ValueError(f"Channels not found in EDF file: {missing_channels}")

        # Extract only the analog channels
        self.recording_extractor = full_recording.select_channels(channel_ids=self._channels_to_include)

        # Generate unique default TimeSeries name - users can override via metadata
        EDFAnalogInterface._instance_counter += 1
        if EDFAnalogInterface._instance_counter == 1:
            self._time_series_name = "TimeSeriesEDF"
        else:
            self._time_series_name = f"TimeSeriesEDF{EDFAnalogInterface._instance_counter}"

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
        channel_units = self.recording_extractor.get_property("physical_unit")

        description = (
            f"Non-electrical analog signals from EDF file. "
            f"Channels: {', '.join([f'{name} ({unit})' for name, unit in zip(channel_names, channel_units)])}"
        )

        metadata["TimeSeries"] = {
            self.metadata_key: dict(
                name=self._time_series_name,
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

        # Get the name from metadata if available, otherwise use default
        time_series_name = metadata.get("TimeSeries", {}).get(self.metadata_key, {}).get("name", self._time_series_name)

        add_recording_as_time_series_to_nwbfile(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
            always_write_timestamps=always_write_timestamps,
            time_series_name=time_series_name,
        )
