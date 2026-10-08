from pydantic import FilePath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class BiocamRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting Biocam data.

    Uses the :py:func:`~spikeinterface.extractors.read_biocam` reader from SpikeInterface.
    """

    display_name = "Biocam Recording"
    associated_suffixes = (".bwr",)
    info = "Interface for Biocam recording data."

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import BiocamRecordingExtractor

        return BiocamRecordingExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        schema = super().get_source_schema()
        schema["properties"]["file_path"]["description"] = "Path to the .bwr file."
        return schema

    def __init__(
        self,
        file_path: FilePath,
        *,
        verbose: bool = False,
        es_key: str | None = None,
        metadata_key: str | None = None,
    ):
        """
        Load and prepare data for Biocam.

        Parameters
        ----------
        file_path : string or Path
            Path to the .bwr file.
        verbose : bool, default: False
            Allows verbose.
        es_key: str, default: "ElectricalSeries"
        metadata_key : str, optional
            Key that indexes this interface's entries in the dict-based metadata. Defaults to
            ``"biocam_recording"``.
        """

        super().__init__(file_path=file_path, verbose=verbose, es_key=es_key, metadata_key=metadata_key)

        if metadata_key is None:
            self.metadata_key = "biocam_recording"
