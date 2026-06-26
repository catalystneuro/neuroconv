from pathlib import Path

from pydantic import FilePath, validate_call

from .intananaloginterface import IntanAnalogInterface
from .intandatainterface import IntanRecordingInterface
from .intanstiminterface import IntanStimInterface
from ....nwbconverter import ConverterPipe
from ....utils import get_json_schema_from_method_signature


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

    # Maps header stream name to interface routing.
    # "interface_name" and "interface" are routing fields consumed by the converter loop.
    # All remaining keys are forwarded verbatim as constructor kwargs. stream_name and
    # file_path are always injected by the loop; only interface-specific extras appear here.
    _ROUTING_KEYS = frozenset({"interface_name", "interface"})
    _STREAM_TO_INTERFACE = {
        "RHD2000 amplifier channel": {
            "interface_name": "Recording",
            "interface": IntanRecordingInterface,
            "metadata_key": "intan_amplifier",
        },
        "RHS2000 amplifier channel": {
            "interface_name": "Recording",
            "interface": IntanRecordingInterface,
            "metadata_key": "intan_amplifier",
        },
        "RHD2000 auxiliary input channel": {
            "interface_name": "AnalogAuxiliary",
            "interface": IntanAnalogInterface,
            "metadata_key": "time_series_intan_auxiliary",
        },
        "USB board ADC input channel": {
            "interface_name": "AnalogADCInput",
            "interface": IntanAnalogInterface,
            "metadata_key": "time_series_intan_adc_input",
        },
        "USB board ADC output channel": {
            "interface_name": "AnalogADCOutput",
            "interface": IntanAnalogInterface,
            "metadata_key": "time_series_intan_adc_output",
        },
        "DC Amplifier channel": {
            "interface_name": "AnalogDC",
            "interface": IntanAnalogInterface,
            "metadata_key": "time_series_intan_dc",
        },
        "Stim channel": {
            "interface_name": "Stim",
            "interface": IntanStimInterface,
            "metadata_key": "time_series_intan_stim",
        },
    }

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["exclude_streams"])
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
        *,
        exclude_streams: list[str] | None = None,
        verbose: bool = False,
        saved_files_are_split: bool = False,
    ):
        """
        Auto-discover and route all Intan streams in a .rhd or .rhs file.

        Streams present in the file header that do not have a routed sub-interface
        (digital input/output, supply voltage) are skipped automatically.

        Parameters
        ----------
        file_path : FilePath
            Path to a .rhd or .rhs file. For Traditional save mode pass the single
            recording file; for One File Per Signal Type and One File Per Channel modes
            pass the ``info.rhd``/``info.rhs`` header file; when
            ``saved_files_are_split=True`` pass any one chunk in the rotated session
            folder.
        exclude_streams : list of str, optional
            Stream names to skip from auto-discovery. Useful for omitting a large
            stream (for example the Stim channel) during a fast test conversion.
            ``IntanConverter.get_streams(file_path=...)`` lists what is available.
            Unknown names raise ``ValueError``.
        verbose : bool, default: False
            Whether to output verbose text.
        saved_files_are_split : bool, default: False
            Set to True when the recording was saved using Intan RHX's "new save file
            every N minutes" option. The flag is forwarded to every sub-interface, which
            concatenate sibling chunks in ``file_path.parent`` in filename order.
        """
        file_path = Path(file_path)

        present_streams = self.get_streams(file_path=file_path)

        if exclude_streams:
            unknown = [name for name in exclude_streams if name not in present_streams]
            if unknown:
                raise ValueError(
                    f"Cannot exclude streams {unknown}: not present in {file_path.name}. "
                    f"Available streams: {present_streams}."
                )
            present_streams = [name for name in present_streams if name not in exclude_streams]

        data_interfaces = {}
        for stream_name in present_streams:
            if stream_name not in self._STREAM_TO_INTERFACE:
                continue
            entry = self._STREAM_TO_INTERFACE[stream_name]
            interface_kwargs = dict(file_path=file_path)
            interface_kwargs.update({k: v for k, v in entry.items() if k not in self._ROUTING_KEYS})
            if entry["interface"] is IntanAnalogInterface:
                interface_kwargs["stream_name"] = stream_name
            elif entry["interface"] is IntanRecordingInterface:
                interface_kwargs["es_key"] = interface_kwargs.pop("metadata_key")
            if saved_files_are_split:
                interface_kwargs["saved_files_are_split"] = True
            data_interfaces[entry["interface_name"]] = entry["interface"](**interface_kwargs)

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)
