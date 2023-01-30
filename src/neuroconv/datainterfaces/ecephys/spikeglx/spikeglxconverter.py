"""The simplest, easiest to use class for converting all SpikeGLX data in a folder."""
from pathlib import Path
from typing import List, Optional

from pynwb import NWBFile
from pydantic import DirectoryPath

from .spikeglxdatainterface import SpikeGLXRecordingInterface, SpikeGLXLFPInterface
from .spikeglxnidqinterface import SpikeGLXNIDQInterface
from ....nwbconverter import ConverterPipe
from ....tools.nwb_helpers import make_or_load_nwbfile
from ....utils import get_schema_from_method_signature


class SpikeGLXConverter(ConverterPipe):
    """Primary conversion class for handling multiple SpikeGLX data streams."""

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
        data_interfaces = dict()
        for stream in available_streams:
            file_path = folder_path / f"{folder_path.stem[:-5]}.imec0.{stream}.bin"  # imagining that stream="ap", "lf"
            # Also might need to consider case where file stem doesn't match folder stem (not typical SpikeGLX though)
            if "ap" in stream:
                interface = SpikeGLXRecordingInterface(file_path=file_path)
            if "lf" in stream:
                interface = SpikeGLXLFPInterface(file_path=file_path)
            if "nidq" in stream:
                interface = SpikeGLXNIDQInterface(file_path=file_path)
            data_interfaces.update({stream: interface})

        self.__init__(data_interfaces=data_interfaces)

    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        # conversion_options: Optional[dict] = None,  # This is the only thing that might get complicated
        # but it will require the same complications no matter what approach we take
    ):
        if metadata is None:
            metadata = self.get_metadata()
        self.validate_metadata(metadata=metadata)
        # self.validate_conversion_options(conversion_options=conversion_options_to_run)

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
        ) as nwbfile_out:
            for interface_name, data_interface in self.data_interface_objects.items():
                data_interface.run_conversion(
                    nwbfile=nwbfile_out,
                    metadata=metadata,
                    # , **conversion_options_to_run.get(interface_name, dict())
                )
