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
    stream_id = "RAW"

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Compile input schema for the AlphaOmega recording extractor.

        Returns
        -------
        dict
            The schema dictionary describing the source data requirements
            for the AlphaOmega recording interface.
        """
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"]["description"] = "Path to the folder of .mpx files."
        return source_schema

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        """
        Convert source data to keyword arguments for the AlphaOmega extractor.

        Parameters
        ----------
        source_data : dict
            Dictionary containing source data parameters.

        Returns
        -------
        dict
            Dictionary containing keyword arguments for the AlphaOmega extractor,
            with stream_id set to the class's stream_id.
        """
        extractor_kwargs = source_data.copy()
        extractor_kwargs["stream_id"] = self.stream_id
        return extractor_kwargs

    def __init__(self, folder_path: DirectoryPath, verbose: bool = False, es_key: str = "ElectricalSeries"):
        """
        Load and prepare data for AlphaOmega.

        Parameters
        ----------
        folder_path: string or Path
            Path to the folder of .mpx files.
        verbose: boolean
            Allows verbose.
            Default is False.
        es_key: str, default: "ElectricalSeries"
        """
        super().__init__(folder_path=folder_path, verbose=verbose, es_key=es_key)

    def get_metadata(self) -> dict:
        """
        Get metadata for the AlphaOmega recording.

        Retrieves metadata from the AlphaOmega recording and adds session
        start time from the recording annotations.

        Returns
        -------
        dict
            Dictionary containing metadata for the AlphaOmega recording,
            including NWBFile section with session_start_time extracted
            from the recording annotations.
        """
        metadata = super().get_metadata()
        annotation = self.recording_extractor.neo_reader.raw_annotations
        metadata["NWBFile"].update(session_start_time=annotation["blocks"][0]["rec_datetime"])
        return metadata
