"""The simplest, easiest to use class for converting all SpikeGLX data in a folder."""
from pathlib import Path
from typing import List

from pydantic import DirectoryPath

from .spikeglxdatainterface import SpikeGLXRecordingInterface, SpikeGLXLFPInterface
from .spikeglxnidqinterface import SpikeGLXNIDQInterface
from ....nwbconverter import ConverterPipe
from ....utils import get_schema_from_method_signature


class SpikeGLXConverter(ConverterPipe):
    """Primary conversion class for handling multiple SpikeGLX data streams."""

    data_interface_classes = dict(AP=SpikeGLXRecordingInterface, LF=SpikeGLXLFPInterface, NIDQ=SpikeGLXNIDQInterface)

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(class_method=cls.__init__)
        source_schema["properties"]["folder_path"]["description"] = "Path to the folder containing SpikeGLX streams."
        return source_schema

    def __init__(
        self,
        folder_path: DirectoryPath,
        streams: List[str] = False,  # List[Outer[Literal["AP"], Literal["LF"], Literal["NIDQ"]]]
        #  'Outer' is short-hand for any combination of those literals
        # TODO think about multiple probe format
    ):
        """
        Read all data from multiple streams stored in the SpikeGLX format.

        This can include...
            (a) single-probe but multi-band such as AP+LF streams
            (b) multi-probe with multi-band
            (c) with or without the associated NIDQ channels

        Parameters
        ----------
        file_path : FilePathType
            Path to .nidq.bin file.
        stub_test : bool, default: False
            Whether to shorten file for testing purposes.
        verbose : bool, default: True
            Whether to output verbose text.
        load_sync_channel : bool, default: False
            Whether or not to load the last channel in the stream, which is typically used for synchronization.
            If True, then the probe is not loaded.
        """
        from spikeinterface.extractors import SpikeGLXRecordingExtractor

        available_streams = SpikeGLXRecordingExtractor.get_streams(
            folder_path=folder_path
        )  # TODO: wish this was a SI class method...

        folder_path = Path(folder_path)
        self.data_interface_objects = dict()
        for stream in available_streams:
            file_path = folder_path / f"{folder_path.stem[:-5]}.imec0.{stream}.bin"  # imagining that stream="ap", "lf"
            # Also might need to consider case where file stem doesn't match folder stem (not typical SpikeGLX though)
            if "ap" in stream:
                interface = SpikeGLXRecordingInterface(file_path=file_path)
            if "lf" in stream:
                interface = SpikeGLXLFPInterface(file_path=file_path)
            if "nidq" in stream:
                interface = SpikeGLXNIDQInterface(file_path=file_path)
            self.data_interface_objects.update({stream: interface})
