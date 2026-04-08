from pathlib import Path

from pydantic import FilePath
from pynwb import NWBFile

from ....basedatainterface import BaseDataInterface
from ....utils import DeepDict, get_json_schema_from_method_signature


class IntanStimInterface(BaseDataInterface):
    """
    Data interface for converting electrical stimulation data from Intan .rhs files.

    This interface handles the stimulation current channels recorded by the RHS2000
    Stim/Recording system. Stimulation data is stored as current in Amperes, with one
    stim channel per corresponding amplifier channel.

    This interface is only compatible with .rhs files. For the main amplifier channels,
    use :py:class:`~neuroconv.datainterfaces.ecephys.intan.intandatainterface.IntanRecordingInterface`.
    For other analog streams (ADC, DC amplifier, auxiliary), use
    :py:class:`~neuroconv.datainterfaces.ecephys.intan.intananaloginterface.IntanAnalogInterface`.
    """

    display_name = "Intan Stimulation"
    keywords = ("intan", "stimulation", "stim", "rhs", "current")
    associated_suffixes = (".rhs",)
    info = "Interface for converting Intan RHS electrical stimulation data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__)
        source_schema["properties"]["file_path"]["description"] = "Path to an Intan .rhs file"
        return source_schema

    def __init__(
        self,
        file_path: FilePath,
        *,
        verbose: bool = False,
        metadata_key: str = "TimeSeriesIntanStim",
    ):
        """
        Load and prepare stimulation data from an Intan .rhs file.

        Parameters
        ----------
        file_path : FilePath
            Path to an Intan .rhs file. Only .rhs files are supported because
            stimulation channels are exclusive to the RHS Stim/Recording System.
        verbose : bool, default: False
            Verbose output.
        metadata_key : str, default: "TimeSeriesIntanStim"
            Key for the TimeSeries metadata in the metadata dictionary.
        """
        from spikeinterface.extractors import read_intan

        self._file_path = Path(file_path)

        if self._file_path.suffix != ".rhs":
            raise ValueError(
                f"IntanStimInterface only supports .rhs files (RHS Stim/Recording System). "
                f"Got: '{self._file_path.suffix}'. "
                "Stimulation channels are not available in .rhd files."
            )

        self._stream_name = "Stim channel"
        self.metadata_key = metadata_key

        self.recording_extractor = read_intan(
            file_path=self._file_path,
            stream_name=self._stream_name,
            all_annotations=True,
        )

        super().__init__(
            file_path=self._file_path,
            verbose=verbose,
        )

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        intan_device = dict(
            name="Intan",
            description="RHS Stim/Recording System",
            manufacturer="Intan",
        )
        metadata["Devices"] = [intan_device]

        channel_names = self.get_channel_names()
        description = (
            "Electrical stimulation current channels (RHS Stim/Recording System). "
            f"Data are in Amperes. Channels are {channel_names} in that order."
        )

        metadata["TimeSeries"] = {
            self.metadata_key: dict(
                name="TimeSeriesIntanStim",
                description=description,
            )
        }

        return metadata

    def get_channel_names(self) -> list[str]:
        """
        Get a list of channel names from the stimulation recording.

        Channel names follow the pattern ``{amplifier_channel}_STIM``
        (e.g., ``A-000_STIM``), matching the corresponding amplifier channels.

        Returns
        -------
        list of str
            The names of all stimulation channels.
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
        always_write_timestamps: bool = False,
    ):
        """
        Add stimulation channel data to an NWB file.

        Stimulation data are stored as a ``TimeSeries`` in acquisition with
        ``unit="A"`` (Amperes). The conversion factor is automatically derived
        from the ``stim_step_size`` recorded in the .rhs file header.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the stimulation data will be added.
        metadata : dict, optional
            Metadata dictionary. If None, uses default metadata from ``get_metadata()``.
        stub_test : bool, default: False
            If True, only writes a small amount of data for testing.
        iterator_type : str, optional, default: "v2"
            Type of iterator to use for data streaming.
        iterator_options : dict, optional
            Additional options for the iterator.
        always_write_timestamps : bool, default: False
            If True, always writes timestamps instead of using sampling rate.
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
            iterator_options=iterator_options,
            always_write_timestamps=always_write_timestamps,
            metadata_key=self.metadata_key,
        )
