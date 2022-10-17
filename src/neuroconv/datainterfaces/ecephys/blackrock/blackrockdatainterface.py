"""Authors: Luiz Tauffer."""
from typing import Optional
from pathlib import Path

from pynwb.ecephys import ElectricalSeries

from .header_tools import parse_nsx_basic_header, parse_nev_basic_header
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....tools import get_package
from ....utils import (
    get_schema_from_hdmf_class,
    get_schema_from_method_signature,
    FilePathType,
    OptionalFilePathType,
)


class BlackrockRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting Blackrock data using a
    :py:class:`~spikeinterface.extractors.BlackrockRecordingExtractor`."""

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
        Load and prepare data corresponding to Blackrock interface.

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
            spikeextractors = get_package(package_name="spikeextractors")
            spikeinterface = get_package(package_name="spikeinterface")

            self.Extractor = spikeextractors.BlackrockRecordingExtractor
            super().__init__(filename=file_path, nsx_override=nsx_override, nsx_to_load=nsx_to_load, verbose=verbose)
            self.source_data = dict(
                file_path=file_path, nsx_override=nsx_override, nsx_to_load=nsx_to_load, verbose=verbose
            )
            self.recording_extractor = spikeinterface.core.old_api_utils.OldToNewRecording(
                oldapi_recording_extractor=self.recording_extractor
            )

        else:
            spikeinterface = get_package(package_name="spikeinterface")

            self.RX = spikeinterface.extractors.BlackrockRecordingExtractor
            super().__init__(file_path=file_path, stream_id=str(nsx_to_load), verbose=verbose)

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeriesRaw=get_schema_from_hdmf_class(ElectricalSeries),
            ElectricalSeriesProcessed=get_schema_from_hdmf_class(ElectricalSeries),
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
            metadata["Ecephys"]["ElectricalSeriesRaw"] = dict(name="ElectricalSeriesRaw")
        else:
            metadata["Ecephys"]["ElectricalSeriesProcessed"] = dict(name="ElectricalSeriesProcessed")
        return metadata

    def get_conversion_options(self):
        if int(self.file_path.suffix[-1]) >= 5:
            write_as = "raw"
            es_key = "ElectricalSeriesRaw"
        else:
            write_as = "processed"
            es_key = "ElectricalSeriesProcessed"
        conversion_options = dict(write_as=write_as, es_key=es_key, stub_test=False)
        return conversion_options


class BlackrockSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting Blackrock spiking data."""

    @classmethod
    def get_source_schema(cls):
        metadata_schema = get_schema_from_method_signature(class_method=cls.__init__)
        metadata_schema["additionalProperties"] = True
        metadata_schema["properties"]["file_path"].update(description="Path to Blackrock file.")
        return metadata_schema

    def __init__(self, file_path: FilePathType, sampling_frequency: float = None, verbose: bool = True):
        """
        Parameters
        ----------
        file_path : str, Path
            The file path to the ``.nev`` data
        sampling_frequency: float,
            The sampling frequency for the sorting extractor. When the signal data is available (.ncs) those files will be
        used to extract the frequency automatically. Otherwise, the sampling frequency needs to be specified for
        this extractor to be initialized.
        verbose : bool, optional
            Enables verbosity
        """

        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency, verbose=verbose)

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
