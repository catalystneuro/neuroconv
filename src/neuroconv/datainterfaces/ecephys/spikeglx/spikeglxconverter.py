from pathlib import Path
from typing import Optional

from pydantic import DirectoryPath, validate_call

from .spikeglxdatainterface import SpikeGLXRecordingInterface
from .spikeglxnidqinterface import SpikeGLXNIDQInterface
from ....nwbconverter import ConverterPipe
from ....utils import get_json_schema_from_method_signature


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
    def get_source_schema(cls) -> dict:
        """
        Get the schema for the source arguments.

        Returns
        -------
        dict
            The schema dictionary containing input parameters and descriptions
            for initializing the SpikeGLX converter.
        """
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["streams"])
        source_schema["properties"]["folder_path"]["description"] = "Path to the folder containing SpikeGLX streams."
        return source_schema

    @classmethod
    def get_streams(cls, folder_path: DirectoryPath) -> list[str]:
        """
        Get the stream IDs available in the folder.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing SpikeGLX streams.

        Returns
        -------
        list of str
            The IDs of all available streams in the folder.
        """
        from spikeinterface.extractors import SpikeGLXRecordingExtractor

        # The first entry is the stream ids the second is the stream names
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

        streams_ids = streams or self.get_streams(folder_path=folder_path)

        data_interfaces = dict()

        nidq_streams = [stream_id for stream_id in streams_ids if stream_id == "nidq"]
        electrical_streams = [stream_id for stream_id in streams_ids if stream_id not in nidq_streams]
        for stream_id in electrical_streams:
            data_interfaces[stream_id] = SpikeGLXRecordingInterface(folder_path=folder_path, stream_id=stream_id)

        for stream_id in nidq_streams:
            data_interfaces[stream_id] = SpikeGLXNIDQInterface(folder_path=folder_path)

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

    def get_conversion_options_schema(self) -> dict:
        conversion_options_schema = super().get_conversion_options_schema()
        conversion_options_schema["properties"].update(
            {name: interface.get_conversion_options_schema() for name, interface in self.data_interface_objects.items()}
        )
        return conversion_options_schema
