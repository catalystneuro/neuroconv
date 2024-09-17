from pathlib import Path
from typing import Optional

from pydantic import DirectoryPath, validate_call

from .spikeglxdatainterface import SpikeGLXRecordingInterface
from .spikeglxnidqinterface import SpikeGLXNIDQInterface
from ....nwbconverter import ConverterPipe
from ....utils import get_schema_from_method_signature


class SpikeGLXConverterPipe(ConverterPipe):
    """
    The simplest, easiest to use class for converting all SpikeGLX data in a folder.

    Primary conversion class for handling multiple SpikeGLX data streams.
    """

    display_name = "SpikeGLX Converter"
    keywords = SpikeGLXRecordingInterface.keywords + SpikeGLXNIDQInterface.keywords
    associated_suffixes = SpikeGLXRecordingInterface.associated_suffixes + SpikeGLXNIDQInterface.associated_suffixes
    info = "Converter for multi-stream SpikeGLX recording data."

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(method=cls.__init__, exclude=["streams"])
        source_schema["properties"]["folder_path"]["description"] = "Path to the folder containing SpikeGLX streams."
        return source_schema

    @classmethod
    def get_streams(cls, folder_path: DirectoryPath) -> list[str]:
        from spikeinterface.extractors import SpikeGLXRecordingExtractor

        return SpikeGLXRecordingExtractor.get_streams(folder_path=folder_path)[0]

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        streams: Optional[list[str]] = None,
        verbose: bool = False,
    ):
        """
        Read all data from multiple streams stored in the SpikeGLX format.

        This can include...
            (a) single-probe but multi-band such as AP+LF streams
            (b) multi-probe with multi-band
            (c) with or without the associated NIDQ channels

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to folder containing the NIDQ stream and subfolders containing each IMEC stream.
        streams : list of strings, optional
            A specific list of streams you wish to load.
            To see which streams are available, run `SpikeGLXConverter.get_streams(folder_path="path/to/spikeglx")`.
            By default, all available streams are loaded.
        verbose : bool, default: False
            Whether to output verbose text.
        """
        folder_path = Path(folder_path)

        streams = streams or self.get_streams(folder_path=folder_path)

        data_interfaces = dict()
        for stream in streams:
            if "ap" in stream:
                probe_name = stream[:5]
                file_path = (
                    folder_path / f"{folder_path.stem}_{probe_name}" / f"{folder_path.stem}_t0.{probe_name}.ap.bin"
                )
                es_key = f"ElectricalSeriesAP{probe_name.capitalize()}"
                interface = SpikeGLXRecordingInterface(file_path=file_path, es_key=es_key)
            elif "lf" in stream:
                probe_name = stream[:5]
                file_path = (
                    folder_path / f"{folder_path.stem}_{probe_name}" / f"{folder_path.stem}_t0.{probe_name}.lf.bin"
                )
                es_key = f"ElectricalSeriesLF{probe_name.capitalize()}"
                interface = SpikeGLXRecordingInterface(file_path=file_path, es_key=es_key)
            elif "nidq" in stream:
                file_path = folder_path / f"{folder_path.stem}_t0.nidq.bin"
                interface = SpikeGLXNIDQInterface(file_path=file_path)
            data_interfaces.update({str(stream): interface})  # Without str() casting, is a numpy string

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

    def get_conversion_options_schema(self) -> dict:
        conversion_options_schema = super().get_conversion_options_schema()
        conversion_options_schema["properties"].update(
            {name: interface.get_conversion_options_schema() for name, interface in self.data_interface_objects.items()}
        )
        return conversion_options_schema
