from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class MCSRawRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting MCSRaw data.

    Using the :py:class:`~spikeinterface.extractors.MCSRawRecordingExtractor`.
    """

    display_name = "MCSRaw Recording"
    associated_suffixes = (".raw",)
    info = "Interface for MCSRaw recording data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the .raw file."
        return source_schema

    def __init__(self, file_path: FilePath, verbose: bool = True, es_key: str = "ElectricalSeries"):
        """
        Load and prepare data for MCSRaw.

        Parameters
        ----------
        file_path: string or Path
            Path to the .raw file.
        verbose: bool, default: True
            Allows verbose.
        es_key: str, default: "ElectricalSeries"
        """
        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key)
