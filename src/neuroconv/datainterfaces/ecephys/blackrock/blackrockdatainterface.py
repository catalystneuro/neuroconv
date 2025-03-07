from pathlib import Path
from typing import Optional

from pydantic import FilePath

from .header_tools import _parse_nev_basic_header, _parse_nsx_basic_header
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import get_json_schema_from_method_signature


class BlackrockRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting Blackrock data using a
    :py:class:`~spikeinterface.extractors.BlackrockRecordingExtractor`."""

    display_name = "Blackrock Recording"
    associated_suffixes = (".ns0", ".ns1", ".ns2", ".ns3", ".ns4", ".ns5")
    info = "Interface for Blackrock recording data."

    @classmethod
    def get_source_schema(cls):
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["block_index", "seg_index"])
        source_schema["properties"]["file_path"][
            "description"
        ] = "Path to the Blackrock file with suffix being .ns1, .ns2, .ns3, .ns4m .ns4, or .ns6."
        return source_schema

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        extractor_kwargs = source_data.copy()
        extractor_kwargs["stream_id"] = self.stream_id

        return extractor_kwargs

    def __init__(
        self,
        file_path: FilePath,
        nsx_override: Optional[FilePath] = None,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ):
        """
        Load and prepare data corresponding to Blackrock interface.

        Parameters
        ----------
        file_path : FilePath
            Path to the Blackrock file with suffix being .ns1, .ns2, .ns3, .ns4m .ns4, or .ns6
        verbose: bool, default: True
        es_key : str, default: "ElectricalSeries"
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

        self.stream_id = str(nsx_to_load)
        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        # Open file and extract headers
        basic_header = _parse_nsx_basic_header(self.source_data["file_path"])
        if "TimeOrigin" in basic_header:
            metadata["NWBFile"].update(session_start_time=basic_header["TimeOrigin"])
        if "Comment" in basic_header:
            metadata["NWBFile"].update(session_description=basic_header["Comment"])

        return metadata


class BlackrockSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting Blackrock spiking data."""

    display_name = "Blackrock Sorting"
    associated_suffixes = (".nev",)
    info = "Interface for Blackrock sorting data."

    @classmethod
    def get_source_schema(cls) -> dict:
        metadata_schema = get_json_schema_from_method_signature(method=cls.__init__)
        metadata_schema["additionalProperties"] = True
        metadata_schema["properties"]["file_path"].update(description="Path to Blackrock .nev file.")
        return metadata_schema

    def __init__(self, file_path: FilePath, sampling_frequency: Optional[float] = None, verbose: bool = False):
        """
        Parameters
        ----------
        file_path : str, Path
            The file path to the ``.nev`` data
        sampling_frequency: float, optional
            The sampling frequency for the sorting extractor. When the signal data is available (.ncs) those files will be
            used to extract the frequency automatically. Otherwise, the sampling frequency needs to be specified for
            this extractor to be initialized.
        verbose : bool, default: False
            Enables verbosity
        """
        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency, verbose=verbose)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        # Open file and extract headers
        basic_header = _parse_nev_basic_header(self.source_data["file_path"])
        if "TimeOrigin" in basic_header:
            session_start_time = basic_header["TimeOrigin"]
            metadata["NWBFile"].update(session_start_time=session_start_time.strftime("%Y-%m-%dT%H:%M:%S"))
        if "Comment" in basic_header:
            metadata["NWBFile"].update(session_description=basic_header["Comment"])
        return metadata
