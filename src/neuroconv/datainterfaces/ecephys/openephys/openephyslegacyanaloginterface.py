from pydantic import ConfigDict, DirectoryPath, validate_call

from .openephyslegacydatainterface import _get_session_start_time
from ..baserecordingastimeseriesinterface import BaseRecordingAsTimeSeriesInterface
from ....utils import DeepDict, get_json_schema_from_method_signature


class OpenEphysLegacyAnalogInterface(BaseRecordingAsTimeSeriesInterface):
    """
    Data interface for the analog inputs of the acquisition board in a legacy Open Ephys recording (.continuous files).

    A legacy recording keeps the analog inputs of the acquisition board (``ADC1`` to ``ADC8``) next to the
    electrodes, and python-neo reads them as their own stream, ``"Signals ADC"``. They are written as one
    ``TimeSeries``. For the electrode channels use
    :py:class:`~neuroconv.datainterfaces.OpenEphysLegacyRecordingInterface`.
    """

    display_name = "OpenEphys Legacy Analog Recording"
    keywords = ("OpenEphys", "analog", "ADC")
    associated_suffixes = (".continuous", ".openephys", ".xml")
    info = "Interface for the analog inputs of the acquisition board in legacy OpenEphys recordings."

    # The stream python-neo reads the analog inputs of the acquisition board into
    _stream_name = "Signals ADC"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__)
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to directory containing OpenEphys legacy files."
        return source_schema

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        block_index: int | None = None,
        verbose: bool = False,
        metadata_key: str | None = None,
        channels_to_include: list[str] | None = None,
    ):
        """
        Read the analog inputs of the acquisition board in a legacy Open Ephys recording.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder holding the ``.continuous`` files.
        block_index : int, optional, default: None
            The index of the block to extract from the data.
        verbose : bool, default: False
            Verbose output.
        metadata_key : str, optional
            Key for the TimeSeries metadata in the metadata dictionary. This addresses the entry; the written
            object's name is the entry's ``name`` field. Defaults to ``"open_ephys_legacy_adc"``.
        channels_to_include : list of str, optional
            Channels to convert, by the names in ``get_channel_names()`` (such as ``"ADC1"``), written in the order
            listed. Every channel is converted when omitted. A name that is not one of the interface's channels
            raises.
        """
        from spikeinterface.extractors.extractor_classes import (
            OpenEphysLegacyRecordingExtractor,
        )

        available_stream_names, _ = OpenEphysLegacyRecordingExtractor.get_streams(folder_path=folder_path)
        if self._stream_name not in available_stream_names:
            raise ValueError(
                f"The folder '{folder_path}' holds no analog inputs of the acquisition board (stream "
                f"'{self._stream_name}'). Its streams are {available_stream_names}."
            )

        self.metadata_key = metadata_key or "open_ephys_legacy_adc"
        self.recording_extractor = OpenEphysLegacyRecordingExtractor(
            folder_path=folder_path,
            stream_name=self._stream_name,
            block_index=block_index,
            use_names_as_ids=True,
        )
        # The reader carries the session start time; read it now, as `channels_to_include` replaces the
        # recording with a channel slice that does not carry it
        self._session_start_time = _get_session_start_time(neo_reader=self.recording_extractor.neo_reader)

        super().__init__(
            folder_path=folder_path,
            block_index=block_index,
            verbose=verbose,
            metadata_key=metadata_key,
            channels_to_include=channels_to_include,
        )

        self._include_channels(channels_to_include)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        if self._session_start_time is not None:
            metadata["NWBFile"].update(session_start_time=self._session_start_time)

        channel_names = [str(channel_name) for channel_name in self.get_channel_names()]
        metadata["TimeSeries"][self.metadata_key] = dict(
            name="TimeSeriesOpenEphysLegacyADC",
            description=(
                f"Analog data acquired with the OpenEphys legacy format, stream '{self._stream_name}'. "
                f"Channels are {channel_names} in that order."
            ),
        )

        return metadata
