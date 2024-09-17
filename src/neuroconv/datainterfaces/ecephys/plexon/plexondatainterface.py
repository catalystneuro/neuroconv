from pathlib import Path

from pydantic import FilePath, validate_call

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import DeepDict


class PlexonRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting Plexon data.

    Uses the :py:class:`~spikeinterface.extractors.PlexonRecordingExtractor`.
    """

    display_name = "Plexon Recording"
    associated_suffixes = (".plx",)
    info = "Interface for Plexon recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .plx file."
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = True,
        es_key: str = "ElectricalSeries",
        stream_name: str = "WB-Wideband",
    ):
        """
        Load and prepare data for Plexon.

        Parameters
        ----------
        file_path : str or Path
            Path to the .plx file.
        verbose : bool, default: True
            Allows verbosity.
        es_key : str, default: "ElectricalSeries"
        stream_name: str, optional
            Only pass a stream if you modified the channel prefixes in the Plexon file and you know the prefix of
            the wideband data.
        """

        invalid_stream_names = ["FPl-Low Pass Filtered", "SPKC-High Pass Filtered", "AI-Auxiliary Input"]
        assert stream_name not in invalid_stream_names, f"Invalid stream name: {stream_name}"

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key, stream_name=stream_name)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        neo_reader = self.recording_extractor.neo_reader

        if hasattr(neo_reader, "raw_annotations"):
            block_ind = self.recording_extractor.block_index
            neo_metadata = neo_reader.raw_annotations["blocks"][block_ind]
            if "rec_datetime" in neo_metadata:
                metadata["NWBFile"].update(session_start_time=neo_metadata["rec_datetime"])

        return metadata


class Plexon2RecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting Plexon2 data.

    Uses the :py:class:`~spikeinterface.extractors.Plexon2RecordingExtractor`.
    """

    display_name = "Plexon2 Recording"
    associated_suffixes = (".pl2",)
    info = "Interface for Plexon2 recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .pl2 file."
        return source_schema

    @validate_call
    def __init__(self, file_path: FilePath, verbose: bool = True, es_key: str = "ElectricalSeries"):
        """
        Load and prepare data for Plexon.

        Parameters
        ----------
        file_path : str or Path
            Path to the .plx file.
        verbose : bool, default: True
            Allows verbosity.
        es_key : str, default: "ElectricalSeries"
        """
        # TODO: when neo version 0.14.4 is out or higher change this to stream_name for clarify
        import neo
        from packaging.version import Version

        neo_version = Version(neo.__version__)
        if neo_version <= Version("0.13.3"):
            stream_id = "3"
        else:
            stream_id = "WB"
        assert Path(file_path).is_file(), f"Plexon file not found in: {file_path}"
        super().__init__(
            file_path=file_path,
            verbose=verbose,
            es_key=es_key,
            stream_id=stream_id,
            all_annotations=True,
        )

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        neo_reader = self.recording_extractor.neo_reader

        block_ind = self.recording_extractor.block_index
        neo_metadata = neo_reader.raw_annotations["blocks"][block_ind]
        metadata["NWBFile"].update(session_start_time=neo_metadata["m_CreatorDateTime"])

        return metadata


class PlexonSortingInterface(BaseSortingExtractorInterface):
    """
    Primary data interface class for converting Plexon spiking data.

    Uses :py:class:`~spikeinterface.extractors.PlexonSortingExtractor`.
    """

    display_name = "Plexon Sorting"
    associated_suffixes = (".plx",)
    info = "Interface for Plexon sorting data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the plexon spiking data (.plx file)."
        return source_schema

    @validate_call
    def __init__(self, file_path: FilePath, verbose: bool = True):
        """
        Load and prepare data for Plexon.

        Parameters
        ----------
        file_path: FilePathType
            Path to the plexon spiking data (.plx file).
        verbose: bool, default: True
            Allows verbosity.
        """
        super().__init__(file_path=file_path, verbose=verbose)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        neo_reader = self.sorting_extractor.neo_reader

        if hasattr(neo_reader, "raw_annotations"):
            block_ind = self.sorting_extractor.block_index
            neo_metadata = neo_reader.raw_annotations["blocks"][block_ind]

            if "rec_datetime" in neo_metadata:
                metadata["NWBFile"].update(session_start_time=neo_metadata["rec_datetime"])

        return metadata
