from pydantic import DirectoryPath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class AlphaOmegaRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting AlphaOmega recording data.

    Uses the :py:class:`~spikeinterface.extractors.AlphaOmegaRecordingExtractor`.
    """

    display_name = "AlphaOmega Recording"
    associated_suffixes = (".mpx",)
    info = "Interface class for converting AlphaOmega recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"]["description"] = "Path to the folder of .mpx files."
        return source_schema

    def __init__(self, folder_path: DirectoryPath, verbose: bool = True, es_key: str = "ElectricalSeries"):
        """
        Load and prepare data for AlphaOmega.

        Parameters
        ----------
        folder_path: string or Path
            Path to the folder of .mpx files.
        verbose: boolean
            Allows verbose.
            Default is True.
        es_key: str, default: "ElectricalSeries"
        """
        super().__init__(folder_path=folder_path, stream_id="RAW", verbose=verbose, es_key=es_key)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        annotation = self.recording_extractor.neo_reader.raw_annotations
        metadata["NWBFile"].update(session_start_time=annotation["blocks"][0]["rec_datetime"])
        return metadata
