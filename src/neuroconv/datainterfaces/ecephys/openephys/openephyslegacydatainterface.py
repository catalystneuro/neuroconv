from datetime import datetime
from typing import List, Optional
from warnings import warn

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import FolderPathType


class OpenEphysLegacyRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface for converting legacy Open Ephys data (.continuous files).
    Uses :py:class:`~spikeinterface.extractors.OpenEphysLegacyRecordingExtractor`."""

    @classmethod
    def get_stream_names(cls, folder_path: FolderPathType, ignore_timestamps_errors: bool = False) -> List[str]:
        from spikeinterface.extractors import OpenEphysLegacyRecordingExtractor

        stream_names, _ = OpenEphysLegacyRecordingExtractor.get_streams(
            folder_path=folder_path,
            ignore_timestamps_errors=ignore_timestamps_errors,
        )
        return stream_names

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
        stream_name: Optional[str] = None,
        verbose: bool = True,
        es_key: str = "ElectricalSeries",
        ignore_timestamps_errors: bool = False,
    ):
        """
        Initialize reading of OpenEphys legacy recording (.continuous files).
        See :py:class:`~spikeinterface.extractors.OpenEphysLegacyRecordingExtractor` for options.

        Parameters
        ----------
        folder_path : FolderPathType
            Path to OpenEphys directory.
        stream_name : str, optional
            The name of the recording stream.
        verbose : bool, default: True
        es_key : str, default: "ElectricalSeries"
        ignore_timestamps_errors : bool, default: False
            Ignore the discontinuous timestamps error in neo.
        """
        available_streams = self.get_stream_names(
            folder_path=folder_path, ignore_timestamps_errors=ignore_timestamps_errors
        )
        if len(available_streams) > 1 and stream_name is None:
            raise ValueError(
                "More than one stream is detected! Please specify which stream you wish to load with the `stream_name` argument. "
                "To see what streams are available, call `OpenEphysRecordingInterface.get_stream_names(folder_path=...)`."
            )
        if stream_name is not None and stream_name not in available_streams:
            raise ValueError(
                f"The selected stream '{stream_name}' is not in the available streams '{available_streams}'!"
            )

        super().__init__(
            folder_path=folder_path,
            stream_name=stream_name,
            ignore_timestamps_errors=ignore_timestamps_errors,
            verbose=verbose,
            es_key=es_key,
        )

    def get_metadata(self):
        metadata = super().get_metadata()

        neo_reader = self.recording_extractor.neo_reader
        block_annotations = neo_reader.raw_annotations.get("blocks", [])
        if block_annotations:
            segment_annotations = block_annotations[0].get("segments", [])
            if segment_annotations:
                expected_date_format = "%d-%b-%Y %H%M%S"
                date_created = segment_annotations[0]["date_created"]
                date_created = date_created.strip("'")
                extracted_date, extracted_timestamp = date_created.split(" ")
                if len(extracted_timestamp) != len("%H%M%S"):
                    warn(
                        f"The timestamp for starting time from openephys metadata is ambiguous ('{extracted_timestamp}')! Only the date will be auto-populated in metadata. Please update the timestamp manually to record this value with the highest known temporal resolution."
                    )
                    session_start_time = datetime.strptime(extracted_date, "%d-%b-%Y")
                else:
                    session_start_time = datetime.strptime(date_created, expected_date_format)
                metadata["NWBFile"].update(session_start_time=session_start_time)

        return metadata
