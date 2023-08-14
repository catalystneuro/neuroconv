from pathlib import Path
from typing import Optional

from .openephysbinarydatainterface import OpenEphysBinaryRecordingInterface
from .openephyslegacydatainterface import OpenEphysLegacyRecordingInterface
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import FolderPathType


class OpenEphysRecordingInterface(BaseRecordingExtractorInterface):
    """Abstract class that defines which interface class to use for a given Open Ephys recording."""

    ExtractorName = "OpenEphysBinaryRecordingExtractor"

    def __new__(
        cls,
        folder_path: FolderPathType,
        stream_name: Optional[str] = None,
        verbose: bool = True,
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
        verbose : bool, default: True
        es_key : str, default: "ElectricalSeries"
        """
        super().__new__(cls)

        folder_path = Path(folder_path)
        if any(folder_path.rglob("*.continuous")):
            return OpenEphysLegacyRecordingInterface(
                folder_path=folder_path, stream_name=stream_name, verbose=verbose, es_key=es_key
            )

        elif any(folder_path.rglob("*.dat")):
            return OpenEphysBinaryRecordingInterface(
                folder_path=folder_path, stream_name=stream_name, verbose=verbose, es_key=es_key
            )

        else:
            raise AssertionError("The Open Ephys data must be in 'legacy' (.continuous) or in 'binary' (.dat) format.")
