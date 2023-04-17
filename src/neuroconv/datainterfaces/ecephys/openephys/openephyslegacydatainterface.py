from typing import List

from dateutil.parser import parse

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import FolderPathType


class OpenEphysLegacyRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface for converting legacy Open Ephys data (.continuous files).
    Uses :py:class:`~spikeinterface.extractors.OpenEphysLegacyRecordingExtractor`."""

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the RecordingExtractor."""
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to directory containing OpenEphys legacy files."

        return source_schema

    def __init__(
        self,
        folder_path: FolderPathType,
        stream_name: str = "Signals CH",
        verbose: bool = True,
    ):
        """
        Initialize reading of OpenEphys legacy recording (.continuous files).
        See :py:class:`~spikeinterface.extractors.OpenEphysLegacyRecordingExtractor` for options.

        Parameters
        ----------
        folder_path : FolderPathType
            Path to OpenEphys directory.
        stream_name : str, default: "Signals CH"
            The name of the recording stream.
        verbose : bool, default: True
        """

        available_streams = self.get_stream_names(folder_path=folder_path)
        assert (
            stream_name in available_streams
        ), f"The selected stream '{stream_name}' is not in the available streams '{available_streams}'!"

        super().__init__(
            folder_path=folder_path,
            stream_name=stream_name,
            verbose=verbose,
        )

    @classmethod
    def get_stream_names(cls, folder_path: FolderPathType) -> List[str]:
        from spikeinterface.extractors import OpenEphysLegacyRecordingExtractor

        stream_names, _ = OpenEphysLegacyRecordingExtractor.get_streams(folder_path=folder_path)
        return stream_names

    def get_metadata(self):
        metadata = super().get_metadata()

        neo_reader = self.recording_extractor.neo_reader
        block_annotations = neo_reader.raw_annotations.get("blocks", [])
        if block_annotations:
            segment_annotations = block_annotations[0].get("segments", [])
            if segment_annotations:
                date_created = segment_annotations[0]["date_created"]
                session_start_time = parse(date_created)
                metadata["NWBFile"].update(session_start_time=session_start_time)
        return metadata
