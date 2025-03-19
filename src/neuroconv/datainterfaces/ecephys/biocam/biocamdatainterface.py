from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class BiocamRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting Biocam data.

    Using the :py:class:`~spikeinterface.extractors.BiocamRecordingExtractor`.
    """

    display_name = "Biocam Recording"
    associated_suffixes = (".bwr",)
    info = "Interface for Biocam recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        schema = super().get_source_schema()
        schema["properties"]["file_path"]["description"] = "Path to the .bwr file."
        return schema

    def __init__(self, file_path: FilePath, verbose: bool = False, es_key: str = "ElectricalSeries"):
        """
        Load and prepare data for Biocam.

        Parameters
        ----------
        file_path : string or Path
            Path to the .bwr file.
        verbose : bool, default: False
            Allows verbose.
        es_key: str, default: "ElectricalSeries"
        """
        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)
