"""Authors: Luiz Tauffer."""
from typing import Optional
from pathlib import Path

from spikeinterface.extractors import BlackrockRecordingExtractor
from spikeinterface.core.old_api_utils import OldToNewRecording

import spikeextractors as se
from pynwb.ecephys import ElectricalSeries

from .header_tools import parse_nsx_basic_header, parse_nev_basic_header
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import (
    get_schema_from_hdmf_class,
    get_schema_from_method_signature,
    FilePathType,
    OptionalFilePathType,
)


class BlackrockRecordingExtractorInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a BlackrockRecordingExtractor."""

    RX = BlackrockRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(
            class_method=cls.__init__, exclude=["block_index", "seg_index"]
        )
        source_schema["properties"]["file_path"]["description"] = "Path to Blackrock file."
        return source_schema

    def __init__(
        self,
        file_path: FilePathType,
        nsx_override: OptionalFilePathType = None,
        verbose: bool = True,
        spikeextractors_backend: bool = False,
    ):
        """
        Load and prepare data corresponding to Blackrock interface

        Parameters
        ----------
        file_path : FilePathType
            The path to the Blackrock with suffix being .ns1, .ns2, .ns3, .ns4m .ns4, or .ns6
        spikeextractors_backend : bool
            False by default. When True the interface uses the old extractor from the spikextractors library instead
            of a new spikeinterface object.
        """
        file_path = Path(file_path)
        if file_path.suffix == "":
            assert nsx_override is not None, (
                "if file_path is empty " 'provide a nsx file to load with "nsx_override" arg'
            )
            nsx_to_load = None
            self.file_path = Path(nsx_override)
        else:
            assert "ns" in file_path.suffix, "file_path should be an nsx file"
            nsx_to_load = int(file_path.suffix[-1])
            self.file_path = file_path

        if spikeextractors_backend:
            self.RX = se.BlackrockRecordingExtractor
            super().__init__(filename=file_path, nsx_override=nsx_override, nsx_to_load=nsx_to_load, verbose=verbose)
            self.source_data = dict(
                file_path=file_path, nsx_override=nsx_override, nsx_to_load=nsx_to_load, verbose=verbose
            )
            self.recording_extractor = OldToNewRecording(oldapi_recording_extractor=self.recording_extractor)

        else:
            super().__init__(file_path=file_path, verbose=verbose)

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeries_raw=get_schema_from_hdmf_class(ElectricalSeries),
            ElectricalSeries_processed=get_schema_from_hdmf_class(ElectricalSeries),
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        # Open file and extract headers
        basic_header = parse_nsx_basic_header(self.source_data["file_path"])
        if "TimeOrigin" in basic_header:
            session_start_time = basic_header["TimeOrigin"]
            metadata["NWBFile"].update(session_start_time=session_start_time.strftime("%Y-%m-%dT%H:%M:%S"))
        if "Comment" in basic_header:
            metadata["NWBFile"].update(session_description=basic_header["Comment"])
        # Checks if data is raw or processed
        if int(self.file_path.suffix[-1]) >= 5:
            metadata["Ecephys"]["ElectricalSeries_raw"] = dict(name="ElectricalSeries_raw")
        else:
            metadata["Ecephys"]["ElectricalSeries_processed"] = dict(name="ElectricalSeries_processed")
        return metadata

    def get_conversion_options(self):
        if int(self.file_path.suffix[-1]) >= 5:
            write_as = "raw"
            es_key = "ElectricalSeries_raw"
        else:
            write_as = "processed"
            es_key = "ElectricalSeries_processed"
        conversion_options = dict(write_as=write_as, es_key=es_key, stub_test=False)
        return conversion_options


class BlackrockSortingExtractorInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting Blackrock spiking data."""

    SX = se.BlackrockSortingExtractor

    @classmethod
    def get_source_schema(cls):
        metadata_schema = get_schema_from_method_signature(
            class_method=cls.__init__, exclude=["block_index", "seg_index"]
        )
        metadata_schema["additionalProperties"] = True
        metadata_schema["properties"]["file_path"].update(description="Path to Blackrock file.")
        return metadata_schema

    def __init__(
        self, file_path: FilePathType, nsx_to_load: Optional[int] = None, nev_override: OptionalFilePathType = None
    ):
        super().__init__(filename=file_path, nsx_to_load=nsx_to_load, nev_override=nev_override)
        self.source_data = dict(file_path=file_path, nsx_to_load=nsx_to_load, nev_override=nev_override)

    def get_metadata(self):
        metadata = super().get_metadata()
        # Open file and extract headers
        basic_header = parse_nev_basic_header(self.source_data["file_path"])
        if "TimeOrigin" in basic_header:
            session_start_time = basic_header["TimeOrigin"]
            metadata["NWBFile"].update(session_start_time=session_start_time.strftime("%Y-%m-%dT%H:%M:%S"))
        if "Comment" in basic_header:
            metadata["NWBFile"].update(session_description=basic_header["Comment"])
        return metadata
