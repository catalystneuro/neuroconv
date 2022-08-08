"""Author: Heberto Mayorquin"""
from typing import Optional
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from spikeinterface.extractors import TdtRecordingExtractor

from ....utils.types import FolderPathType


class TdtRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting Tucker-Davis Technologies (TDT) data."""

    RX = TdtRecordingExtractor

    def __init__(self, folder_path: FolderPathType, stream_id: Optional[str] = None, verbose: bool = True):
        """
        Parameters
        ----------
        folder_path: str or Path
            Path to the folder or directory with the corresponding files (TSQ, TBK, TEV, SEV)
        stream_id: str, optional
            Select from multiple streams.
        verbose: bool, True by default
            Allows verbose.
        """
        super().__init__(
            folder_path=folder_path,
            stream_id=stream_id,
            verbose=verbose,
        )

        # Fix channel name format
        channel_names = self.recording_extractor.get_property("channel_name")
        channel_names = [name.replace("'", "")[1:] for name in channel_names]
        self.recording_extractor.set_property(key="channel_name", values=channel_names)
