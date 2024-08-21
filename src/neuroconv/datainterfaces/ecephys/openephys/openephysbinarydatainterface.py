from typing import Optional

from pydantic import DirectoryPath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import get_schema_from_method_signature


class OpenEphysBinaryRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface for converting binary OpenEphys data (.dat files).

    Uses :py:class:`~spikeinterface.extractors.OpenEphysBinaryRecordingExtractor`.
    """

    display_name = "OpenEphys Binary Recording"
    associated_suffixes = (".dat", ".oebin", ".npy")
    info = "Interface for converting binary OpenEphys recording data."

    ExtractorName = "OpenEphysBinaryRecordingExtractor"

    @classmethod
    def get_stream_names(cls, folder_path: DirectoryPath) -> list[str]:
        from spikeinterface.extractors import OpenEphysBinaryRecordingExtractor

        stream_names, _ = OpenEphysBinaryRecordingExtractor.get_streams(folder_path=folder_path)
        return stream_names

    @classmethod
    def get_source_schema(cls) -> dict:
        """Compile input schema for the RecordingExtractor."""
        source_schema = get_schema_from_method_signature(
            method=cls.__init__, exclude=["recording_id", "experiment_id", "stub_test"]
        )
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to directory containing OpenEphys binary files."
        return source_schema

    def __init__(
        self,
        folder_path: DirectoryPath,
        stream_name: Optional[str] = None,
        block_index: Optional[int] = None,
        stub_test: bool = False,
        verbose: bool = True,
        es_key: str = "ElectricalSeries",
    ):
        """
        Initialize reading of OpenEphys binary recording.

        Parameters
        ----------
        folder_path: FolderPathType
            Path to directory containing OpenEphys binary files.
        stream_name : str, optional
            The name of the recording stream to load; only required if there is more than one stream detected.
            Call `OpenEphysRecordingInterface.get_stream_names(folder_path=...)` to see what streams are available.
        block_index : int, optional, default: None
            The index of the block to extract from the data.
        stub_test : bool, default: False
        verbose : bool, default: True
        es_key : str, default: "ElectricalSeries"
        """
        from ._openephys_utils import _read_settings_xml

        self._xml_root = _read_settings_xml(folder_path)

        available_streams = self.get_stream_names(folder_path=folder_path)
        if len(available_streams) > 1 and stream_name is None:
            raise ValueError(
                "More than one stream is detected! "
                "Please specify which stream you wish to load with the `stream_name` argument. "
                "To see what streams are available, call "
                " `OpenEphysRecordingInterface.get_stream_names(folder_path=...)`."
            )
        if stream_name is not None and stream_name not in available_streams:
            raise ValueError(
                f"The selected stream '{stream_name}' is not in the available streams '{available_streams}'!"
            )

        super().__init__(
            folder_path=folder_path, stream_name=stream_name, block_index=block_index, verbose=verbose, es_key=es_key
        )

        if stub_test:
            self.subset_channels = [0, 1]

    def get_metadata(self) -> dict:
        from ._openephys_utils import _get_session_start_time

        metadata = super().get_metadata()

        session_start_time = _get_session_start_time(element=self._xml_root)
        if session_start_time is not None:
            metadata["NWBFile"].update(session_start_time=session_start_time)
        return metadata
