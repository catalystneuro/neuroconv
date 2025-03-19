from pathlib import Path
from typing import Optional

from pydantic import DirectoryPath

from .openephysbinarydatainterface import OpenEphysBinaryRecordingInterface
from .openephyslegacydatainterface import OpenEphysLegacyRecordingInterface
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class OpenEphysRecordingInterface(BaseRecordingExtractorInterface):
    """Abstract class that defines which interface class to use for a given Open Ephys recording."""

    display_name = "OpenEphys Recording"
    associated_suffixes = (".dat", ".oebin", ".npy")
    info = "Interface for converting any OpenEphys recording data."

    ExtractorName = "OpenEphysBinaryRecordingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to OpenEphys directory (.continuous or .dat files)."
        return source_schema

    @classmethod
    def get_stream_names(cls, folder_path: DirectoryPath) -> list[str]:
        """
        Get the names of available recording streams in the OpenEphys folder.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to OpenEphys directory (.continuous or .dat files).

        Returns
        -------
        list of str
            The names of the available recording streams.

        Raises
        ------
        AssertionError
            If the data is neither in 'legacy' (.continuous) nor 'binary' (.dat) format.
        """
        if any(Path(folder_path).rglob("*.continuous")):
            return OpenEphysLegacyRecordingInterface.get_stream_names(folder_path=folder_path)
        elif any(Path(folder_path).rglob("*.dat")):
            return OpenEphysBinaryRecordingInterface.get_stream_names(folder_path=folder_path)
        else:
            raise AssertionError("The Open Ephys data must be in 'legacy' (.continuous) or in 'binary' (.dat) format.")

    def __new__(
        cls,
        folder_path: DirectoryPath,
        stream_name: Optional[str] = None,
        block_index: Optional[int] = None,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ):
        """
        Abstract class that defines which interface class to use for a given Open Ephys recording.

        For "legacy" format (.continuous files) the interface redirects to OpenEphysLegacyRecordingInterface.
        For "binary" format (.dat files) the interface redirects to OpenEphysBinaryRecordingInterface.

        Parameters
        ----------
        folder_path : FolderPathType
            Path to OpenEphys directory (.continuous or .dat files).
        stream_name : str, optional
            The name of the recording stream.
            When the recording stream is not specified the channel stream is chosen if available.
            When channel stream is not available the name of the stream must be specified.
        block_index : int, optional, default: None
            The index of the block to extract from the data.
        verbose : bool, default: False
        es_key : str, default: "ElectricalSeries"
        """
        super().__new__(cls)

        folder_path = Path(folder_path)
        if any(folder_path.rglob("*.continuous")):
            return OpenEphysLegacyRecordingInterface(
                folder_path=folder_path,
                stream_name=stream_name,
                block_index=block_index,
                verbose=verbose,
                es_key=es_key,
            )

        elif any(folder_path.rglob("*.dat")):
            return OpenEphysBinaryRecordingInterface(
                folder_path=folder_path,
                stream_name=stream_name,
                block_index=block_index,
                verbose=verbose,
                es_key=es_key,
            )

        else:
            raise AssertionError("The Open Ephys data must be in 'legacy' (.continuous) or in 'binary' (.dat) format.")
