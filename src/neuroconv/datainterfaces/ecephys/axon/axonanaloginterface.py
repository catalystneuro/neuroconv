from pathlib import Path

from pydantic import ConfigDict, FilePath, validate_call

from .axondatainterface import _get_start_datetime
from ..baserecordingastimeseriesinterface import BaseRecordingAsTimeSeriesInterface
from ....utils import DeepDict, get_json_schema_from_method_signature


class AxonAnalogInterface(BaseRecordingAsTimeSeriesInterface):
    """
    Data interface for the non-neural channels of an Axon Binary Format (ABF) file, written as a ``TimeSeries``.

    An ABF file records every input of the digitizer in one stream, so the channels a lab wants as plain signals
    (a stimulus monitor, a temperature probe, a force transducer, an optical channel) sit next to the cells and
    the extracellular channels. Name the ones that belong together with ``channels_to_include``. For a cell use
    :py:class:`~neuroconv.datainterfaces.AxonIntracellularInterface`, and for extracellular channels
    :py:class:`~neuroconv.datainterfaces.AxonRecordingInterface`.
    """

    display_name = "Axon Analog"
    keywords = ("axon", "abf", "analog")
    associated_suffixes = (".abf",)
    info = "Interface for the non-neural channels of Axon Binary Format (ABF) recordings."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__)
        source_schema["properties"]["file_path"]["description"] = "Path to an Axon Binary Format (.abf) file."
        return source_schema

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __init__(
        self,
        file_path: FilePath,
        *,
        verbose: bool = False,
        metadata_key: str = "axon_analog",
        channels_to_include: list[str] | None = None,
    ):
        """
        Read the channels of an Axon Binary Format file to write as a ``TimeSeries``.

        Parameters
        ----------
        file_path : FilePath
            Path to an Axon Binary Format (.abf) file.
        verbose : bool, default: False
            Verbose output.
        metadata_key : str, default: "axon_analog"
            Key for the TimeSeries metadata in the metadata dictionary. This addresses the entry; the written
            object's name is the entry's ``name`` field.
        channels_to_include : list of str, optional
            Channels to convert, by the names the file stores (as Clampex shows them, without spaces, such as
            ``"Tmp"`` or ``"IN7"``), written in the order listed. A channel with no stored name is ``ch{index}``.
            Every channel is converted when omitted. A name that is not one of the file's channels raises.
        """
        from spikeinterface.extractors.extractor_classes import AxonRecordingExtractor

        self._file_path = Path(file_path)
        self.metadata_key = metadata_key

        recording = AxonRecordingExtractor(file_path=self._file_path)
        neo_reader = recording.neo_reader
        # Read from the reader before the channels are renamed, as the renamed recording does not carry it
        self._session_start_time = _get_start_datetime(neo_reader)

        # neo numbers the channels; address them by the names the file stores. Interior spaces are removed so a
        # channel keeps one spelling across neo versions (``IN0`` below neo 0.15, ``IN 0`` from it), as in
        # `AxonIntracellularInterface`, and a blank name gets a ``ch{index}`` fallback.
        channel_names = []
        for index, channel in enumerate(neo_reader.header["signal_channels"]):
            channel_name = str(channel["name"]).replace(" ", "")
            channel_names.append(channel_name or f"ch{index}")
        self.recording_extractor = recording.rename_channels(new_channel_ids=channel_names)

        super().__init__(
            file_path=self._file_path,
            verbose=verbose,
            metadata_key=metadata_key,
            channels_to_include=channels_to_include,
        )

        self._include_channels(channels_to_include)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        metadata["NWBFile"].update(session_start_time=self._session_start_time)

        channel_names = [str(channel_name) for channel_name in self.get_channel_names()]
        metadata["TimeSeries"][self.metadata_key] = dict(
            name="TimeSeriesAxonAnalog",
            description=(
                f"Analog channels from an Axon Binary Format file. Channels are {channel_names} in that order."
            ),
        )

        return metadata
