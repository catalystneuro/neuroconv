"""Authors: Szonja Weigl, Cody Baker."""
from typing import Optional
from warnings import warn

from neo.rawio import OpenEphysRawIO
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
        stream_id: Optional[str] = None,
        stream_name: Optional[str] = None,
        block_index: Optional[int] = 0,
        all_annotations: Optional[bool] = False,
        stub_test: bool = False,
        verbose: bool = True,
    ):
        """
        Initialize reading of OpenEphys legacy recording (.continuous files).
        See :py:class:`~spikeinterface.extractors.OpenEphysLegacyRecordingExtractor` for options.

        Parameters
        ----------
        folder_path : FolderPathType
            Path to OpenEphys directory.
        stream_id : str, default: None
            The identifier of the recording stream.
            When the recording stream is not specified the channel stream ("CH") is chosen if available.
            When channel stream is not available the stream_id or stream_name must be specified.
        stream_name : str, optional
            The name of the recording stream.
        block_index : int, default: 0
        all_annotations : bool, default: False
        stub_test : bool, default: False
        verbose : bool, default: True
        """
        self.RX = OpenEphysLegacyRecordingExtractor

        self.folder_path = folder_path
        if stream_name is None and stream_id is None:
            stream_ids = self._get_stream_ids()

            assert "CH" in stream_ids, (
                "The identifier or name of recording stream must be specified when the "
                "channel stream cannot be found in the data. The stream IDs in this data: "
                f"{', '.join(stream_ids)}"
            )

            stream_id = "CH"

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

    def _get_stream_ids(self):
        """Returns the identifier of signal streams for this folder."""
        reader = OpenEphysRawIO(self.folder_path)
        reader.parse_header()
        signal_streams = reader.header["signal_streams"]
        return list(signal_streams["id"])

    def get_metadata(self):
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        import pyopenephys

        metadata = super().get_metadata()

        folder_path = self.source_data["folder_path"]
        fileobj = pyopenephys.File(foldername=folder_path)
        session_start_time = fileobj.experiments[0].datetime

        metadata["NWBFile"].update(session_start_time=session_start_time)
        return metadata
