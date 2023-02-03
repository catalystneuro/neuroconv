"""Authors: Szonja Weigl, Cody Baker."""
from typing import Optional

from spikeinterface.extractors import OpenEphysLegacyRecordingExtractor

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import FolderPathType, get_schema_from_method_signature


class OpenEphysLegacyRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface for converting legacy Open Ephys data (.continuous files).
    Uses :py:class:`~spikeinterface.extractors.OpenEphysLegacyRecordingExtractor`."""

    ExtractorName = "OpenEphysLegacyRecordingExtractor"

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the RecordingExtractor."""
        source_schema = get_schema_from_method_signature(
            class_method=cls.__init__,
            exclude=["stream_id", "stream_name", "block_index", "all_annotations", "stub_test"],
        )
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to directory containing OpenEphys legacy files."
        return source_schema

    def __init__(
        self,
        folder_path: FolderPathType,
        stream_id: Optional[str] = "CH",
        stream_name: Optional[str] = None,
        block_index: Optional[int] = 0,
        all_annotations: Optional[bool] = False,
        stub_test: bool = True,
        verbose: bool = True,
    ):
        """
        Initialize reading of OpenEphys legacy recording (.continuous files).
        See :py:class:`~spikeinterface.extractors.OpenEphysLegacyRecordingExtractor` for options.

        Parameters
        ----------
        folder_path : FolderPathType
            Path to OpenEphys directory.
        stream_id : str, default: "CH"
            The identifier of the recording stream (e.g. "CH" for channel data).
        stream_name : str, default: None
        block_index : int, default: 0
        all_annotations : bool, default: False
        stub_test : bool, default: False
        verbose : bool, default: True
        """
        self.RX = OpenEphysLegacyRecordingExtractor
        super().__init__(
            folder_path=folder_path,
            stream_id=stream_id,
            stream_name=stream_name,
            block_index=block_index,
            all_annotations=all_annotations,
            verbose=verbose,
        )

        if stub_test:
            self.subset_channels = [0, 1]

    def get_metadata(self):
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        import pyopenephys

        metadata = super().get_metadata()

        folder_path = self.source_data["folder_path"]
        fileobj = pyopenephys.File(foldername=folder_path)
        session_start_time = fileobj.experiments[0].datetime

        metadata["NWBFile"].update(session_start_time=session_start_time)
        return metadata
