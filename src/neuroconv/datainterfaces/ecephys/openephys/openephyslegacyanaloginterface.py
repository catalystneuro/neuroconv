from pydantic import ConfigDict, DirectoryPath, validate_call

from .openephyslegacydatainterface import _get_session_start_time
from ..baserecordingastimeseriesinterface import BaseRecordingAsTimeSeriesInterface
from ....utils import DeepDict, get_json_schema_from_method_signature


class OpenEphysLegacyAnalogInterface(BaseRecordingAsTimeSeriesInterface):
    """
    Data interface for the analog channels of a legacy Open Ephys recording (.continuous files).

    A legacy recording keeps two kinds of analog channels next to the electrodes, which python-neo reads as their
    own streams: the analog inputs of the acquisition board (``ADC1`` to ``ADC8``, stream ``"Signals ADC"``) and
    the auxiliary inputs of each headstage, usually its accelerometer (``AUX1`` to ``AUX3`` per headstage, stream
    ``"Signals AUX"``). Each stream is written as one ``TimeSeries``. For the electrode channels use
    :py:class:`~neuroconv.datainterfaces.OpenEphysLegacyRecordingInterface`.
    """

    display_name = "OpenEphys Legacy Analog Recording"
    keywords = ("OpenEphys", "analog", "ADC", "AUX")
    associated_suffixes = (".continuous", ".openephys", ".xml")
    info = "Interface for the analog and auxiliary channels of legacy OpenEphys recordings."

    # The analog streams python-neo reads from a legacy folder, with the name of the series each is written as
    _stream_name_to_time_series_name = {
        "Signals ADC": "TimeSeriesOpenEphysLegacyADC",
        "Signals AUX": "TimeSeriesOpenEphysLegacyAUX",
    }

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
        stream_name: str | None = None,
        block_index: int | None = None,
        verbose: bool = False,
        metadata_key: str | None = None,
        channels_to_include: list[str] | None = None,
    ):
        """
        Read the analog channels of a legacy Open Ephys recording.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder holding the ``.continuous`` files.
        stream_name : {"Signals ADC", "Signals AUX"}, optional
            The analog stream to read. Only required when the folder holds both.
        block_index : int, optional, default: None
            The index of the block to extract from the data.
        verbose : bool, default: False
            Verbose output.
        metadata_key : str, optional
            Key for the TimeSeries metadata in the metadata dictionary. This addresses the entry; the written
            object's name is the entry's ``name`` field. Defaults to ``"open_ephys_legacy_adc"`` or
            ``"open_ephys_legacy_aux"``, after the stream, so one interface per stream can share a conversion.
        channels_to_include : list of str, optional
            Channels to convert, by the names in ``get_channel_names()`` (such as ``"ADC1"``), written in the order
            listed. Every channel is converted when omitted. A name that is not one of the interface's channels
            raises.
        """
        from spikeinterface.extractors.extractor_classes import (
            OpenEphysLegacyRecordingExtractor,
        )

        available_stream_names, _ = OpenEphysLegacyRecordingExtractor.get_streams(folder_path=folder_path)
        analog_stream_names = [name for name in available_stream_names if name in self._stream_name_to_time_series_name]
        if not analog_stream_names:
            raise ValueError(
                f"The folder '{folder_path}' holds no analog streams. Its streams are {available_stream_names}."
            )
        if stream_name is None:
            if len(analog_stream_names) > 1:
                raise ValueError(
                    f"The folder holds more than one analog stream, {analog_stream_names}. "
                    "Choose one with the `stream_name` argument."
                )
            stream_name = analog_stream_names[0]
        elif stream_name not in analog_stream_names:
            raise ValueError(
                f"The stream '{stream_name}' is not an analog stream of this folder. Its analog streams are "
                f"{analog_stream_names}. For the electrode channels use `OpenEphysLegacyRecordingInterface`."
            )

        self._stream_name = stream_name
        self.metadata_key = metadata_key or f"open_ephys_legacy_{stream_name.split()[-1].lower()}"
        self.recording_extractor = OpenEphysLegacyRecordingExtractor(
            folder_path=folder_path,
            stream_name=stream_name,
            block_index=block_index,
            use_names_as_ids=True,
        )
        # The reader carries the session start time; read it now, as `channels_to_include` replaces the
        # recording with a channel slice that does not carry it
        self._session_start_time = _get_session_start_time(neo_reader=self.recording_extractor.neo_reader)

        super().__init__(
            folder_path=folder_path,
            stream_name=stream_name,
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
            name=self._stream_name_to_time_series_name[self._stream_name],
            description=(
                f"Analog data acquired with the OpenEphys legacy format, stream '{self._stream_name}'. "
                f"Channels are {channel_names} in that order."
            ),
        )

        return metadata
