import warnings
from pathlib import Path

from pydantic import FilePath
from pynwb import NWBFile

from ..baserecordingtotimeseriesinterface import BaseRecordingToTimeSeriesInterface
from ....utils import get_json_schema_from_method_signature


class EDFAnalogInterface(BaseRecordingToTimeSeriesInterface):
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

    @classmethod
    def get_stream_names(cls, file_path: FilePath) -> list[str]:
        """
        Get the names of the streams available in an EDF file.

        A stream is a set of channels that share a sampling rate, so a file that sampled some of
        its signals at a different rate than the rest carries more than one.

        Parameters
        ----------
        file_path : FilePath
            Path to the EDF file

        Returns
        -------
        list of str
            List of the stream names in the EDF file
        """
        from spikeinterface.extractors.extractor_classes import EDFRecordingExtractor

        stream_names, _ = EDFRecordingExtractor.get_streams(file_path=file_path)
        return stream_names

    @staticmethod
    def get_available_channel_ids(file_path: FilePath) -> list:
        """
        Get all available channel names from an EDF file.

        The names span the whole file. A file that sampled some of its signals at a different rate
        than the rest holds them in separate streams, and an interface reads one stream at a time, so
        the channels of the stream it holds are a subset of these. They are read from the file's
        header, so this works on a file with more than one stream.

        Parameters
        ----------
        file_path : FilePath
            Path to the EDF file

        Returns
        -------
        list
            List of all channel names in the EDF file
        """
        from pyedflib import EdfReader

        edf_reader = EdfReader(str(file_path))
        try:
            channel_names = edf_reader.getSignalLabels()
        finally:
            # EDFlib refuses to open a file it already has open, so the handle is released here
            # rather than left to garbage collection.
            edf_reader.close()

        return channel_names

    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        channels_to_include: list[str] | None = None,
        verbose: bool = False,
        metadata_key: str = "edf_analog",
        stream_name: str | None = None,
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
        metadata_key : str, default: "edf_analog"
            Key for the TimeSeries metadata in the metadata dictionary. This addresses the entry;
            the written object's name is the entry's ``name`` field.
        stream_name : str, optional
            Name of the stream the channels are read from, as returned by ``get_stream_names``. A file
            that sampled some of its signals at a different rate than the rest carries more than one
            stream and cannot be read without naming one, since a single recording holds a single
            sampling rate.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "channels_to_include",
                "verbose",
                "metadata_key",
            ]
            num_positional_args_before_args = 1  # file_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to EDFAnalogInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            channels_to_include = positional_values.get("channels_to_include", channels_to_include)
            verbose = positional_values.get("verbose", verbose)
            metadata_key = positional_values.get("metadata_key", metadata_key)

        from spikeinterface.extractors import read_edf

        self._file_path = Path(file_path)
        self.metadata_key = metadata_key

        full_recording = read_edf(
            file_path=self._file_path, stream_name=stream_name, all_annotations=True, use_names_as_ids=True
        )

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
            stream_name=stream_name,
        )

    def _get_time_series_name(self) -> str:
        return "TimeSeriesAnalogEDF"

    def _get_time_series_description(self) -> str:
        channels_string = ", ".join(self.get_channel_names())
        return f"Auxiliary signals from the EDF format. Channels: {channels_string}"

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        stub_test: bool = False,
        iterator_type: str | None = "v2",
        iterator_options: dict | None = None,
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
        iterator_options : dict, optional
            Additional options for the iterator
        always_write_timestamps : bool, default: False
            If True, always writes timestamps instead of using sampling rate
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "stub_test",
                "iterator_type",
                "iterator_options",
                "always_write_timestamps",
            ]
            num_positional_args_before_args = 2  # nwbfile, metadata
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"add_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                    f"{len(args) + num_positional_args_before_args} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to EDFAnalogInterface.add_to_nwbfile() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            stub_test = positional_values.get("stub_test", stub_test)
            iterator_type = positional_values.get("iterator_type", iterator_type)
            iterator_options = positional_values.get("iterator_options", iterator_options)
            always_write_timestamps = positional_values.get("always_write_timestamps", always_write_timestamps)

        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
            always_write_timestamps=always_write_timestamps,
        )
