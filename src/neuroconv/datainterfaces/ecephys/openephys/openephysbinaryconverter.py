import inspect
import re
from pathlib import Path

from pydantic import DirectoryPath, validate_call

from .openephybinarysanaloginterface import OpenEphysBinaryAnalogInterface
from .openephysbinarydatainterface import OpenEphysBinaryRecordingInterface
from ....nwbconverter import ConverterPipe
from ....tools.nwb_helpers import get_default_nwbfile_metadata
from ....utils import DeepDict, dict_deep_update, get_json_schema_from_method_signature


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
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["exclude_streams"])
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
        exclude_streams: list[str] | None = None,
        verbose: bool = False,
    ):
        """
        Read all data from every stream stored in OpenEphys binary format.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing OpenEphys binary streams.
        exclude_streams : list of str, optional
            Stream names to skip from auto-discovery. Useful for omitting a large
            stream (for example an LFP band) during a fast test conversion.
            ``OpenEphysBinaryConverter.get_streams(folder_path=...)`` lists what is
            available. Unknown names raise ``ValueError``.
        verbose : bool, default: False
            Whether to output verbose text.
        """
        folder_path = Path(folder_path)

        stream_names = self.get_streams(folder_path=folder_path)

        if exclude_streams:
            unknown = [name for name in exclude_streams if name not in stream_names]
            if unknown:
                raise ValueError(
                    f"Cannot exclude streams {unknown}: not present in {folder_path}. "
                    f"Available streams: {stream_names}."
                )
            stream_names = [name for name in stream_names if name not in exclude_streams]

        non_neural_indicators = ["ADC", "NI-DAQ"]
        is_non_neural = lambda name: any(indicator in name for indicator in non_neural_indicators)
        _to_suffix = lambda name: name.rsplit(".", maxsplit=1)[-1].replace("-", "")
        # The dict-based metadata key is a snake_case handle derived from the whole stream name. The interface
        # defaults it to a constant, which would collide across streams here, and the ``es_key`` suffix above is
        # not unique either: two record nodes can both end in ``.0``.
        _to_metadata_key = lambda name: re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
        neural_streams = [name for name in stream_names if not is_non_neural(name)]
        analog_streams = [name for name in stream_names if is_non_neural(name)]

        data_interfaces = {}

        # Each neural stream needs both a distinct entry and a distinct ElectricalSeries name: the interface
        # keys its entry by ``metadata_key`` but names every series "ElectricalSeries", which collides once a
        # session holds several streams. ``get_metadata`` below assigns the names.
        self._series_name_by_metadata_key = {
            _to_metadata_key(stream_name): "ElectricalSeries" + _to_suffix(stream_name)
            for stream_name in neural_streams
        }

        for stream_name in neural_streams:
            es_key = "ElectricalSeries" + _to_suffix(stream_name)
            data_interfaces[stream_name] = OpenEphysBinaryRecordingInterface(
                folder_path=folder_path,
                stream_name=stream_name,
                es_key=es_key,
                metadata_key=_to_metadata_key(stream_name),
            )

        for stream_name in analog_streams:
            time_series_name = "TimeSeries" + _to_suffix(stream_name)
            data_interfaces[stream_name] = OpenEphysBinaryAnalogInterface(
                folder_path=folder_path,
                stream_name=stream_name,
                time_series_name=time_series_name,
            )

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

    def get_metadata(self, *, use_new_metadata_format: bool = False) -> DeepDict:
        """
        Aggregate the metadata of every stream interface.

        Parameters
        ----------
        use_new_metadata_format : bool, default: False
            If True, the recording interfaces emit the dict-based format and each stream's
            ``ElectricalSeries`` entry is named after its stream, so several streams can be written to one
            NWB file. The interfaces themselves cannot do this: each one only knows that it is "the"
            Open Ephys recording, so they all name their series ``"ElectricalSeries"``.

        Returns
        -------
        DeepDict
            The metadata of all interfaces, merged.
        """
        if not use_new_metadata_format:
            return super().get_metadata()

        metadata = get_default_nwbfile_metadata()
        for interface in self.data_interface_objects.values():
            if "use_new_metadata_format" in inspect.signature(interface.get_metadata).parameters:
                interface_metadata = interface.get_metadata(use_new_metadata_format=True)
            else:
                interface_metadata = interface.get_metadata()
            metadata = dict_deep_update(metadata, interface_metadata)

        electrical_series_metadata = metadata["Ecephys"]["ElectricalSeries"]
        for metadata_key, series_name in self._series_name_by_metadata_key.items():
            electrical_series_metadata[metadata_key]["name"] = series_name

        return metadata

    def get_conversion_options_schema(self) -> dict:
        conversion_options_schema = super().get_conversion_options_schema()
        conversion_options_schema["properties"].update(
            {name: interface.get_conversion_options_schema() for name, interface in self.data_interface_objects.items()}
        )
        return conversion_options_schema
