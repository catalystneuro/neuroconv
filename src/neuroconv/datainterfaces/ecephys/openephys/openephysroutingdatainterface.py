from abc import ABC
from pathlib import Path
from typing import Optional

from .openephysdatainterface import OpenEphysBinaryRecordingInterface
from .openephyslegacydatainterface import OpenEphysLegacyRecordingInterface
from ....utils import FolderPathType


class OpenEphysRecordingInterface(ABC):
    """Abstract class that defines which interface class to use for a given Open Ephys recording."""

    def __new__(
        cls,
        folder_path: FolderPathType,
        interface_kwargs: Optional[dict] = None,
        stub_test: bool = False,
        verbose: bool = True,
    ):
        """
        Abstract class that defines which interface class to use for a given Open Ephys recording.
        For "legacy" format (.continuous files) the interface redirects to OpenEphysLegacyRecordingInterface.
        For "binary" format (.dat files) the interface redirects to OpenEphysBinaryRecordingInterface.

        Parameters
        ----------
        folder_path : FolderPathType
            Path to OpenEphys directory (.continuous or .dat files).
        interface_kwargs : dict, default: None
            The keyword arguments to propagate to the recording interface depending on the format.
            For "legacy" format use "stream_id" to define which recording stream to convert.
            For "binary" format use "experiment_id" or "recording_id".
        stub_test : bool, default: False
        verbose : bool, default: True
        """
        self = super().__new__(cls)
        self.folder_path = folder_path
        self.interface_kwargs = interface_kwargs or dict()

        if any((Path(self.folder_path).rglob("*.continuous"))):
            return OpenEphysLegacyRecordingInterface(
                folder_path=self.folder_path,
                stub_test=stub_test,
                verbose=verbose,
                **self.interface_kwargs,
            )

        elif any((Path(self.folder_path).rglob("*.dat"))):
            return OpenEphysBinaryRecordingInterface(
                folder_path=self.folder_path,
                stub_test=stub_test,
                verbose=verbose,
                **self.interface_kwargs,
            )

        else:
            raise AssertionError("The data must be in 'legacy' (.continuous) or in 'binary' (.dat) format.")
