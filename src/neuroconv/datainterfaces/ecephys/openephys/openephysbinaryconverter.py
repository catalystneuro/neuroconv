from pathlib import Path

from pydantic import DirectoryPath, validate_call

from .openephybinarysanaloginterface import OpenEphysBinaryAnalogInterface
from .openephysbinarydatainterface import OpenEphysBinaryRecordingInterface
from ....nwbconverter import ConverterPipe
from ....utils import get_json_schema_from_method_signature


class OpenEphysBinaryConverter(ConverterPipe):
    """
    Converter for multi-stream OpenEphys binary recording data.

    Auto-discovers all streams in a folder and creates the appropriate interfaces
    (recording for neural streams, analog for ADC/NI-DAQ streams).
    """

    display_name = "OpenEphys Binary Converter"
    keywords = OpenEphysBinaryRecordingInterface.keywords + OpenEphysBinaryAnalogInterface.keywords
    associated_suffixes = OpenEphysBinaryRecordingInterface.associated_suffixes
    info = "Converter for multi-stream OpenEphys binary recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["streams"])
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to the folder containing OpenEphys binary streams."
        return source_schema

    @classmethod
    def get_streams(cls, folder_path: DirectoryPath) -> list[str]:
        """
        Get the stream names available in the folder.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing OpenEphys binary streams.

        Returns
        -------
        list of str
            The names of all available streams in the folder.
        """
        from spikeinterface.extractors.extractor_classes import (
            OpenEphysBinaryRecordingExtractor,
        )

        return OpenEphysBinaryRecordingExtractor.get_streams(folder_path=folder_path)[0]

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        streams: list[str] | None = None,
        verbose: bool = False,
    ):
        """
        Read all data from multiple streams stored in OpenEphys binary format.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing OpenEphys binary streams.
        streams : list of str, optional
            A specific list of streams to load.
            To see which streams are available, run
            `OpenEphysBinaryConverter.get_streams(folder_path="path/to/openephys")`.
            By default, all available streams are loaded.
        verbose : bool, default: False
            Whether to output verbose text.
        """
        folder_path = Path(folder_path)

        stream_names = streams or self.get_streams(folder_path=folder_path)
        self._stream_names = stream_names

        non_neural_indicators = ["ADC", "NI-DAQ"]
        is_non_neural = lambda name: any(indicator in name for indicator in non_neural_indicators)
        _to_suffix = lambda name: name.rsplit(".", maxsplit=1)[-1].replace("-", "")
        neural_streams = [name for name in stream_names if not is_non_neural(name)]
        analog_streams = [name for name in stream_names if is_non_neural(name)]

        data_interfaces = {}

        for stream_name in neural_streams:
            es_key = "ElectricalSeries" + _to_suffix(stream_name)
            data_interfaces[stream_name] = OpenEphysBinaryRecordingInterface(
                folder_path=folder_path,
                stream_name=stream_name,
                es_key=es_key,
            )

        for stream_name in analog_streams:
            time_series_name = "TimeSeries" + _to_suffix(stream_name)
            data_interfaces[stream_name] = OpenEphysBinaryAnalogInterface(
                folder_path=folder_path,
                stream_name=stream_name,
                time_series_name=time_series_name,
            )

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

    def get_conversion_options_schema(self) -> dict:
        conversion_options_schema = super().get_conversion_options_schema()
        conversion_options_schema["properties"].update(
            {name: interface.get_conversion_options_schema() for name, interface in self.data_interface_objects.items()}
        )
        return conversion_options_schema
