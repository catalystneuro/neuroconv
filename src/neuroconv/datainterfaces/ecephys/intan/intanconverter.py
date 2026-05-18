from pathlib import Path

from pydantic import FilePath, validate_call

from .intananaloginterface import IntanAnalogInterface
from .intandatainterface import IntanRecordingInterface
from .intanstiminterface import IntanStimInterface
from ....nwbconverter import ConverterPipe
from ....utils import get_json_schema_from_method_signature

# Header stream name -> (interface key, interface class, extra kwargs).
# IntanRecordingInterface accepts both RHD2000 and RHS2000 amplifier streams (it
# selects by stream_id, not stream_name). Each IntanAnalogInterface instance gets
# a unique metadata_key to avoid collisions in metadata["TimeSeries"].
_STREAM_TO_INTERFACE = {
    "RHD2000 amplifier channel": (
        "Recording",
        IntanRecordingInterface,
        {},
    ),
    "RHS2000 amplifier channel": (
        "Recording",
        IntanRecordingInterface,
        {},
    ),
    "RHD2000 auxiliary input channel": (
        "AnalogAuxiliary",
        IntanAnalogInterface,
        {"stream_name": "RHD2000 auxiliary input channel", "metadata_key": "TimeSeriesIntanAuxiliary"},
    ),
    "USB board ADC input channel": (
        "AnalogADCInput",
        IntanAnalogInterface,
        {"stream_name": "USB board ADC input channel", "metadata_key": "TimeSeriesIntanADCInput"},
    ),
    "USB board ADC output channel": (
        "AnalogADCOutput",
        IntanAnalogInterface,
        {"stream_name": "USB board ADC output channel", "metadata_key": "TimeSeriesIntanADCOutput"},
    ),
    "DC Amplifier channel": (
        "AnalogDC",
        IntanAnalogInterface,
        {"stream_name": "DC Amplifier channel", "metadata_key": "TimeSeriesIntanDC"},
    ),
    "Stim channel": (
        "Stim",
        IntanStimInterface,
        {"metadata_key": "TimeSeriesIntanStim"},
    ),
}


class IntanConverter(ConverterPipe):
    """
    Converter for multi-stream Intan .rhd or .rhs recordings.

    Auto-discovers all streams present in the file header and instantiates the
    appropriate sub-interface for each: IntanRecordingInterface for the amplifier
    stream, IntanAnalogInterface for analog streams (auxiliary, ADC inputs/outputs,
    DC amplifier), and IntanStimInterface for the RHS stim channel.
    """

    display_name = "Intan Converter"
    keywords = IntanRecordingInterface.keywords
    associated_suffixes = (".rhd", ".rhs")
    info = "Auto-discovers Intan streams and routes each to the appropriate sub-interface."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__)
        source_schema["properties"]["file_path"]["description"] = (
            "Path to a .rhd or .rhs file. For Traditional save mode pass the single recording file; "
            "for One File Per Signal Type and One File Per Channel modes pass the info.rhd/info.rhs "
            "header file; for split rotated sessions pass any one chunk."
        )
        return source_schema

    @classmethod
    def get_streams(cls, file_path: FilePath) -> list[str]:
        """
        List the stream names present in an Intan .rhd or .rhs file.

        Reads the file header via neo's IntanRawIO without loading any sample data.

        Parameters
        ----------
        file_path : FilePath
            Path to a .rhd or .rhs file.

        Returns
        -------
        list of str
            All stream names reported by the file header (including streams not
            currently routed by this converter, such as digital inputs/outputs
            and supply voltage).
        """
        from neo.rawio import IntanRawIO

        reader = IntanRawIO(filename=str(file_path))
        reader.parse_header()
        return [str(name) for name in reader.header["signal_streams"]["name"]]

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = False,
        saved_files_are_split: bool = False,
    ):
        """
        Auto-discover and route all Intan streams in a .rhd or .rhs file.

        Streams present in the file header that do not have a routed sub-interface
        (digital input/output, supply voltage) are skipped. For finer control,
        construct a ``ConverterPipe`` directly with the specific interfaces you want.

        Parameters
        ----------
        file_path : FilePath
            Path to a .rhd or .rhs file. For Traditional save mode pass the single
            recording file; for One File Per Signal Type and One File Per Channel modes
            pass the ``info.rhd``/``info.rhs`` header file; when
            ``saved_files_are_split=True`` pass any one chunk in the rotated session
            folder.
        verbose : bool, default: False
            Whether to output verbose text.
        saved_files_are_split : bool, default: False
            Set to True when the recording was saved using Intan RHX's "new save file
            every N minutes" option. The flag is forwarded to every sub-interface, which
            concatenate sibling chunks in ``file_path.parent`` in filename order.
        """
        file_path = Path(file_path)

        data_interfaces = {}
        for stream_name in self.get_streams(file_path=file_path):
            if stream_name not in _STREAM_TO_INTERFACE:
                continue
            interface_key, interface_class, extra_kwargs = _STREAM_TO_INTERFACE[stream_name]
            interface_kwargs = dict(file_path=file_path, **extra_kwargs)
            if saved_files_are_split:
                interface_kwargs["saved_files_are_split"] = True
            data_interfaces[interface_key] = interface_class(**interface_kwargs)

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)
